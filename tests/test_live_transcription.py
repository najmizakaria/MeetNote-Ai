from types import SimpleNamespace

import numpy as np

from meetnote import live_transcription as live
from meetnote.local_capture import LocalCapture
from meetnote.transcriber import transcribe_live


def test_live_mix_keeps_quiet_laptop_audio_audible():
    capture = LocalCapture({"microphone": 0, "laptop audio": 1})
    capture._rates = dict.fromkeys(capture.devices, live.TARGET_RATE)
    capture._buffers["microphone"].append(np.zeros(512, dtype=np.float32))
    capture._buffers["laptop audio"].append(np.full(512, 0.01, dtype=np.float32))
    np.testing.assert_allclose(capture.drain_samples(), 0.12)


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
    np.testing.assert_array_equal(speech.draft(), seconds[-live.DRAFT_WINDOW:])
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
