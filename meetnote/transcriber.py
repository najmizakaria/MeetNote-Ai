"""Speech recognition, loaded lazily to keep app startup fast."""
from __future__ import annotations
from operator import itemgetter
import tempfile
from pathlib import Path

LANGUAGES = {"Auto detect": None, "English": "en", "Bahasa Melayu": "ms"}


def _transcribe(audio, model, language, **options):
    if language not in LANGUAGES.values():
        raise ValueError("Choose English, Bahasa Melayu, or Auto detect.")
    return model.transcribe(audio, language=language, condition_on_previous_text=False, **options)


def transcribe_bytes(data: bytes, suffix: str, model, language: str | None = None) -> tuple[str, str | None]:
    if not data:
        return "", None
    # faster-whisper reads the file before this temporary directory is cleaned up
    with tempfile.TemporaryDirectory(prefix="meetnote-") as tmp:
        filename = Path(tmp) / ("clip" + suffix)
        filename.write_bytes(data)
        return transcribe_file(filename, model, language)


def transcribe_file(filename: Path, model, language: str | None = None) -> tuple[str, str | None]:
    segments, info = _transcribe(str(filename), model, language, beam_size=3, vad_filter=True)
    sentence = " ".join(s.text.strip() for s in segments if s.text.strip())
    return sentence, getattr(info, "language", None)


def transcribe_live(samples, model, language, *, draft=False, start=0, cutoff=None):
    from .audio import TARGET_RATE

    timed = bool(start or cutoff is not None)
    draft_options = {"temperature": 0.0} if draft else {}
    segments, info = _transcribe(
        samples, model, language, beam_size=1 if draft else 3, vad_filter=not draft,
        without_timestamps=draft, word_timestamps=timed,
        **draft_options,
    )
    if timed:
        words = []
        for segment in segments:
            for word in segment.words or ():
                center = (word.start + word.end) * TARGET_RATE / 2
                if center > start and (cutoff is None or center <= cutoff):
                    words.append(word.word)
        sentence = "".join(words).strip()
    else:
        sentence = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
    return sentence, getattr(info, "language", None)


def make_model(name: str):
    from faster_whisper import WhisperModel

    class MeetingWhisper(WhisperModel):
        def detect_language(self, *args, **kwargs):
            _, _, scores = super().detect_language(*args, **kwargs)
            allowed_scores = [(code, probability) for code, probability in scores if code in LANGUAGES.values()]
            language, probability = max(allowed_scores, key=itemgetter(1))
            return language, probability, allowed_scores

    bundled_tiny = Path(__file__).resolve().parents[1] / "_models" / "tiny"
    model = str(bundled_tiny) if name == "tiny" and (bundled_tiny / "model.bin").is_file() else name
    return MeetingWhisper(model, device="cpu", compute_type="int8")
