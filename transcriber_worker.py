def worker_main(conn, model_size, compute_type, cpu_threads, initial_prompt,
                 beam_size, best_of, temperature):
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(model_size, device="cpu", compute_type=compute_type, cpu_threads=cpu_threads)
    except Exception as exc:
        conn.send(f"LOAD_FAILED: {exc}")
        return

    conn.send("READY")

    while True:
        try:
            job_id, audio = conn.recv()
        except EOFError:
            return
        try:
            segments, _ = model.transcribe(
                audio, language="bn", task="transcribe",
                beam_size=beam_size, best_of=best_of, temperature=temperature,
                initial_prompt=initial_prompt, vad_filter=False,
            )
            segments = list(segments)  # materialize the generator so we can use it twice
            text = "".join(s.text for s in segments).strip()
            if segments:
                total_dur = sum(max(s.end - s.start, 1e-6) for s in segments)
                avg_logprob = sum(s.avg_logprob * (s.end - s.start) for s in segments) / total_dur
            else:
                avg_logprob = None
            conn.send((job_id, text, None, avg_logprob))
        except Exception as exc:
            conn.send((job_id, "", str(exc), None))