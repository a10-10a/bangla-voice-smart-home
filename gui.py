import sounddevice as sd
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QPlainTextEdit,
)

from engine import VoiceEngine

BUILTIN_NAME_HINT = "smart sound technology for digital microphones"

_STATUS_COLORS = {
    "idle": "#555555",
    "busy": "#b06000",
    "ok": "#1e7e34",
    "error": "#c0392b",
}


def _list_relevant_mics():
    devices = sd.query_devices()
    default_input_index = sd.default.device[0]

    builtin_index = None
    for idx, dev in enumerate(devices):
        if dev.get("max_input_channels", 0) > 0 and BUILTIN_NAME_HINT in dev["name"].lower():
            builtin_index = idx
            break

    entries = []
    if builtin_index is not None:
        entries.append((f"Built-in: {devices[builtin_index]['name']}", builtin_index))

    if default_input_index is not None and default_input_index != builtin_index:
        default_dev = devices[default_input_index]
        if default_dev.get("max_input_channels", 0) > 0:
            entries.append((f"External: {default_dev['name']}", default_input_index))

    if not entries and default_input_index is not None:
        entries.append((devices[default_input_index]["name"], default_input_index))

    return entries


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bangla Voice Smart Home Controller")
        self.resize(520, 440)

        self.mic_combo = QComboBox()
        for label, idx in _list_relevant_mics():
            self.mic_combo.addItem(label, userData=idx)

        self.start_btn = QPushButton("Start Listening")
        self.stop_btn = QPushButton("Stop Listening")
        self.stop_btn.setEnabled(False)

        self.status_label = QLabel()
        self._set_status("Idle", "idle")

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Microphone:"))
        top_row.addWidget(self.mic_combo, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.stop_btn)

        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("Status:"))
        status_row.addWidget(self.status_label, stretch=1)

        layout = QVBoxLayout()
        layout.addLayout(top_row)
        layout.addLayout(btn_row)
        layout.addLayout(status_row)
        layout.addWidget(self.log_view)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.engine = None
        self.start_btn.clicked.connect(self._start)
        self.stop_btn.clicked.connect(self._stop)

    def _set_status(self, text: str, kind: str = "idle"):
        color = _STATUS_COLORS.get(kind, "#555555")
        self.status_label.setStyleSheet(f"font-weight: bold; color: {color};")
        self.status_label.setText(text)

    def _log(self, text: str):
        self.log_view.appendPlainText(text)

    def _start(self):
        mic_index = self.mic_combo.currentData()
        self.engine = VoiceEngine(mic_device=mic_index)
        self.engine.log_message.connect(self._log)
        self.engine.transcription_ready.connect(lambda t: self._log(f'INFO: Heard: "{t}"'))
        self.engine.status_changed.connect(self._set_status)
        self.engine.start_failed.connect(self._on_start_failed)
        self.engine.start()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.mic_combo.setEnabled(False)

    def _on_start_failed(self, reason: str):
        self.engine = None
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.mic_combo.setEnabled(True)

    def _stop(self):
        if self.engine is not None:
            self.engine.stop()
            self.engine = None
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.mic_combo.setEnabled(True)

    def closeEvent(self, event):
        self._stop()
        super().closeEvent(event)