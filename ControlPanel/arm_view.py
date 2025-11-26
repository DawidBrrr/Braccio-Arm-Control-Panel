from __future__ import annotations

import math

from PyQt6 import QtCore, QtGui, QtWidgets

from config import ARM_LINKS_MM, SERVO_CONFIG, clamp
from kinematics import ArmKinematics


class ArmView(QtWidgets.QWidget):
    pose_changed = QtCore.pyqtSignal(dict)

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setMinimumHeight(500)
        self.setSizePolicy(
            QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        )
        self.setCursor(QtCore.Qt.CursorShape.CrossCursor)
        self._servo_values: dict[str, int] = {
            "m1": SERVO_CONFIG["m1"].initial,
            "m2": SERVO_CONFIG["m2"].initial,
            "m3": SERVO_CONFIG["m3"].initial,
            "m4": SERVO_CONFIG["m4"].initial,
            "m5": SERVO_CONFIG["m5"].initial,
        }
        self._drag_target: tuple[float, float] | None = None
        self._is_dragging = False
        self._active_joint: str | None = None
        self._last_drag_valid = True
        self._last_drag_point: QtCore.QPointF | None = None
        self._display_rotation = math.pi / 2  # rotate visualization so 90° aims upward

    def set_servo_value(self, servo_id: str, value: int) -> None:
        if servo_id in self._servo_values:
            self._servo_values[servo_id] = value
            self.update()

    def set_pose(self, pose: dict[str, int]) -> None:
        changed = False
        for key in ("m1", "m2", "m3", "m4", "m5"):
            if key in pose:
                if self._servo_values.get(key) != pose[key]:
                    changed = True
                self._servo_values[key] = pose[key]
        if changed:
            self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802 - Qt override
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor(16, 18, 26))

        origin, scale = self._origin_and_scale()
        self._draw_workspace(painter, origin, scale)
        self._draw_arm(painter, origin, scale)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            origin, scale = self._origin_and_scale()
            self._active_joint = self._pick_joint(event.position(), origin, scale)
            if self._active_joint is None:
                self._active_joint = "effector"
            self._is_dragging = True
            self.grabMouse()
            self._handle_drag(event.position())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self._is_dragging and event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            self._handle_drag(event.position())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self._is_dragging:
            self._is_dragging = False
            self._active_joint = None
            self._last_drag_point = None
            self.releaseMouse()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _origin_and_scale(self) -> tuple[QtCore.QPointF, float]:
        reach = ArmKinematics.max_reach()
        size = min(self.width(), self.height())
        scale = (0.85 * size) / reach if reach else 1.0
        origin = QtCore.QPointF(self.width() * 0.5, self.height() * 0.99)
        return origin, scale

    def _draw_workspace(self, painter: QtGui.QPainter, origin: QtCore.QPointF, scale: float) -> None:
        shoulder_len = ARM_LINKS_MM["shoulder"]
        elbow_len = ARM_LINKS_MM["elbow"]
        wrist_len = ARM_LINKS_MM["wrist"]

        painter.save()
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        self._fill_workspace_band(
            painter,
            origin,
            scale,
            max(abs(shoulder_len - elbow_len) - wrist_len, 0.0),
            ArmKinematics.max_reach(),
            QtGui.QColor(40, 110, 90, 28),
        )
        self._fill_workspace_band(
            painter,
            origin,
            scale,
            abs(shoulder_len - elbow_len),
            shoulder_len + elbow_len,
            QtGui.QColor(120, 120, 40, 25),
        )
        painter.restore()

        pen = QtGui.QPen(QtGui.QColor(70, 80, 100))
        pen.setStyle(QtCore.Qt.PenStyle.DashLine)
        painter.setPen(pen)
        radius = ArmKinematics.max_reach() * scale
        rect = QtCore.QRectF(
            origin.x() - radius,
            origin.y() - radius,
            radius * 2,
            radius * 2,
        )
        painter.drawArc(rect, 0, 180 * 16)

        shoulder_radius = shoulder_len * scale
        shoulder_rect = QtCore.QRectF(
            origin.x() - shoulder_radius,
            origin.y() - shoulder_radius,
            shoulder_radius * 2,
            shoulder_radius * 2,
        )
        painter.drawArc(shoulder_rect, 0, 180 * 16)

        base_rect = QtCore.QRectF(origin.x() - 20, origin.y() - 15, 40, 30)
        painter.setBrush(QtGui.QColor(30, 34, 48))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.drawRoundedRect(base_rect, 6, 6)

        painter.setPen(QtGui.QPen(QtGui.QColor(120, 180, 255), 2))
        base_angle = math.radians(self._servo_values["m1"] - 135)
        line = QtCore.QLineF(
            origin,
            QtCore.QPointF(
                origin.x() + 55 * math.cos(base_angle),
                origin.y() - 55 * math.sin(base_angle),
            ),
        )
        painter.drawLine(line)

        effector = self._current_effector(origin, scale)
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 80, 80), 2))
        painter.setBrush(QtGui.QColor(255, 80, 80, 120))
        painter.drawEllipse(effector, 8, 8)

        if self._last_drag_point is not None:
            color = QtGui.QColor(90, 200, 140, 140) if self._last_drag_valid else QtGui.QColor(230, 120, 120, 160)
            painter.setPen(QtGui.QPen(color.darker(), 1))
            painter.setBrush(color)
            painter.drawEllipse(self._last_drag_point, 6, 6)

    def _draw_arm(self, painter: QtGui.QPainter, origin: QtCore.QPointF, scale: float) -> None:
        screen_points = self._arm_screen_points(origin, scale)

        painter.setPen(QtGui.QPen(QtGui.QColor(64, 132, 214), 6))
        for start, end in zip(screen_points[:-1], screen_points[1:]):
            painter.drawLine(QtCore.QLineF(start, end))

        painter.setBrush(QtGui.QColor(240, 248, 255))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        for point in screen_points:
            painter.drawEllipse(point, 6, 6)

        wrist_handle = self._wrist_handle_point(origin, scale)
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 196, 120), 2, QtCore.Qt.PenStyle.DotLine))
        painter.drawLine(screen_points[-1], wrist_handle)
        painter.setBrush(QtGui.QColor(255, 196, 120, 200))
        painter.drawEllipse(wrist_handle, 7, 7)

    def _arm_screen_points(self, origin: QtCore.QPointF, scale: float) -> list[QtCore.QPointF]:
        points = ArmKinematics.forward(
            self._servo_values["m2"],
            self._servo_values["m3"],
            self._servo_values["m5"],
        )
        rotated_points = [self._rotate_point(pt, self._display_rotation) for pt in points]
        return [self._to_screen(pt, origin, scale) for pt in rotated_points]

    def _screen_to_plane(self, pos: QtCore.QPointF, origin: QtCore.QPointF, scale: float) -> tuple[float, float]:
        x_disp = (pos.x() - origin.x()) / scale
        z_disp = (origin.y() - pos.y()) / scale
        return self._rotate_point((x_disp, z_disp), -self._display_rotation)

    def _current_tool_angle(self) -> float:
        shoulder_angle = math.radians(self._servo_values["m2"] - 90)
        elbow_deflection = math.radians(self._servo_values["m3"] - 90)
        wrist_deflection = math.radians(self._servo_values["m5"] - 90)
        return shoulder_angle + elbow_deflection + wrist_deflection

    def _wrist_handle_point(self, origin: QtCore.QPointF, scale: float) -> QtCore.QPointF:
        points = ArmKinematics.forward(
            self._servo_values["m2"],
            self._servo_values["m3"],
            self._servo_values["m5"],
        )
        effector = points[-1]
        handle_length = ARM_LINKS_MM["wrist"] * 0.5
        angle = self._current_tool_angle()
        handle_point = (
            effector[0] + handle_length * math.cos(angle),
            effector[1] + handle_length * math.sin(angle),
        )
        rotated = self._rotate_point(handle_point, self._display_rotation)
        return self._to_screen(rotated, origin, scale)

    def _to_screen(self, point: tuple[float, float], origin: QtCore.QPointF, scale: float) -> QtCore.QPointF:
        return QtCore.QPointF(origin.x() + point[0] * scale, origin.y() - point[1] * scale)

    def _fill_workspace_band(
        self,
        painter: QtGui.QPainter,
        origin: QtCore.QPointF,
        scale: float,
        inner_radius: float,
        outer_radius: float,
        color: QtGui.QColor,
    ) -> None:
        outer = outer_radius * scale
        inner = inner_radius * scale
        if outer <= inner:
            return
        outer_rect = QtCore.QRectF(origin.x() - outer, origin.y() - outer, outer * 2, outer * 2)
        inner_rect = QtCore.QRectF(origin.x() - inner, origin.y() - inner, inner * 2, inner * 2)

        path = QtGui.QPainterPath()
        path.moveTo(origin.x() + outer, origin.y())
        path.arcTo(outer_rect, 0, 180)
        path.lineTo(origin.x() - inner, origin.y())
        path.arcTo(inner_rect, 180, -180)
        path.closeSubpath()
        painter.fillPath(path, color)

    def _pick_joint(self, pos: QtCore.QPointF, origin: QtCore.QPointF, scale: float) -> str | None:
        screen_points = self._arm_screen_points(origin, scale)
        wrist_handle = self._wrist_handle_point(origin, scale)
        joints = {
            "base": origin,
            "shoulder": screen_points[1],
            "elbow": screen_points[2],
            "wrist": wrist_handle,
            "effector": screen_points[3],
        }
        threshold = {
            "base": 36.0,
            "shoulder": 26.0,
            "elbow": 26.0,
            "wrist": 24.0,
            "effector": 30.0,
        }
        closest = None
        best = float("inf")
        for name, point in joints.items():
            dist = QtCore.QLineF(point, pos).length()
            limit = threshold[name]
            if dist <= limit and dist < best:
                closest = name
                best = dist
        return closest

    def _handle_drag(self, pos: QtCore.QPointF) -> None:
        if self._active_joint is None:
            self._active_joint = "effector"

        origin, scale = self._origin_and_scale()
        self._last_drag_point = QtCore.QPointF(pos)
        solution: dict[str, int] | None = None
        within_limits = True

        if self._active_joint == "base":
            dx = pos.x() - origin.x()
            dy = origin.y() - pos.y()
            if math.isclose(dx, 0.0, abs_tol=1e-4) and math.isclose(dy, 0.0, abs_tol=1e-4):
                return
            angle = math.degrees(math.atan2(dy, dx))
            m1_value = int(round(angle + 135))
            m1_value = int(clamp(m1_value, SERVO_CONFIG["m1"].minimum, SERVO_CONFIG["m1"].maximum))
            solution = {"m1": m1_value}
        else:
            x, z = self._screen_to_plane(pos, origin, scale)
            if self._active_joint == "shoulder":
                result = ArmKinematics.solve_shoulder(x, z)
                if result is None:
                    return
                solution, within_limits = result
            elif self._active_joint == "elbow":
                result = ArmKinematics.solve_elbow(x, z)
                if result is None:
                    return
                solution, within_limits = result
            elif self._active_joint == "wrist":
                rotation_solution = self._solve_wrist_rotation(x, z)
                if rotation_solution is None:
                    return
                solution = rotation_solution
                within_limits = True
            else:  # effector
                tool_angle = self._current_tool_angle()
                result = ArmKinematics.solve_inverse(x, z, tool_angle)
                if result is None:
                    return
                solution, within_limits = result
                self._drag_target = (x, z)

        self._last_drag_valid = within_limits
        self.pose_changed.emit(solution)
        self.update()

    def _current_effector(self, origin: QtCore.QPointF, scale: float) -> QtCore.QPointF:
        points = ArmKinematics.forward(
            self._servo_values["m2"],
            self._servo_values["m3"],
            self._servo_values["m5"],
        )
        effector = self._rotate_point(points[-1], self._display_rotation)
        return self._to_screen(effector, origin, scale)

    @staticmethod
    def _rotate_point(point: tuple[float, float], angle: float) -> tuple[float, float]:
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        x, y = point
        return (x * cos_a - y * sin_a, x * sin_a + y * cos_a)

    def _solve_wrist_rotation(self, target_x: float, target_z: float) -> dict[str, int] | None:
        points = ArmKinematics.forward(
            self._servo_values["m2"],
            self._servo_values["m3"],
            self._servo_values["m5"],
        )
        wrist_joint = points[-2]
        vec_x = target_x - wrist_joint[0]
        vec_z = target_z - wrist_joint[1]
        if math.hypot(vec_x, vec_z) < 1e-4:
            return None
        phi_target = math.atan2(vec_z, vec_x)

        shoulder_angle = math.radians(self._servo_values["m2"] - 90)
        elbow_deflection = math.radians(self._servo_values["m3"] - 90)
        forearm_angle = shoulder_angle + elbow_deflection
        wrist_relative = phi_target - forearm_angle

        m5_value = int(round(math.degrees(wrist_relative) + 90))
        if not (SERVO_CONFIG["m5"].minimum <= m5_value <= SERVO_CONFIG["m5"].maximum):
            return None
        return {"m5": int(clamp(m5_value, SERVO_CONFIG["m5"].minimum, SERVO_CONFIG["m5"].maximum))}
