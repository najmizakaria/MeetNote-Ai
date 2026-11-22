from meetnote.audio import wav_bytes
from meetnote.transcriber import transcribe_bytes
import numpy as np


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
