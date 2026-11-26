import sys
from types import SimpleNamespace

import numpy as np
import pytest

from meetnote.audio import wav_bytes
from meetnote.transcriber import LANGUAGES, make_model, transcribe_bytes, transcribe_live


class FakeInfo:
    language = "en"


class FakeModel:
    def transcribe(self, filename, **kwargs):
        with open(filename, "rb") as f:
            assert f.read(4) == b"RIFF"
        assert kwargs.get("language") == "en"
        return [type("Seg", (), {"text": " Hello meeting "})()], FakeInfo()


def test_transcription_adapter_with_fake_model():
    text, lang = transcribe_bytes(wav_bytes(np.zeros(160, dtype=np.float32)), ".wav",
                                  FakeModel(), language="en")
    assert text == "Hello meeting"
    assert lang == "en"


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
