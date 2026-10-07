import numpy as np
import torch
from silero_vad import load_silero_vad, VADIterator

import config


class VADProcessor:
    def __init__(self, on_rejected=None, on_speech_start=None):

        self._model = load_silero_vad()
        self._iterator = VADIterator(
            self._model,
            sampling_rate=config.SAMPLE_RATE,
            threshold=config.VAD_THRESHOLD,
            min_silence_duration_ms=config.SILENCE_MS_TO_END,
        )
        self._buffer: list[np.ndarray] = []
        self._in_speech = False
        self._on_rejected = on_rejected
        self._on_speech_start = on_speech_start

    @staticmethod
    def _rms(segment: np.ndarray) -> float:
        return float(np.sqrt(np.mean(np.square(segment)))) if segment.size else 0.0

    def _finalize(self, segment: np.ndarray):

        min_samples = int(config.SAMPLE_RATE * config.MIN_SPEECH_MS / 1000)
        if segment.size < min_samples:
            if self._on_rejected:
                self._on_rejected("too_short", None)
            return None
        rms = self._rms(segment)
        if rms < config.MIN_SEGMENT_RMS:
            if self._on_rejected:
                self._on_rejected("too_quiet", rms)
            return None
        return segment

    def process_frame(self, frame: np.ndarray):

        event = self._iterator(torch.from_numpy(frame), return_seconds=False)

        if self._in_speech:
            self._buffer.append(frame)

        if event is not None:
            if "start" in event:
                self._in_speech = True
                self._buffer = [frame]
                if self._on_speech_start:
                    self._on_speech_start()
            elif "end" in event:
                self._in_speech = False
                if self._buffer:
                    segment = np.concatenate(self._buffer)
                    self._buffer = []
                    return self._finalize(segment)

        max_samples = int(config.SAMPLE_RATE * config.MAX_SEGMENT_S)
        if self._in_speech and sum(b.size for b in self._buffer) > max_samples:
            segment = np.concatenate(self._buffer)
            self._buffer = []
            self._in_speech = False
            self._iterator.reset_states()
            return self._finalize(segment)
        return None