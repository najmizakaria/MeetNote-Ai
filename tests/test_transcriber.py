<<<<<<< HEAD
from meetnote.audio import wav_bytes
from meetnote.transcriber import ALLOWED_LANGUAGES, _detect_allowed_language, transcribe_bytes, transcribe_live
=======
import sys
from types import SimpleNamespace

>>>>>>> 483ff043d3b546dc69552f513ca1f6cdee94c35c
import numpy as np
import pytest

from meetnote.audio import wav_bytes
from meetnote.transcriber import LANGUAGES, make_model, transcribe_bytes, transcribe_live


class FakeInfo:
    def __init__(self, language="en"):
        self.language = language


class FakeModel:
    def transcribe(self, filename, **kwargs):
        with open(filename, "rb") as f:
            assert f.read(4) == b"RIFF"
        assert kwargs.get("language") == "en"
        return [type("Seg", (), {"text": " Hello meeting "})()], FakeInfo()


class FakeMultilingualModel:
    def __init__(self, probs):
        self.probs = probs
        self.transcribe_languages = []

    def detect_language(self, audio=None):
        top_lang, top_prob = self.probs[0]
        return top_lang, top_prob, self.probs

    def transcribe(self, samples, **kwargs):
        lang = kwargs.get("language")
        self.transcribe_languages.append(lang)
        return [type("Seg", (), {"text": " Selamat pagi "})()], FakeInfo(lang)


def test_transcription_adapter_with_fake_model():
    text, lang = transcribe_bytes(wav_bytes(np.zeros(160, dtype=np.float32)), ".wav",
                                  FakeModel(), language="en")
    assert text == "Hello meeting"
    assert lang == "en"


<<<<<<< HEAD
def test_auto_detect_restricts_to_allowed_languages():
    assert ALLOWED_LANGUAGES == frozenset({"en", "ms", "id"})
    model = FakeMultilingualModel([("ru", 0.72), ("ms", 0.18), ("en", 0.07), ("id", 0.03)])
    samples = np.ones(1600, dtype=np.float32) * 0.1

    text, lang = transcribe_live(samples, model, None, draft=True)
    assert text == "Selamat pagi"
    assert lang == "ms"
    assert model.transcribe_languages == ["ms"]


def test_detect_allowed_language_falls_back_to_en_when_none_allowed():
    model = FakeMultilingualModel([("ru", 0.9), ("fr", 0.1)])
    assert _detect_allowed_language(model, np.ones(1600, dtype=np.float32), vad_filter=False) == "en"
=======
@pytest.mark.parametrize(("first", "second"), [("en", "ms"), ("ms", "en")])
def test_auto_detection_only_considers_english_and_malay(monkeypatch, first, second):
    allowed_scores = [(first, 0.06), (second, 0.04)]

    class FakeWhisper:
        def __init__(self, *args, **kwargs):
            pass

        def detect_language(self):
            return "id", 0.9, [("id", 0.9), *allowed_scores]

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=FakeWhisper))
    assert make_model("tiny").detect_language() == (first, 0.06, allowed_scores)
    assert set(LANGUAGES.values()) == {None, "en", "ms"}


def test_transcription_rejects_other_language_selections():
    with pytest.raises(ValueError, match="English, Bahasa Melayu"):
        transcribe_live(np.zeros(160, dtype=np.float32), FakeModel(), language="id")
>>>>>>> 483ff043d3b546dc69552f513ca1f6cdee94c35c
