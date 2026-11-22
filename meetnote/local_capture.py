"""Live recording from audio devices attached to the LOCAL Python process.

Never use this to record the microphone of a visitor to a hosted Streamlit app.
For Windows system audio choose Stereo Mix or VB-Cable's CABLE Output input.
"""
from __future__ import annotations
from collections import defaultdict
from threading import RLock
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
        if not devices:
            raise ValueError("Choose at least one input device")
        if len(devices) != len(set(devices.values())):
            raise ValueError("Choose two different physical/virtual input devices for Both mode")
        self.devices = devices
        self._streams = []
        self._lock = RLock()
        self._buffers: dict[str, list[np.ndarray]] = defaultdict(list)
        self._rates: dict[str, int] = {}
        self.active = False
        self.started_at = 0.0
        self.last_error = ""

    def start(self) -> None:
        import sounddevice as sd
        if self.active:
            return
        try:
            for label, device_id in self.devices.items():
                info = sd.query_devices(device_id, kind="input")
                rate = int(info["default_samplerate"])
                if rate <= 0:
                    raise RuntimeError(f"Invalid sample rate for {label}")
                self._rates[label] = rate

                def callback(indata, frames, timing, status, source=label):
                    if status:
                        self.last_error = str(status)
                    with self._lock:
                        self._buffers[source].append(indata.copy())

                stream = sd.InputStream(
                    device=device_id, channels=1, samplerate=rate,
                    dtype="float32", blocksize=0, callback=callback,
                )
                self._streams.append(stream)
                stream.start()
            self.started_at = time.monotonic()
            self.active = True
        except Exception:
            self.stop()
            raise

    @property
    def elapsed(self) -> float:
        return max(0.0, time.monotonic() - self.started_at) if self.started_at else 0.0

    def buffered_seconds(self) -> float:
        with self._lock:
            if not self._rates:
                return 0.0
            durations = [sum(len(a) for a in self._buffers[label]) / rate
                         for label, rate in self._rates.items() if rate > 0]
        return max(durations, default=0.0)

    def drain(self) -> bytes | None:
        """Consume and mix the currently available audio buffer."""
        with self._lock:
            blocks = {label: self._buffers.pop(label, [])
                      for label in self.devices}
        tracks = []
        for label, chunks in blocks.items():
            if chunks:
                joined = np.concatenate(chunks, axis=0)
                tracks.append(to_mono_16k(joined, self._rates[label]))
        mixed = mix_tracks(tracks)
        return wav_bytes(mixed) if len(mixed) else None

    def stop(self) -> None:
        self.active = False
        for stream in self._streams:
            try:
                stream.stop()
                # A stream that failed to start still needs to be closed.
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass
        self._streams.clear()
