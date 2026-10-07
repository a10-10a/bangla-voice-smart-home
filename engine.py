import queue
import threading
import numpy as np
import sounddevice as sd
from PyQt6.QtCore import QObject, pyqtSignal

import config
from vad_processor import VADProcessor
from transcriber import Transcriber
from command_parser import parse_command
from esp32_client import ESP32Client


class VoiceEngine(QObject):
    log_message = pyqtSignal(str)
    transcription_ready = pyqtSignal(str)
    status_changed = pyqtSignal(str, str)   # (text, kind); kind in {"idle", "busy", "ok", "error"}
    start_failed = pyqtSignal(str)          # emitted if start() couldn't complete; GUI should reset buttons

    def __init__(self, mic_device=None):
        super().__init__()
        self._frame_queue: queue.Queue = queue.Queue()
        self._segment_queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()
        self._mic_device = mic_device

        self._vad = VADProcessor(
            on_rejected=self._on_segment_rejected,
            on_speech_start=lambda: self.status_changed.emit("Speech detected — capturing…", "busy"),
        )
        self._esp32 = ESP32Client(config.DEFAULT_ESP32_IP)
        self._transcriber = None

        self._stream = None
        self._vad_thread = None
        self._transcribe_thread = None
        self._start_thread = None

    def _on_segment_rejected(self, reason: str, rms):
        if reason == "too_quiet":
            self.log_message.emit(
                f"INFO: Ignored quiet segment (rms={rms:.4f}, floor={config.MIN_SEGMENT_RMS}) — likely background noise."
            )
        self.status_changed.emit("Listening — waiting for speech", "ok")

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            if getattr(status, "input_overflow", False):
                self.log_message.emit(
                    "WARNING: audio input overflow — the CPU couldn't read audio fast enough; some audio may have been dropped."
                )
            else:
                self.log_message.emit(f"WARNING: audio stream status: {status}")
        self._frame_queue.put(indata[:, 0].copy())  # minimal work: real-time thread

    def _vad_loop(self):
        while not self._stop_event.is_set():
            try:
                frame = self._frame_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                segment = self._vad.process_frame(frame)
            except Exception as exc:
                self.log_message.emit(f"ERROR: voice detection error: {exc}")
                self.status_changed.emit("Error: voice detection hit a problem", "error")
                continue
            if segment is not None:
                self._segment_queue.put(segment)

    def _transcribe_tick(self):
        try:
            audio = self._segment_queue.get(timeout=0.05)
        except queue.Empty:
            audio = None

        if audio is not None:
            peak = np.max(np.abs(audio)) if audio.size else 0.0
            if peak > 1e-6:
                audio = audio / peak
            job_id = self._transcriber.submit(audio)
            if job_id is None:
                self._segment_queue.put(audio)  # both workers busy; retry next tick
            else:
                self.status_changed.emit("Transcribing…", "busy")

        for _job_id, text, error, avg_logprob in self._transcriber.poll_all():
            if error:
                self.log_message.emit(f"ERROR: Transcription failed: {error}")
                self.status_changed.emit("Listening — waiting for speech", "ok")
                continue
            if not text:
                self.status_changed.emit("Listening — waiting for speech", "ok")
                continue

            self.transcription_ready.emit(text)

            if avg_logprob is not None and avg_logprob < config.MIN_TRANSCRIPTION_LOGPROB:
                self.log_message.emit(
                    f'INFO: confidence was low (avg_logprob={avg_logprob:.2f}) for "{text}" — ignored.'
                )
                self.status_changed.emit("Listening — waiting for speech", "ok")
                continue

            commands = parse_command(text)
            if not commands:
                self.log_message.emit(f'INFO: Heard "{text}" -> invalid command, ignored.')
                self.status_changed.emit("Listening — waiting for speech", "ok")
                continue
            for device_id, action in commands:
                self._esp32.send_command(
                    device_id, action,
                    on_result=lambda ok, msg, t=text, d=device_id, a=action: self.log_message.emit(
                        f'{"INFO" if ok else "ERROR"}: "{t}" -> {d} {a}: {"OK" if ok else "FAILED"} ({msg})'
                    ),
                )
            self.status_changed.emit("Listening — waiting for speech", "ok")

        self._transcriber.enforce_timeouts()

    def _transcribe_loop(self):
        while not self._stop_event.is_set():
            try:
                self._transcribe_tick()
            except Exception as exc:
                self.log_message.emit(f"ERROR: transcription loop hit an unexpected problem: {exc}")
                self.status_changed.emit("Error: transcription loop hit a problem", "error")

    def start(self):
        self._stop_event.clear()
        self.status_changed.emit("Loading speech model… this can take a while.", "busy")
        self.log_message.emit("INFO: Loading speech model(s)...")
        self._start_thread = threading.Thread(target=self._start_worker, daemon=True)
        self._start_thread.start()

    def _start_worker(self):
        try:
            self._transcriber = Transcriber(
                num_workers=config.NUM_TRANSCRIBE_WORKERS,
                on_timeout=lambda: self.log_message.emit(
                    "WARNING: Utterance took too long (likely out of scope) — cancelled, still listening."
                ),
            )
        except Exception as exc:
            self.log_message.emit(f"ERROR: Failed to load speech model: {exc}")
            self.status_changed.emit("Error: failed to load speech model", "error")
            self.start_failed.emit(str(exc))
            return

        if self._stop_event.is_set():
            self._transcriber.shutdown()
            self._transcriber = None
            return

        try:
            self._stream = sd.InputStream(
                samplerate=config.SAMPLE_RATE, channels=config.CHANNELS, dtype="float32",
                blocksize=config.FRAME_SAMPLES, device=self._mic_device, callback=self._audio_callback,
            )
            self._stream.start()
        except Exception as exc:
            if self._stream is not None:
                try:
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            self.log_message.emit(f"ERROR: Failed to open microphone: {exc}")
            self.status_changed.emit("Error: failed to open microphone", "error")
            self._transcriber.shutdown()
            self._transcriber = None
            self.start_failed.emit(str(exc))
            return

        if self._stop_event.is_set():
            self._stream.stop()
            self._stream.close()
            self._stream = None
            self._transcriber.shutdown()
            self._transcriber = None
            return

        self._vad_thread = threading.Thread(target=self._vad_loop, daemon=True)
        self._transcribe_thread = threading.Thread(target=self._transcribe_loop, daemon=True)
        self._vad_thread.start()
        self._transcribe_thread.start()
        self.log_message.emit("INFO: Listening started.")
        self.status_changed.emit("Listening — waiting for speech", "ok")

    def stop(self):
        self._stop_event.set()
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if self._transcriber is not None:
            self._transcriber.shutdown()
            self._transcriber = None
        self.log_message.emit("INFO: Listening stopped.")
        self.status_changed.emit("Idle", "idle")