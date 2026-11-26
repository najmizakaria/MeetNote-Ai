from meetnote.audio import wav_bytes
from meetnote.transcriber import ALLOWED_LANGUAGES, _detect_allowed_language, transcribe_bytes, transcribe_live
import numpy as np


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
