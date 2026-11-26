"""Live recording from audio devices attached to the LOCAL Python process.

Never use this to record the microphone of a visitor to a hosted Streamlit app.
For Windows system audio choose Stereo Mix or VB-Cable's CABLE Output input.
"""
from __future__ import annotations
from collections import defaultdict
from threading import Lock
import time
import numpy as np
from .audio import to_mono_16k, mix_tracks, wav_bytes


def list_inputs() -> list[dict]:
    import sounddevice as sd  # optional: installed only in local environment
    return [dict(index=i, name=d["name"], channels=int(d["max_input_channels"]),
                 rate=int(d["default_samplerate"]))
            for i, d in enumerate(sd.query_devices()) if int(d["max_input_channels"]) > 0]


class LocalCapture:
    def __init__(self, devices: dict[str, int]):
        self._validate_devices(devices)
        self.devices = dict(devices)
        self._streams = {}
        self._lock = Lock()
        self._controls = Lock()
        self._buffers: dict[int, list[np.ndarray]] = defaultdict(list)
        self._segments = []
        self.active = False
        self.started_at = 0.0
        self.last_error = ""

    @staticmethod
    def _validate_devices(devices):
        if not devices:
            raise ValueError("Choose at least one input device")
        if len(devices) != len(set(devices.values())):
            raise ValueError("Choose two different physical/virtual input devices for Both mode")

    def start(self) -> None:
        with self._controls:
            if self.active:
                return
            self._set_devices(self.devices)
            self.started_at = time.monotonic()
            self.active = True

    def switch_devices(self, devices: dict[str, int]) -> None:
        """Change inputs within the current recording, preserving any buffered audio."""
        devices = dict(devices)
        self._validate_devices(devices)
        with self._controls:
            if not self.active:
                raise RuntimeError("Start recording before switching inputs")
            if devices != self.devices:
                self._set_devices(devices)

    def _set_devices(self, devices):
        previous = self._streams
        opened = {}
        try:
            for label, device_id in devices.items():
                if device_id not in previous:
                    opened[device_id] = self._open_stream(label, device_id)
        except Exception:
            for stream, _ in opened.values():
                self._close_stream(stream)
            raise

        with self._lock:
            self._end_segment()
            self._streams = {device_id: previous.get(device_id) or opened[device_id]
                             for device_id in devices.values()}
            self.devices = devices
        for device_id, (stream, _) in previous.items():
            if device_id not in self._streams:
                self._close_stream(stream)

    def _open_stream(self, label, device_id):
        import sounddevice as sd

        info = sd.query_devices(device_id, kind="input")
        rate = int(info["default_samplerate"])
        if rate <= 0:
            raise RuntimeError(f"Invalid sample rate for {label}")

        def callback(indata, frames, timing, status):
            with self._lock:
                current = self._streams.get(device_id)
                # Ignore samples from streams that are warming up or have been replaced.
                if current is None or current[0] is not stream:
                    return
                if status:
                    self.last_error = str(status)
                self._buffers[device_id].append(indata.copy())

        stream = sd.InputStream(
            device=device_id, channels=1, samplerate=rate,
            dtype="float32", blocksize=0, callback=callback,
        )
        try:
            stream.start()
        except Exception:
            self._close_stream(stream)
            raise
        return stream, rate

    def _current_tracks(self):
        return [(label, self._buffers[device_id], self._streams[device_id][1])
                for label, device_id in self.devices.items() if self._buffers.get(device_id)]

    def _end_segment(self):
        tracks = self._current_tracks()
        if tracks:
            self._segments.append(tracks)
        self._buffers.clear()

    @property
    def elapsed(self) -> float:
        return max(0.0, time.monotonic() - self.started_at) if self.started_at else 0.0

    def buffered_seconds(self) -> float:
        with self._lock:
            segments = [*self._segments, self._current_tracks()]
            return sum(max((sum(map(len, chunks)) / rate for _, chunks, rate in tracks),
                           default=0.0) for tracks in segments)

    def drain(self) -> bytes | None:
        """Consume and mix the currently available audio buffer."""
        mixed = self.drain_samples(balance=False)
        return wav_bytes(mixed) if len(mixed) else None

    def drain_samples(self, *, balance=True) -> np.ndarray:
        """Consume the buffer as mono 16 kHz samples for live recognition."""
        with self._lock:
            self._end_segment()
            segments, self._segments = self._segments, []
        mixed = []
        for segment in segments:
            tracks = []
            for label, chunks, rate in segment:
                joined = np.concatenate(chunks, axis=0)
                track = to_mono_16k(joined, rate)
                if balance:
                    peak = float(np.max(np.abs(track), initial=0.0))
                    # Stereo Mix level follows speaker volume. Limit mic noise amplification.
                    limit = 24.0 if label == "laptop audio" else 2.0
                    if 0.002 <= peak < 0.24:
                        track *= min(limit, 0.24 / peak)
                tracks.append(track)
            mixed.append(mix_tracks(tracks))
        return np.concatenate(mixed) if mixed else np.empty(0, dtype=np.float32)

    def stop(self) -> None:
        with self._controls:
            self.active = False
            for stream, _ in self._streams.values():
                self._close_stream(stream)
            with self._lock:
                self._end_segment()
                self._streams = {}

    @staticmethod
    def _close_stream(stream):
        try:
            stream.stop()
        except Exception:
            pass
        try:
            stream.close()
        except Exception:
            pass
