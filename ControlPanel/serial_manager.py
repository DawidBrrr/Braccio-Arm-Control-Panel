from __future__ import annotations

import threading
from typing import Callable

from PyQt6 import QtCore

try:
    import serial
    import serial.tools.list_ports
except ImportError:  # pragma: no cover - optional dependency
    serial = None  # type: ignore


class LogEmitter(QtCore.QObject):
    message = QtCore.pyqtSignal(str)


class SerialManager:
    """Thin wrapper around pySerial with a background reader."""

    def __init__(self, on_message: Callable[[str], None]):
        self.on_message = on_message
        self.serial_conn: serial.Serial | None = None  # type: ignore[assignment]
        self.reader_thread: threading.Thread | None = None
        self.reader_stop = threading.Event()

    def connect(self, port: str, baud: int) -> None:
        if serial is None:
            raise RuntimeError("pyserial is not installed. Run 'pip install pyserial'.")
        if self.serial_conn and self.serial_conn.is_open:
            self.disconnect()
        self.serial_conn = serial.Serial(port, baudrate=baud, timeout=0.1)
        self.reader_stop.clear()
        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_thread.start()

    def disconnect(self) -> None:
        self.reader_stop.set()
        if self.reader_thread:
            self.reader_thread.join(timeout=0.5)
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        self.serial_conn = None

    def send(self, payload: str) -> None:
        if not self.serial_conn or not self.serial_conn.is_open:
            raise RuntimeError("Serial port is not connected.")
        self.serial_conn.write(payload.encode("ascii"))

    def _reader_loop(self) -> None:
        assert self.serial_conn is not None
        while not self.reader_stop.is_set():
            try:
                line = self.serial_conn.readline()
            except serial.SerialException as exc:  # type: ignore[attr-defined]
                self.on_message(f"[Serial error] {exc}\n")
                break
            if line:
                try:
                    decoded = line.decode("utf-8", errors="replace")
                except Exception:
                    decoded = repr(line)
                self.on_message(decoded)
        self.on_message("[Serial] Reader stopped.\n")
