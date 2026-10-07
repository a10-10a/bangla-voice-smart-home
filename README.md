# Bangla Voice-Controlled Smart Home

A local, offline-first voice assistant that understands spoken Bangla and romanized Bangla ("Benglish") commands and controls real hardware — two lights and two fans — over Wi-Fi, with no cloud services involved.

## Features

- Speech recognition tuned for Bangla + romanized Bangla phrasing (faster-whisper, small/int8)
- Voice activity detection (Silero VAD) with noise/loudness gating so background chatter doesn't trigger false commands
- Multi-device, multi-action parsing in a single utterance — e.g. "light 1 chalu koro, fan 2 bondho koro" controls both devices correctly
- "shob" / "shobkichu" ("all") voice command to control every device at once
- PyQt6 desktop GUI with live status, a color-coded log, and mic selection
- Runs fully on commodity, low-end hardware (no GPU required)
- ESP32-C3 firmware exposes a simple local HTTP API; auto-reconnects if Wi-Fi drops

## How It Works
Microphone → VAD (speech detection) → Whisper (speech-to-text)
→ Command Parser → HTTP request → ESP32 → Light/Fan

1. **VAD** continuously listens and buffers audio only while someone is speaking, trimming silence and rejecting segments that are too short or too quiet.
2. **Whisper** (running in a small pool of persistent worker processes) transcribes the finished utterance to text.
3. **Command Parser** matches the text against known device phrases and action words (digit, native-Bangla-word, and ordinal spellings are all recognized) and produces a list of (device, action) pairs.
4. **ESP32 Client** fires an HTTP GET per command to the ESP32, which flips the corresponding GPIO pin.

## Hardware

- ESP32-C3 SuperMini (or similar ESP32-C3 board)
- DRV8833 dual H-bridge driver (drives the 2 fans)
- 2 lights, 2 DC fans
- A laptop/PC running the Python app, sharing a Wi-Fi hotspot the ESP32 joins

## Software Requirements

- Python 3.9+
- Arduino IDE (or `arduino-cli`) with the **esp32** board package installed (Boards Manager → "esp32" by Espressif)
- Python dependencies in `requirements.txt`

## Setup

### 1. Flash the ESP32
1. Open the firmware sketch in the Arduino IDE.
2. Set `WIFI_SSID` / `WIFI_PASSWORD` to your hotspot's credentials.
3. Board: **Tools → Board → ESP32C3 Dev Module**.
4. Upload, then open the Serial Monitor at 115200 baud and note the printed IP address.

### 2. Configure and run the Python app
```bash
python -m venv .venv
source .venv/bin/activate      # .venv\Scripts\activate on Windows
pip install -r requirements.txt
```
Update `DEFAULT_ESP32_IP` in `config.py` to match the IP the ESP32 printed over serial (it's a DHCP lease, so this can change if the ESP32 reconnects).

```bash
python main.py
```
Pick your microphone, click **Start Listening**, and speak a command.

## Example Commands

| Say | Effect |
|---|---|
| "light 1 on koro" | Light 1 ON |
| "2 number fan bondho koro" | Fan 2 OFF |
| "light 1, light 2 on koro" | Both lights ON |
| "prothom light chalu koro, dui number fan bondho koro" | Light 1 ON, Fan 2 OFF |
| "shob on koro" | Everything ON |

## Project Structure

| File | Purpose |
|---|---|
| `esp.txt` | ESP32-C3 firmware — Wi-Fi HTTP server for the 2 lights + 2 fans |
| `main.py` | App entry point |
| `gui.py` | PyQt6 main window |
| `engine.py` | Orchestrates capture → VAD → transcription → command dispatch |
| `vad_processor.py` | Wraps Silero VAD, buffers and gates speech segments |
| `transcriber.py` | Manages a pool of persistent Whisper worker processes |
| `transcriber_worker.py` | Whisper worker process entry point |
| `command_parser.py` | Parses transcribed text into device commands |
| `esp32_client.py` | Sends HTTP commands to the ESP32 |
| `config.py` | Central configuration; endpoints/prompt auto-generate from `command_parser.py` |

## Known Limitations

- The ESP32 uses DHCP, not a static IP — `DEFAULT_ESP32_IP` needs a manual update if the lease changes.
- Fans are on/off only (no speed control).
- Recognition accuracy depends on mic quality and background noise.