"""@brief Finite local-contract AV v1 session; no traffic or capture on import."""

import queue
import socket
import time

from av_protocol import BLOCK_SAMPLES, KEEP_NS, LEASE_NS, RATE, decode
from av_session import AvSession
from gamepad_backend import GamepadDispatcher, VigemXbox360Backend
from live_audio import LoopbackAudio
from realtime import GAMEBUB_GAMEPAD_FLAGS

BUTTON_NAMES = ("select", "start", "r", "l", "right", "left", "down", "up", "y", "x", "b", "a")


class ProfileSink:
    """@brief Adapt the tested session's digital flags back to a profile's raw mask."""

    def __init__(self, dispatcher=None):
        """@brief Request fresh held snapshots for WoW acceleration; observation uses no device."""
        self.dispatcher = dispatcher
        self.repeat_buttons = getattr(dispatcher, "profile", None) == "wow"

    def set_buttons(self, flags):
        """@brief Preserve all twelve buttons through digital flags and profile dispatch."""
        mask = sum(
            1 << bit for bit, name in enumerate(BUTTON_NAMES) if flags & GAMEBUB_GAMEPAD_FLAGS[name]
        )
        if self.dispatcher is not None:
            self.dispatcher.apply(mask)


def handshake(session, sock, peer, clock, timeout=5):
    """@brief Retry HELLO/START with a finite deadline until fresh ACTIVE input arrives."""
    deadline, next_send = clock() + int(timeout * 1e9), 0
    while clock() < deadline:
        now = clock()
        if now >= next_send:
            sock.send(session.hello(now) if session.state == "hello" else session.start(now))
            next_send = now + KEEP_NS
        try:
            raw, source = sock.recvfrom(561)
        except TimeoutError:
            continue
        try:
            if session.state == "hello":
                if session.offer(raw, source, clock()):
                    next_send = 0
            elif session.receive_input(raw, source, clock()):
                return
        except ValueError:
            continue
    raise TimeoutError(f"No active AV handshake with{peer}; check source filter/UDP5534")


def run_av(
    args,
    event,
    ready=lambda: None,
    clock=time.perf_counter_ns,
    socket_factory=socket.socket,
    audio_factory=LoopbackAudio,
    health=lambda: None,
    stop_when=lambda: False,
):
    """@brief Run one AV owner with independent input lease and bounded audio pacing.

    @param args Validated launcher options including duration, addresses and profile.
    @param event Structured logger, accepting event kind and named fields.
    @param ready Called after ACTIVE, before starting the finite session clock.
    @param health Optional nonblocking owned-video health check at each loop iteration.
    @param stop_when Optional nonblocking completion predicate; STOP follows completion.
    @return Counters with snapshot validity preserved; no end-to-end playback claim.
    """
    dispatcher = audio = session = sock = None
    counts = {
        "input_packets": 0,
        "invalid_packets": 0,
        "stale_packets": 0,
        "input_timeouts": 0,
        "audio_sent": 0,
        "audio_stale": 0,
        "source_inactive_events": 0,
    }
    summary = counts.copy()
    try:
        if args.gamepad:
            dispatcher = GamepadDispatcher(VigemXbox360Backend.create(), args.profile)
        health()
        peer = socket.gethostbyname(args.receiver), args.av_port
        session = AvSession(peer, ProfileSink(dispatcher), audio=args.audio)
        sock = socket_factory(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((args.bind, args.av_source_port))
        sock.connect(peer)
        sock.settimeout(0.005)
        event("socket", local=sock.getsockname(), peer=peer)
        handshake(session, sock, peer, clock)
        health()
        event("active", session=f"{session.cookie:016x}", audio=args.audio, profile=args.profile)
        ready()
        started = clock()
        if args.audio:
            audio = audio_factory(args.gain, clock=clock)
            audio.start()
        next_audio, inactive = started, False
        period = round(BLOCK_SAMPLES * 1e9 / RATE)
        while clock() - started < args.seconds * 1e9:
            health()
            if stop_when():
                break
            now = clock()
            keep = session.keepalive(now)
            if keep is not None:
                sock.send(keep)
            if audio is not None:
                if audio.error:
                    raise RuntimeError(audio.error)
                last = audio.last_capture_ns if audio.last_capture_ns is not None else started
                missing = now - last > args.source_timeout * 1e9
                if missing != inactive:
                    event(
                        "audio_source_inactive" if missing else "audio_source_resumed",
                        age_ms=(now - last) / 1e6,
                    )
                    counts["source_inactive_events"] += int(missing)
                    inactive = missing
                if now >= next_audio:
                    try:
                        sequence, stamp, block = audio.blocks.get_nowait()
                    except queue.Empty:
                        pass
                    else:
                        if now - stamp > 80_000_000:
                            counts["audio_stale"] += 1
                            event(
                                "audio_drop",
                                sequence=sequence,
                                reason="stale",
                                age_ms=(now - stamp) / 1e6,
                            )
                        else:
                            # Sequence belongs to every encoded block, including queue evictions.
                            session.audio_sequence = sequence
                            packet = session.prepare_audio(block, now)
                            sock.send(packet)
                            counts["audio_sent"] += 1
                            event(
                                "audio_send",
                                sequence=sequence,
                                bytes=len(packet),
                                age_ms=(now - stamp) / 1e6,
                            )
                            next_audio = max(next_audio + period, now - period)
            try:
                raw, source = sock.recvfrom(561)
            except TimeoutError:
                pass
            else:
                try:
                    accepted = session.receive_input(raw, source, clock())
                except ValueError:
                    counts["invalid_packets"] += 1
                else:
                    if accepted:
                        counts["input_packets"] += 1
                        event("input", sequence=session.input.sequence, **session.status)
                    else:
                        counts["stale_packets"] += 1
            now = clock()
            session.expire_input(now)
            if now - session.input.last_ns >= LEASE_NS:
                counts["input_timeouts"] += 1
                raise TimeoutError("No newer MSI1 for500ms; input neutralized")
        summary.update(counts)
    finally:
        summary.update(counts)
        summary["last_status"] = session.status if session is not None else None
        summary["stop_sent"] = False
        cleanup_errors = []
        if session is not None:
            try:
                packet = session.stop(clock())
                if packet is not None and sock is not None:
                    if sock.send(packet) != len(packet):
                        raise OSError("Partial AV STOP datagram send")
                    summary["stop_sent"] = True
                    event(
                        "stop_sent",
                        sequence=decode(packet).sequence,
                        bytes=len(packet),
                        wire_hex=packet.hex(),
                    )
            except (OSError, RuntimeError, ValueError) as error:
                summary["stop_error"] = str(error)
            finally:
                try:
                    session.close()
                except OSError as error:
                    cleanup_errors.append(f"session:{error}")
        for name, resource in (("socket", sock), ("controller", dispatcher)):
            if resource is not None:
                try:
                    resource.close()
                except OSError as error:
                    cleanup_errors.append(f"{name}:{error}")
        if audio is not None:
            summary["audio_worker"] = audio.close()
        summary["cleanup_errors"] = cleanup_errors
        event("av_summary", **summary)
    return summary
