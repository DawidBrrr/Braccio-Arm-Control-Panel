from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from config import ServoConfig


class ServoSlider(QtWidgets.QGroupBox):
    value_changed = QtCore.pyqtSignal(str, int)

    def __init__(self, servo_id: str, cfg: ServoConfig, parent: QtWidgets.QWidget | None = None):
        super().__init__(f"{cfg.label} ({servo_id.upper()})", parent)
        self.servo_id = servo_id
        self.cfg = cfg

        layout = QtWidgets.QVBoxLayout(self)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider.setRange(cfg.minimum, cfg.maximum)
        self.slider.setValue(cfg.initial)
        self.slider.setTickInterval(5)
        self.slider.setTickPosition(QtWidgets.QSlider.TickPosition.TicksBelow)
        self.slider.valueChanged.connect(self._on_value_changed)

        self.value_label = QtWidgets.QLabel(str(cfg.initial))
        self.value_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.value_label.setObjectName("value-label")

        layout.addWidget(self.slider)
        layout.addWidget(self.value_label)

    def _on_value_changed(self, value: int) -> None:
        self.value_label.setText(str(value))
        self.value_changed.emit(self.servo_id, value)

    def set_value(self, value: int, emit: bool = False) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(value)
        self.slider.blockSignals(False)
        self.value_label.setText(str(value))
        if emit:
            self.value_changed.emit(self.servo_id, value)

    def current_value(self) -> int:
        return self.slider.value()
