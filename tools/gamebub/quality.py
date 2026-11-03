"""@brief Conservative JPEG quality adaptation for the experimental host sender."""

import math


class QualityController:
    """@brief Lower quality quickly under pressure and recover only after sustained headroom.

    This controller uses the configured payload budget, not measured Wi-Fi
    throughput or physical receiver performance. Callers serialize access.
    """

    def __init__(self, initial, minimum, recovery_frames=30):
        """@brief Set JPEG quality bounds and the required consecutive headroom frames.

        @param initial Initial and maximum JPEG quality, 1..95.
        @param minimum Lowest allowed JPEG quality.
        @param recovery_frames Consecutive headroom observations needed to increase by one.
        """
        if (
            type(initial) is not int
            or type(minimum) is not int
            or type(recovery_frames) is not int
            or not 1 <= minimum <= initial <= 95
            or recovery_frames <= 0
        ):
            raise ValueError("Invalid JPEG quality bounds or recovery interval")
        self.minimum = minimum
        self.maximum = self.value = initial
        self.recovery_frames = recovery_frames
        self.headroom_frames = 0

    def congested(self):
        """@brief Reduce quality by five and discard accumulated recovery credit.

        @return Updated bounded JPEG quality.
        """
        self.headroom_frames = 0
        self.value = max(self.minimum, self.value - 5)
        return self.value

    def observe(self, wire_bytes, budget_bytes, may_recover):
        """@brief Update quality from encoded frame size and feedback availability.

        @param wire_bytes Positive MSV1 frame bytes including chunk headers.
        @param budget_bytes Positive per-frame MSV1 byte budget.
        @param may_recover True only while recent matching feedback is available.
        @return Updated bounded JPEG quality.
        """
        if (
            type(wire_bytes) is not int
            or wire_bytes <= 0
            or type(budget_bytes) not in (int, float)
            or not math.isfinite(budget_bytes)
            or budget_bytes <= 0
            or type(may_recover) is not bool
        ):
            raise ValueError("Invalid size, budget, or feedback status")
        if wire_bytes > budget_bytes * 0.9:
            return self.congested()
        if not may_recover or wire_bytes >= budget_bytes * 0.7:
            self.headroom_frames = 0
            return self.value
        self.headroom_frames += 1
        if self.headroom_frames >= self.recovery_frames:
            self.value = min(self.maximum, self.value + 1)
            self.headroom_frames = 0
        return self.value
