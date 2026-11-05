"""@brief Verify an exact AV STOP at an explicitly captured host interface point."""

import ipaddress
import math
import subprocess
from pathlib import Path

from av_protocol import decode


def verify_stop(capture_path, packet, source_ip, *, tshark, runner=subprocess.run):
    """@brief Find the exact successfully sent STOP in a finalized capture.

    @param capture_path Finalized pcap/pcapng path.
    @param packet Exact AV STOP wire bytes, including its session and sequence.
    @param source_ip Concrete sender IPv4 address.
    @param tshark Installed Wireshark tshark executable path.
    @param runner Injectable subprocess runner for deterministic tests.
    @return Matching frame numbers/timestamps and interface-capture verification.
    @throws ValueError If the supplied packet/address or captured fields are invalid.
    @throws OSError If the executable or capture cannot be read.
    @throws subprocess.SubprocessError If capture inspection fails or times out.
    """
    parsed = decode(packet)
    if parsed.magic != b"MSC1" or parsed.kind != 4:
        raise ValueError("Expected an exact AV STOP packet")
    source = ipaddress.IPv4Address(source_ip)
    if source.is_unspecified:
        raise ValueError("STOP verification requires a concrete sender IPv4")
    result = runner(
        [
            str(tshark),
            "-n",
            "-r",
            str(Path(capture_path)),
            "-Y",
            f"ip.src == {source} && udp.payload == {packet.hex(':')}",
            "-T",
            "fields",
            "-e",
            "frame.number",
            "-e",
            "frame.time_epoch",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    packets = []
    for line in result.stdout.splitlines():
        number, stamp = line.split("\t")
        if int(number) <= 0 or not math.isfinite(float(stamp)) or float(stamp) <= 0:
            raise ValueError("Invalid captured STOP record")
        packets.append({"frame_number": int(number), "epoch_seconds": stamp})
    return {
        "stop_packet_verified": bool(packets),
        "stop_packets": packets,
        "scope": "Exact AV STOP at the captured interface; not RF delivery or receiver acknowledgement",
    }
