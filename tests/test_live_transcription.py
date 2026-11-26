import sys
from types import SimpleNamespace

import numpy as np
import pytest

from meetnote import live_transcription as live
from meetnote.local_capture import LocalCapture
from meetnote.transcriber import transcribe_live


@pytest.fixture
def inputs(monkeypatch):
    streams = []

    class InputStream:
        def __init__(self, *, device, callback, **kwargs):
            self.device = device
            self.callback = callback
            self.closed = False
            streams.append(self)

        def start(self):
            if self.device == 2:
                raise RuntimeError("Input unavailable")

        def stop(self):
            pass

        def close(self):
            self.closed = True

        def feed(self, level, frames=512):
            self.callback(np.full((frames, 1), level, dtype=np.float32), frames, None, None)

    monkeypatch.setitem(sys.modules, "sounddevice", SimpleNamespace(
        InputStream=InputStream,
        query_devices=lambda device, **_: {"default_samplerate": 48000 if device == 1 else 16000},
    ))
    return streams


def test_live_mix_keeps_quiet_laptop_audio_audible(inputs):
    capture = LocalCapture({"microphone": 0, "laptop audio": 1})
    capture.start()
    inputs[0].feed(0)
    inputs[1].feed(0.01, 1536)
    np.testing.assert_allclose(capture.drain_samples(), 0.12)
    capture.stop()


def test_source_switch_keeps_audio_in_order_and_reuses_shared_inputs(inputs):
    capture = LocalCapture({"microphone": 0})
    capture.start()
    started_at = capture.started_at
    inputs[0].feed(0.2)

    capture.switch_devices({"microphone": 0, "laptop audio": 1})
    assert [stream.device for stream in inputs] == [0, 1]
    inputs[0].feed(0.4)
    inputs[1].feed(0.8, 1536)

    capture.switch_devices({"laptop audio": 1})
    assert capture.active and capture.started_at == started_at
    assert [stream.closed for stream in inputs] == [True, False]
    inputs[0].feed(-1)
    inputs[1].feed(0.9, 1536)
    assert capture.buffered_seconds() == pytest.approx(1536 / live.TARGET_RATE)

    capture.stop()
    assert all(stream.closed for stream in inputs)
    np.testing.assert_allclose(capture.drain_samples(balance=False),
                               np.repeat([0.2, 0.6, 0.9], 512))
    assert len(capture.drain_samples()) == 0


def test_failed_source_switch_leaves_the_previous_input_recording(inputs):
    capture = LocalCapture({"microphone": 0})
    capture.start()
    inputs[0].feed(0.2)
    with pytest.raises(RuntimeError, match="Input unavailable"):
        capture.switch_devices({"microphone": 1, "laptop audio": 2})
    assert capture.active and capture.devices == {"microphone": 0}
    assert [stream.closed for stream in inputs] == [False, True, True]

    inputs[0].feed(0.4)
    np.testing.assert_allclose(capture.drain_samples(balance=False),
                               np.repeat([0.2, 0.4], 512))
    capture.stop()


def test_draft_refresh_never_consumes_audio_and_stop_preserves_last_phrase(monkeypatch):
    monkeypatch.setattr(live, "speech_timestamps",
                        lambda samples: [{"start": 0, "end": len(samples)}])
    speech = live.LiveSpeech()
    first = np.ones(live.FIRST_DRAFT, dtype=np.float32)
    assert speech.add(first) is None
    np.testing.assert_array_equal(speech.draft(), first)
    assert speech.draft() is None

    seconds = np.full(live.DRAFT_INTERVAL * 6, 0.5, dtype=np.float32)
    assert speech.add(seconds) is None
    np.testing.assert_array_equal(speech.draft(), np.concatenate((first, seconds)))
    np.testing.assert_array_equal(speech.finish().samples, np.concatenate((first, seconds)))
    assert speech.finish() is None


def test_pause_finalizes_phrase_and_keeps_silence_for_the_next_onset(monkeypatch):
    def detect(samples):
        voiced = np.flatnonzero(samples)
        return [{"start": voiced[0], "end": voiced[-1] + 1}] if len(voiced) else []

    monkeypatch.setattr(live, "speech_timestamps", detect)
    speech = live.LiveSpeech()
    voice = np.ones(live.FIRST_DRAFT, dtype=np.float32)
    silence = np.zeros(live.PAUSE, dtype=np.float32)
    assert speech.add(voice) is None
    first = speech.add(silence)
    np.testing.assert_array_equal(first.samples[:len(voice)], voice)
    assert len(first.samples) == len(voice) + live.CONTEXT // 2
    assert speech.revision == 1
    assert speech.draft() is None
    assert speech.add(voice) is None
    tail = speech.finish()
    np.testing.assert_array_equal(tail.samples[-len(voice):], voice)
    assert tail.start == 0


def test_long_phrase_keeps_overlap_and_assigns_words_to_one_side(monkeypatch):
    monkeypatch.setattr(live, "speech_timestamps",
                        lambda samples: [{"start": 0, "end": len(samples)}])
    speech = live.LiveSpeech()
    raw = np.arange(live.MAX_PHRASE + live.CONTEXT, dtype=np.float32)
    first = speech.add(raw)
    tail = speech.finish()
    np.testing.assert_array_equal(first.samples[-2 * live.CONTEXT:], tail.samples)
    assert first.cutoff == live.MAX_PHRASE and tail.start == live.CONTEXT

    def recognize(samples, **kwargs):
        assert kwargs["word_timestamps"]
        boundary = (first.cutoff if samples is first.samples else tail.start) / live.TARGET_RATE
        words = [SimpleNamespace(word=" before", start=boundary - 0.2, end=boundary),
                 SimpleNamespace(word=" after", start=boundary, end=boundary + 0.2)]
        return [SimpleNamespace(words=words)], SimpleNamespace(language="ms")

    model = SimpleNamespace(transcribe=recognize)
    assert transcribe_live(first.samples, model, "ms", cutoff=first.cutoff) == ("before", "ms")
    assert transcribe_live(tail.samples, model, "ms", start=tail.start) == ("after", "ms")
