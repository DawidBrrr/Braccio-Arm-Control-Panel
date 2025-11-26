from __future__ import annotations

import math

from config import ARM_LINKS_MM, SERVO_CONFIG, clamp


class ArmKinematics:
    """Planar 3-link model used for visualization and dragging."""

    @classmethod
    def max_reach(cls) -> float:
        return ARM_LINKS_MM["shoulder"] + ARM_LINKS_MM["elbow"] + ARM_LINKS_MM["wrist"]

    @classmethod
    def forward(cls, m2: int, m3: int, m5: int) -> list[tuple[float, float]]:
        base = (0.0, 0.0)
        shoulder_angle = math.radians(m2 - 90)
        elbow_deflection = math.radians(m3 - 90)
        forearm_angle = shoulder_angle + elbow_deflection
        wrist_deflection = math.radians(m5 - 90)
        end_angle = forearm_angle + wrist_deflection

        p1 = (
            ARM_LINKS_MM["shoulder"] * math.cos(shoulder_angle),
            ARM_LINKS_MM["shoulder"] * math.sin(shoulder_angle),
        )
        p2 = (
            p1[0] + ARM_LINKS_MM["elbow"] * math.cos(forearm_angle),
            p1[1] + ARM_LINKS_MM["elbow"] * math.sin(forearm_angle),
        )
        p3 = (
            p2[0] + ARM_LINKS_MM["wrist"] * math.cos(end_angle),
            p2[1] + ARM_LINKS_MM["wrist"] * math.sin(end_angle),
        )
        return [base, p1, p2, p3]

    @classmethod
    def solve_inverse(cls, x: float, z: float, phi: float = -math.pi / 2) -> tuple[dict[str, int], bool] | None:
        wrist_offset = (
            ARM_LINKS_MM["wrist"] * math.cos(phi),
            ARM_LINKS_MM["wrist"] * math.sin(phi),
        )
        wx = x - wrist_offset[0]
        wz = z - wrist_offset[1]

        original_dist = math.hypot(wx, wz)
        if original_dist == 0:
            return None
        max_reach = ARM_LINKS_MM["shoulder"] + ARM_LINKS_MM["elbow"] - 1.0
        min_reach = abs(ARM_LINKS_MM["shoulder"] - ARM_LINKS_MM["elbow"]) + 1.0
        target_dist = clamp(original_dist, min_reach, max_reach)
        within_limits = math.isclose(target_dist, original_dist, rel_tol=0.0, abs_tol=1e-3)
        scale = target_dist / original_dist
        wx *= scale
        wz *= scale

        cos_elbow = clamp(
            (target_dist**2 - ARM_LINKS_MM["shoulder"]**2 - ARM_LINKS_MM["elbow"]**2)
            / (2 * ARM_LINKS_MM["shoulder"] * ARM_LINKS_MM["elbow"]),
            -1.0,
            1.0,
        )
        elbow_angle = math.acos(cos_elbow)

        shoulder_angle = math.atan2(wz, wx) - math.atan2(
            ARM_LINKS_MM["elbow"] * math.sin(elbow_angle),
            ARM_LINKS_MM["shoulder"] + ARM_LINKS_MM["elbow"] * math.cos(elbow_angle),
        )

        upper_vector = (
            ARM_LINKS_MM["shoulder"] * math.cos(shoulder_angle),
            ARM_LINKS_MM["shoulder"] * math.sin(shoulder_angle),
        )
        forearm_angle = math.atan2(wz - upper_vector[1], wx - upper_vector[0])
        elbow_deflection = forearm_angle - shoulder_angle
        wrist_relative = phi - forearm_angle

        m2 = int(round(math.degrees(shoulder_angle) + 90))
        m3 = int(round(math.degrees(elbow_deflection) + 90))
        m5 = int(round(math.degrees(wrist_relative) + 90))

        if not (SERVO_CONFIG["m2"].minimum <= m2 <= SERVO_CONFIG["m2"].maximum):
            return None
        if not (SERVO_CONFIG["m3"].minimum <= m3 <= SERVO_CONFIG["m3"].maximum):
            return None
        if not (SERVO_CONFIG["m5"].minimum <= m5 <= SERVO_CONFIG["m5"].maximum):
            return None

        return {"m2": m2, "m3": m3, "m5": m5}, within_limits

    @classmethod
    def solve_elbow(cls, x: float, z: float) -> tuple[dict[str, int], bool] | None:
        shoulder_len = ARM_LINKS_MM["shoulder"]
        elbow_len = ARM_LINKS_MM["elbow"]
        dist = math.hypot(x, z)
        if dist == 0:
            return None
        max_reach = shoulder_len + elbow_len
        min_reach = abs(shoulder_len - elbow_len)
        target_dist = clamp(dist, min_reach, max_reach)
        within_limits = math.isclose(target_dist, dist, rel_tol=0.0, abs_tol=1e-3)
        scale = target_dist / dist
        tx = x * scale
        tz = z * scale

        cos_elbow = clamp(
            (target_dist**2 - shoulder_len**2 - elbow_len**2) / (2 * shoulder_len * elbow_len),
            -1.0,
            1.0,
        )
        elbow_angle = math.acos(cos_elbow)
        shoulder_angle = math.atan2(tz, tx) - math.atan2(
            elbow_len * math.sin(elbow_angle),
            shoulder_len + elbow_len * math.cos(elbow_angle),
        )

        upper_vector = (
            shoulder_len * math.cos(shoulder_angle),
            shoulder_len * math.sin(shoulder_angle),
        )
        forearm_angle = math.atan2(tz - upper_vector[1], tx - upper_vector[0])
        elbow_deflection = forearm_angle - shoulder_angle

        m2 = int(round(math.degrees(shoulder_angle) + 90))
        m3 = int(round(math.degrees(elbow_deflection) + 90))

        if not (SERVO_CONFIG["m2"].minimum <= m2 <= SERVO_CONFIG["m2"].maximum):
            return None
        if not (SERVO_CONFIG["m3"].minimum <= m3 <= SERVO_CONFIG["m3"].maximum):
            return None

        return {"m2": m2, "m3": m3}, within_limits

    @classmethod
    def solve_shoulder(cls, x: float, z: float) -> tuple[dict[str, int], bool] | None:
        if math.isclose(x, 0.0, abs_tol=1e-4) and math.isclose(z, 0.0, abs_tol=1e-4):
            return None
        shoulder_len = ARM_LINKS_MM["shoulder"]
        dist = math.hypot(x, z)
        within_limits = math.isclose(dist, shoulder_len, rel_tol=0.0, abs_tol=5.0)
        angle = math.atan2(z, x)
        m2 = int(round(math.degrees(angle) + 90))
        if not (SERVO_CONFIG["m2"].minimum <= m2 <= SERVO_CONFIG["m2"].maximum):
            return None
        return {"m2": m2}, within_limits
