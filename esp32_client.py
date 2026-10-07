"""Fire-and-forget HTTP dispatch to the ESP32, off the audio/transcription threads."""

from concurrent.futures import ThreadPoolExecutor
import requests

import config


class ESP32Client:
    def __init__(self, ip: str):
        self._ip = ip
        self._session = requests.Session()
        self._executor = ThreadPoolExecutor(max_workers=4)

    def set_ip(self, ip: str):
        self._ip = ip

    def _do_request(self, device_id, action, on_result):
        path = config.ENDPOINTS.get((device_id, action))
        if path is None:
            on_result(False, "no matching ESP32 endpoint configured")
            return
        url = f"http://{self._ip}{path}"
        try:
            resp = self._session.get(url, timeout=config.HTTP_TIMEOUT_S)
            on_result(resp.status_code == 200, f"HTTP {resp.status_code}")
        except requests.RequestException as exc:
            on_result(False, str(exc))

    def send_command(self, device_id: str, action: str, on_result):
        self._executor.submit(self._do_request, device_id, action, on_result)