"""Speech recognition, loaded lazily to keep app startup fast."""
from __future__ import annotations
from operator import itemgetter
import tempfile
from pathlib import Path

<<<<<<< HEAD
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
=======
LANGUAGES = {"Auto detect": None, "English": "en", "Bahasa Melayu": "ms"}


def _transcribe(audio, model, language, **options):
    if language not in LANGUAGES.values():
        raise ValueError("Choose English, Bahasa Melayu, or Auto detect.")
    return model.transcribe(audio, language=language, condition_on_previous_text=False, **options)
>>>>>>> 483ff043d3b546dc69552f513ca1f6cdee94c35c


def transcribe_bytes(data: bytes, suffix: str, model, language: str | None = None) -> tuple[str, str | None]:
    if not data:
        return "", None
    # faster-whisper reads the file before this temporary directory is cleaned up
    with tempfile.TemporaryDirectory(prefix="meetnote-") as tmp:
        filename = Path(tmp) / ("clip" + suffix)
        filename.write_bytes(data)
        return transcribe_file(filename, model, language)


def transcribe_file(filename: Path, model, language: str | None = None) -> tuple[str, str | None]:
<<<<<<< HEAD
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
=======
    segments, info = _transcribe(str(filename), model, language, beam_size=3, vad_filter=True)
>>>>>>> 483ff043d3b546dc69552f513ca1f6cdee94c35c
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
