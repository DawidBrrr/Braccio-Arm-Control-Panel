from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets

from arm_view import ArmView
from config import BAUD_RATE, DEFAULT_PORT, SERVO_CONFIG, SLIDER_DEBOUNCE_MS
from serial_manager import LogEmitter, SerialManager
from widgets import ServoSlider

try:
    from serial.tools import list_ports
except ImportError:  # pragma: no cover - optional dependency
    list_ports = None  # type: ignore


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Braccio Controller")
        self.resize(960, 640)

        self.log_emitter = LogEmitter()
        self.log_emitter.message.connect(self._append_log)
        self.serial_manager = SerialManager(self.log_emitter.message.emit)
        self.slider_timers: dict[str, QtCore.QTimer] = {}
        self._syncing_from_canvas = False

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(16)

        main_layout.addLayout(self._build_connection_bar())
        main_layout.addLayout(self._build_sliders_grid())
        self.arm_view = ArmView()
        self.arm_view.pose_changed.connect(self._apply_canvas_pose)
        main_layout.addWidget(self.arm_view, stretch=2)
        main_layout.addLayout(self._build_actions_row())
        main_layout.addWidget(self._build_log_panel(), stretch=1)

        self.arm_view.set_pose(self._current_servo_values())

    def _build_connection_bar(self) -> QtWidgets.QHBoxLayout:
        layout = QtWidgets.QHBoxLayout()
        layout.setSpacing(12)

        self.port_combo = QtWidgets.QComboBox()
        self.port_combo.setEditable(True)
        self.port_combo.setMinimumWidth(120)
        layout.addWidget(QtWidgets.QLabel("Port"))
        layout.addWidget(self.port_combo)

        self.baud_edit = QtWidgets.QLineEdit(str(BAUD_RATE))
        self.baud_edit.setValidator(QtGui.QIntValidator(1, 1_000_000, self))
        self.baud_edit.setMaximumWidth(120)
        layout.addWidget(QtWidgets.QLabel("Baud"))
        layout.addWidget(self.baud_edit)

        self.connect_btn = QtWidgets.QPushButton("Connect")
        self.connect_btn.clicked.connect(self.toggle_connection)
        layout.addWidget(self.connect_btn)

        layout.addStretch()

        self.status_label = QtWidgets.QLabel("Disconnected")
        self.status_label.setObjectName("status-label")
        layout.addWidget(self.status_label)

        self._refresh_ports()
        return layout

    def _build_sliders_grid(self) -> QtWidgets.QGridLayout:
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(12)
        self.servos: dict[str, ServoSlider] = {}

        for idx, (servo_id, cfg) in enumerate(SERVO_CONFIG.items()):
            slider = ServoSlider(servo_id, cfg)
            slider.value_changed.connect(self._handle_servo_change)
            row, col = divmod(idx, 3)
            grid.addWidget(slider, row, col)
            self.servos[servo_id] = slider

        return grid

    def _build_actions_row(self) -> QtWidgets.QHBoxLayout:
        layout = QtWidgets.QHBoxLayout()
        layout.setSpacing(12)

        self.send_all_btn = QtWidgets.QPushButton("Send All")
        self.send_all_btn.clicked.connect(self.send_all)
        layout.addWidget(self.send_all_btn)

        self.reset_btn = QtWidgets.QPushButton("Reset Pose")
        self.reset_btn.clicked.connect(self.reset_positions)
        layout.addWidget(self.reset_btn)

        layout.addStretch()
        return layout

    def _build_log_panel(self) -> QtWidgets.QTextEdit:
        self.log_view = QtWidgets.QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.NoWrap)
        self.log_view.setPlaceholderText("Serial monitor output will appear here...")
        self.log_view.document().setDefaultFont(QtGui.QFont("Consolas", 10))
        return self.log_view

    def _refresh_ports(self) -> None:
        ports: list[str] = []
        if list_ports is not None:
            ports = [p.device for p in list_ports.comports()]
        if DEFAULT_PORT not in ports:
            ports.insert(0, DEFAULT_PORT)
        self.port_combo.clear()
        self.port_combo.addItems(ports)
        self.port_combo.setCurrentText(DEFAULT_PORT)

    def toggle_connection(self) -> None:
        if self.connect_btn.text() == "Connect":
            self._connect()
        else:
            self._disconnect()

    def _connect(self) -> None:
        port = self.port_combo.currentText().strip()
        if not port:
            self._error("Please provide a serial port (e.g. COM3).")
            return
        baud_text = self.baud_edit.text().strip()
        baud = int(baud_text or BAUD_RATE)

        try:
            self.serial_manager.connect(port, baud)
        except Exception as exc:  # pragma: no cover - UI feedback only
            self._error(f"Failed to connect: {exc}")
            return

        self.status_label.setText(f"Connected to {port}")
        self.connect_btn.setText("Disconnect")
        self._append_log(f"[Serial] Connected to {port} @ {baud}\n")

    def _disconnect(self) -> None:
        self.serial_manager.disconnect()
        self.status_label.setText("Disconnected")
        self.connect_btn.setText("Connect")
        self._append_log("[Serial] Disconnected.\n")

    def _handle_servo_change(self, servo_id: str, value: int) -> None:
        self.arm_view.set_servo_value(servo_id, value)
        if not self._syncing_from_canvas:
            self._queue_servo_send(servo_id)

    def _queue_servo_send(self, servo_id: str) -> None:
        timer = self.slider_timers.get(servo_id)
        if timer is None:
            timer = QtCore.QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda s=servo_id: self._send_servo_value(s))
            self.slider_timers[servo_id] = timer
        timer.start(SLIDER_DEBOUNCE_MS)

    def _send_servo_value(self, servo_id: str) -> None:
        slider = self.servos[servo_id]
        value = slider.current_value()
        command = f"{servo_id}:{value}\n"
        self._transmit(command)

    def send_all(self) -> None:
        payload = ";".join(f"{sid}:{slider.current_value()}" for sid, slider in self.servos.items()) + "\n"
        self._transmit(payload)

    def _send_pose_fragment(self, pose: dict[str, int]) -> None:
        parts = [f"{sid}:{self.servos[sid].current_value()}" for sid in pose if sid in self.servos]
        if not parts:
            return
        self._transmit(";".join(parts) + "\n")

    def reset_positions(self) -> None:
        for servo_id, cfg in SERVO_CONFIG.items():
            self.servos[servo_id].set_value(cfg.initial)
        self.arm_view.set_pose(self._current_servo_values())
        self.send_all()

    def _transmit(self, payload: str) -> None:
        try:
            self.serial_manager.send(payload)
            self._append_log(f"-> {payload}")
        except Exception as exc:
            self._append_log(f"[Send failed] {exc}\n")

    def _apply_canvas_pose(self, pose: dict[str, int]) -> None:
        self._syncing_from_canvas = True
        try:
            for servo_id, value in pose.items():
                if servo_id in self.servos:
                    self.servos[servo_id].set_value(value, emit=True)
        finally:
            self._syncing_from_canvas = False
        self._send_pose_fragment(pose)

    def _current_servo_values(self) -> dict[str, int]:
        return {sid: slider.current_value() for sid, slider in self.servos.items()}

    def _append_log(self, text: str) -> None:
        self.log_view.moveCursor(QtGui.QTextCursor.MoveOperation.End)
        self.log_view.insertPlainText(text)
        self.log_view.moveCursor(QtGui.QTextCursor.MoveOperation.End)

    def _error(self, message: str) -> None:
        QtWidgets.QMessageBox.critical(self, "Braccio Controller", message)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802 (Qt override)
        self._disconnect()
        super().closeEvent(event)
