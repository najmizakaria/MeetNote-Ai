"""Keep draft and final audio windows separate for desktop live captions."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .audio import TARGET_RATE


CONTEXT = int(0.48 * TARGET_RATE)
PAUSE = int(0.55 * TARGET_RATE)
FIRST_DRAFT = int(0.75 * TARGET_RATE)
DRAFT_INTERVAL = int(0.75 * TARGET_RATE)
MAX_PHRASE = 8 * TARGET_RATE


@dataclass
class LiveClip:
    samples: np.ndarray
    start: int = 0
    cutoff: int | None = None


def speech_timestamps(samples):
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    return get_speech_timestamps(samples, VadOptions(
        threshold=0.4, min_speech_duration_ms=64,
        min_silence_duration_ms=160, speech_pad_ms=0,
    ))


class LiveSpeech:
    def __init__(self):
        self.pending = np.empty(0, dtype=np.float32)
        self.context = self.pending
        self.speech_end = None
        self.next_draft = FIRST_DRAFT
        self.revision = 0

    def add(self, samples):
        previous = len(self.pending)
        lookback = min(previous, CONTEXT)
        self.pending = np.concatenate((self.pending, samples))
        offset = previous - lookback
        for region in speech_timestamps(self.pending[offset:]):
            end = offset + region["end"]
            if end > previous:
                if self.speech_end is None:
                    self.next_draft = max(0, offset + region["start"]) + FIRST_DRAFT
                self.speech_end = max(end, self.speech_end or 0)

        if self.speech_end is None:
            self.pending = self.pending[-CONTEXT:]
        elif len(self.pending) - self.speech_end >= PAUSE:
            return self.cut(self.speech_end + CONTEXT // 2)
        elif len(self.pending) >= MAX_PHRASE + CONTEXT:
            return self.cut(MAX_PHRASE, overlap=True)
        return None

    def cut(self, count, *, overlap=False):
        before = self.context
        after = CONTEXT if overlap else 0
        clip = LiveClip(
            np.concatenate((before, self.pending[:count + after])),
            start=len(before),
            cutoff=len(before) + count if overlap else None,
        )
        self.context = self.pending[count - CONTEXT:count] if overlap else self.pending[:0]
        self.pending = self.pending[count:]
        self.speech_end = max(0, self.speech_end - count) if overlap else None
        self.next_draft = FIRST_DRAFT
        self.revision += 1
        return clip

    def draft(self):
        if self.speech_end is None or len(self.pending) < self.next_draft:
            return None
        self.next_draft = len(self.pending) + DRAFT_INTERVAL
        return self.pending

    def finish(self):
        if len(self.pending):
            return self.cut(len(self.pending))
