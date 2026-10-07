"""Central configuration for the Bangla voice smart home controller."""

from command_parser import DEVICE_VARIANTS, ACTION_VARIANTS

# --- Audio ---
SAMPLE_RATE = 16000
CHANNELS = 1
FRAME_MS = 32  # silero-vad expects 512-sample chunks at 16kHz
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_MS / 1000)  # 512

# --- VAD ---
VAD_THRESHOLD = 0.6
SILENCE_MS_TO_END = 250
MIN_SPEECH_MS = 1000
MAX_SEGMENT_S = 10

# --- Noise rejection ---
MIN_SEGMENT_RMS = 0.02

# --- Transcription confidence ---
MIN_TRANSCRIPTION_LOGPROB = -1.0

# --- Whisper ---
WHISPER_MODEL_SIZE = "small"
WHISPER_COMPUTE_TYPE = "int8"
WHISPER_CPU_THREADS = 4
WHISPER_BEAM_SIZE = 1
WHISPER_BEST_OF = 1
WHISPER_TEMPERATURE = 0.0
TRANSCRIBE_TIMEOUT_S = 4.0
NUM_TRANSCRIBE_WORKERS = 2


def _build_initial_prompt():
    lines = []
    action_cycle = ["chalu", "on", "bondho", "off"]
    i = 0
    for phrases in DEVICE_VARIANTS.values():
        for phrase in phrases[:3]:
            lines.append(f"{phrase} {action_cycle[i % len(action_cycle)]} koro")
            i += 1

    device_ids = list(DEVICE_VARIANTS)
    if len(device_ids) >= 2:
        p1 = DEVICE_VARIANTS[device_ids[0]][0]
        p2 = DEVICE_VARIANTS[device_ids[1]][0]
        lines.append(f"{p1}, {p2} on koro")
        lines.append(f"{p1} chalu koro, {p2} bondho koro")

    lines.append("shob on koro")
    lines.append("shobkichu bondho koro")

    return ", ".join(lines)


INITIAL_PROMPT = _build_initial_prompt()

# --- ESP32 ---
DEFAULT_ESP32_IP = "192.168.1.1"
HTTP_TIMEOUT_S = 2.0

DEVICE_ENDPOINT_SEGMENTS = {
    "LED1": "light1",
    "LED2": "light2",
    "FAN1": "fan1",
    "FAN2": "fan2",
}

ENDPOINTS = {
    (device_id, action): f"/{segment}/{action}"
    for device_id, segment in DEVICE_ENDPOINT_SEGMENTS.items()
    for action in ACTION_VARIANTS
}