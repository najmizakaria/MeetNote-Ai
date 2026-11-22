"""Audio data conversion used by local capture and downloads."""
from __future__ import annotations
import io
import math
import wave
import numpy as np

TARGET_RATE = 16000


def to_mono_16k(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    """Convert mono/stereo float data into 16 kHz mono float32.

    Linear interpolation keeps dependencies small; use an external resampler for
    professional audio processing. Handles empty recordings gracefully.
    """
    if sample_rate <= 0:
        raise ValueError("Invalid audio sample rate")
    x = np.asarray(samples, dtype=np.float32)
    if x.ndim == 2:
        x = x.mean(axis=1)
    if x.ndim != 1:
        raise ValueError("Expected mono or multichannel audio")
    if len(x) == 0:
        return np.empty(0, dtype=np.float32)
    if sample_rate == TARGET_RATE:
        return np.clip(x, -1.0, 1.0)
    new_length = max(1, round(len(x) * TARGET_RATE / sample_rate))
    output = np.interp(
        np.arange(new_length) / TARGET_RATE,
        np.arange(len(x)) / sample_rate,
        x,
        left=0,
        right=float(x[-1]),
    )
    return np.clip(output, -1.0, 1.0).astype(np.float32)


def mix_tracks(tracks: list[np.ndarray]) -> np.ndarray:
    """Mix mono tracks at the same sample rate, padding shorter ones with silence.

    The tracks are aligned at the start of each drained segment; minor drift is
    possible across different physical audio interfaces.
    """
    valid = [np.asarray(t, dtype=np.float32) for t in tracks if len(t)]
    if not valid:
        return np.empty(0, dtype=np.float32)
    length = max(map(len, valid))
    output = np.zeros(length, dtype=np.float32)
    for track in valid:
        output[:len(track)] += track / len(valid)
    return np.clip(output, -1.0, 1.0)


def wav_bytes(samples: np.ndarray, sample_rate: int = TARGET_RATE) -> bytes:
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    result = io.BytesIO()
    with wave.open(result, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())
    return result.getvalue()


def has_audible_content(samples: np.ndarray, threshold: float = 0.002) -> bool:
    if len(samples) == 0:
        return False
    return float(np.sqrt(np.mean(np.square(samples, dtype=np.float64)))) >= threshold
