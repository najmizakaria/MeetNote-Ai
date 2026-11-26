"""Speech recognition, loaded lazily to keep app startup fast."""
from __future__ import annotations
import tempfile
from pathlib import Path

LANGUAGES = {"Auto detect": None, "English": "en", "Bahasa Melayu": "ms", "Indonesian": "id"}
ALLOWED_LANGUAGES = frozenset(code for code in LANGUAGES.values() if code)


def _detect_allowed_language(model, audio, *, vad_filter: bool) -> str | None:
    if audio is None or len(audio) == 0:
        return None
    if vad_filter:
        from faster_whisper.vad import VadOptions, collect_chunks, get_speech_timestamps

        speech_chunks = get_speech_timestamps(audio, VadOptions(min_silence_duration_ms=160))
        if not speech_chunks:
            return None
        import numpy as np

        audio_chunks, _ = collect_chunks(audio, speech_chunks)
        audio = np.concatenate(audio_chunks, axis=0)

    _, _, all_language_probs = model.detect_language(audio=audio)
    best_language = max(
        ((lang, prob) for lang, prob in all_language_probs if lang in ALLOWED_LANGUAGES),
        key=lambda item: item[1],
        default=(None, 0.0),
    )[0]
    return best_language or "en"


def transcribe_bytes(data: bytes, suffix: str, model, language: str | None = None) -> tuple[str, str | None]:
    if not data:
        return "", None
    # faster-whisper reads the file before this temporary directory is cleaned up
    with tempfile.TemporaryDirectory(prefix="meetnote-") as tmp:
        filename = Path(tmp) / ("clip" + suffix)
        filename.write_bytes(data)
        return transcribe_file(filename, model, language)


def transcribe_file(filename: Path, model, language: str | None = None) -> tuple[str, str | None]:
    audio_input: str | object = str(filename)
    if language is None and hasattr(model, "detect_language"):
        from faster_whisper.audio import decode_audio

        audio_input = decode_audio(str(filename))
        language = _detect_allowed_language(model, audio_input, vad_filter=True)
        if language is None:
            return "", None

    segments, info = model.transcribe(
        audio_input, language=language, beam_size=3,
        vad_filter=True, condition_on_previous_text=False,
    )
    sentence = " ".join(s.text.strip() for s in segments if s.text.strip())
    return sentence, getattr(info, "language", None)


def transcribe_live(samples, model, language, *, draft=False, start=0, cutoff=None):
    from .audio import TARGET_RATE

    if language is None and hasattr(model, "detect_language"):
        language = _detect_allowed_language(model, samples, vad_filter=not draft)
        if language is None:
            return "", None

    timed = bool(start or cutoff is not None)
    draft_options = {"temperature": 0.0} if draft else {}
    segments, info = model.transcribe(
        samples, language=language, beam_size=1 if draft else 3,
        vad_filter=not draft, condition_on_previous_text=False,
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
    bundled_tiny = Path(__file__).resolve().parents[1] / "_models" / "tiny"
    model = str(bundled_tiny) if name == "tiny" and (bundled_tiny / "model.bin").is_file() else name
    return WhisperModel(model, device="cpu", compute_type="int8")
