"""Optional normalized per-frame telemetry for offline correlation."""


class FrameTelemetry:
    """Write bounded capture and completed-send records to an EventLog sink.

    Timestamps are host monotonic nanoseconds. The capture wall timestamp is
    retained only as separate metadata; it is never used for duration math.
    A completed send means the local sender finished packet submission, not
    receiver ingress, decode, or presentation.
    """

    def __init__(self, sink, session_id, evidence_kind="simulated"):
        self.validate_configuration(session_id, evidence_kind)
        self.sink = sink
        self.session_id = session_id
        self.evidence_kind = evidence_kind

    @staticmethod
    def validate_configuration(session_id, evidence_kind):
        """Validate immutable run labels before starting any logging worker."""
        if type(session_id) is not str or not session_id or len(session_id) > 128:
            raise ValueError("Telemetry session ID must contain 1..128 characters")
        if evidence_kind not in ("hardware", "simulated"):
            raise ValueError("Telemetry evidence kind must be hardware or simulated")

    def _base(self, frame, stage, timestamp_ns):
        if (
            type(frame.frame_seq) is not int or frame.frame_seq < 0
            or type(frame.frame_id) is not int or not 0 <= frame.frame_id <= 0xFFFFFFFF
            or type(timestamp_ns) is not int or timestamp_ns < 0
        ):
            raise ValueError("Invalid frame telemetry identity or timestamp")
        return {
            "session_id": self.session_id,
            "frame_seq": frame.frame_seq,
            "frame_id": frame.frame_id,
            "stage": stage,
            "clock_domain": "host_monotonic",
            "timestamp_ns": timestamp_ns,
            "evidence_kind": self.evidence_kind,
        }

    def capture(self, frame, capture_wall_us):
        """Record capture start as normalized timestamp plus end and wall metadata."""
        if type(frame.captured_ns) is not int or frame.captured_ns < 0:
            raise ValueError("Invalid monotonic capture start")
        if type(frame.capture_end_ns) is not int or frame.capture_end_ns < frame.captured_ns:
            raise ValueError("Invalid monotonic capture end")
        if type(capture_wall_us) is not int or capture_wall_us < 0:
            raise ValueError("Invalid capture wall timestamp")
        if capture_wall_us != frame.capture_us:
            raise ValueError("Capture wall timestamp must match the frame's wire timestamp")
        event = self._base(frame, "capture", frame.captured_ns)
        event.update({
            "capture_start_ns": frame.captured_ns,
            "capture_end_ns": frame.capture_end_ns,
            "capture_wall_us": capture_wall_us,
        })
        return self.sink.submit(event)

    def send_complete(self, frame, timestamp_ns, wire_bytes=None):
        """Record local completion after every frame datagram was submitted."""
        event = self._base(frame, "send", timestamp_ns)
        event["send_complete_ns"] = timestamp_ns
        if wire_bytes is not None:
            if type(wire_bytes) is not int or wire_bytes <= 0:
                raise ValueError("Wire byte count must be a positive integer")
            event["wire_bytes"] = wire_bytes
        return self.sink.submit(event)
