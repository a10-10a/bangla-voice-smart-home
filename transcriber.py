import multiprocessing as mp
import time

import config
from transcriber_worker import worker_main


class _Worker:
    def __init__(self):
        self._spawn()

    def _spawn(self):
        self._conn, child_conn = mp.Pipe()
        self._process = mp.Process(
            target=worker_main,
            args=(child_conn, config.WHISPER_MODEL_SIZE, config.WHISPER_COMPUTE_TYPE,
                  config.WHISPER_CPU_THREADS, config.INITIAL_PROMPT,
                  config.WHISPER_BEAM_SIZE, config.WHISPER_BEST_OF, config.WHISPER_TEMPERATURE),
            daemon=True,
        )
        self._process.start()
        self._ready = False
        self.busy = False
        self.job_id = None
        self.started_at = None

    def _pump_ready(self):
        if not self._ready and self._conn.poll():
            msg = self._conn.recv()
            if msg == "READY":
                self._ready = True
            elif isinstance(msg, str) and msg.startswith("LOAD_FAILED"):
                raise RuntimeError(msg.split(":", 1)[1].strip() if ":" in msg else msg)

    def available(self):
        self._pump_ready()
        return self._ready and not self.busy

    def submit(self, job_id, audio):
        self.busy = True
        self.job_id = job_id
        self.started_at = time.monotonic()
        self._conn.send((job_id, audio))

    def poll(self):
        self._pump_ready()
        if self.busy and self._conn.poll():
            job_id, text, error, avg_logprob = self._conn.recv()
            self.busy = False
            self.job_id = None
            self.started_at = None
            return job_id, text, error, avg_logprob
        return None

    def overdue(self):
        return self.busy and (time.monotonic() - self.started_at) > config.TRANSCRIBE_TIMEOUT_S

    def kill_and_respawn(self):
        self._process.terminate()
        self._process.join(timeout=1.0)
        if self._process.is_alive():
            self._process.kill()
            self._process.join()
        self._spawn()  # non-blocking; becomes available() again once its READY message is pumped

    def shutdown(self):
        try:
            self._process.terminate()
        except Exception:
            pass


class Transcriber:
    def __init__(self, num_workers=2, on_timeout=None):
        self._workers = [_Worker() for _ in range(num_workers)]
        for w in self._workers:
            msg = w._conn.recv()  # block once at startup so we know both models are actually loaded
            if isinstance(msg, str) and msg.startswith("LOAD_FAILED"):
                self.shutdown()
                raise RuntimeError(msg.split(":", 1)[1].strip() if ":" in msg else msg)
            w._ready = True
        self._next_job_id = 0
        self._on_timeout = on_timeout

    def submit(self, audio):
        """Non-blocking. Returns a job_id if a worker took it, else None
        (both busy but still within their timeout — caller should retry
        shortly rather than wait)."""
        for w in self._workers:
            if w.available():
                self._next_job_id += 1
                w.submit(self._next_job_id, audio)
                return self._next_job_id
        for w in self._workers:
            if w.overdue():
                if self._on_timeout:
                    self._on_timeout()
                w.kill_and_respawn()
                break
        return None

    def poll_all(self):
        results = []
        for w in self._workers:
            result = w.poll()
            if result is not None:
                results.append(result)
        return results

    def enforce_timeouts(self):
        for w in self._workers:
            if w.overdue():
                if self._on_timeout:
                    self._on_timeout()
                w.kill_and_respawn()

    def shutdown(self):
        for w in self._workers:
            w.shutdown()