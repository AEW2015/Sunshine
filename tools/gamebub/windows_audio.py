"""@brief Probe/capture Windows speaker loopback without changing output devices.

This prepares PCM locally; no network audio format is selected or transmitted.
"""

import argparse
import array
import json
import math
import struct
import sys
import time
import wave
from pathlib import Path


def pcm_stats(payload):
    """@brief Measure little-endian signed 16-bit PCM, including silence.

    @param payload Complete PCM samples in little-endian byte order.
    @return Sample count, peak magnitude and RMS amplitude.
    """
    if not isinstance(payload, bytes) or len(payload) % 2:
        raise ValueError("Expected complete signed 16-bit PCM samples")
    values = array.array("h", payload)
    if sys.byteorder != "little":
        values.byteswap()
    return {
        "samples": len(values),
        "peak": max((abs(x) for x in values), default=0),
        "rms": math.sqrt(sum(x * x for x in values) / len(values)) if values else 0.0,
    }


def test_tone(frames=480, rate=48000):
    """@brief Produce deterministic stereo PCM with distinct left/right tones.

    @param frames Positive number of interleaved stereo sample frames.
    @param rate Positive sample rate in samples per second per channel.
    @return Signed little-endian 16-bit stereo PCM at modest amplitude.
    """
    if type(frames) is not int or not 1 <= frames <= 480000:
        raise ValueError("Invalid tone length")
    if type(rate) is not int or not 8000 <= rate <= 192000:
        raise ValueError("Invalid sample rate")
    return b"".join(
        struct.pack(
            "<hh",
            round(4096 * math.sin(2 * math.pi * 440 * i / rate)),
            round(4096 * math.sin(2 * math.pi * 880 * i / rate)),
        )
        for i in range(frames)
    )


def capture(seconds, output, backend=None):
    """@brief Save bounded-duration native-rate speaker-loopback PCM to a WAV.

    @param seconds Duration greater than zero and no more than sixty seconds.
    @param output New WAV path; existing files are never overwritten.
    @param backend Optional injected PyAudioWPatch-compatible backend for tests.
    @return Capture format, counters, duration and signal statistics.
    """
    if not math.isfinite(seconds) or not 0 < seconds <= 60:
        raise ValueError("Capture duration must be within (0,60] seconds")
    if backend is None:
        import pyaudiowpatch as backend

    output = Path(output)
    with backend.PyAudio() as audio:
        device = audio.get_default_wasapi_loopback()
        native_channels = int(device["maxInputChannels"])
        channels = min(native_channels, 2)
        rate = int(device["defaultSampleRate"])
        if not device.get("isLoopbackDevice") or native_channels not in (1, 2, 6, 8):
            raise ValueError("Expected a supported WASAPI speaker-loopback endpoint")
        if not 8000 <= rate <= 192000:
            raise ValueError("Unsupported native audio sample rate")
        target = max(1, round(rate * seconds))
        samples = peak = total_squared = frames = 0
        started = time.perf_counter()
        with output.open("xb") as raw, wave.open(raw, "wb") as wav:
            wav.setnchannels(channels)
            wav.setsampwidth(2)
            wav.setframerate(rate)
            with audio.open(
                format=backend.paInt16,
                channels=channels,
                rate=rate,
                input=True,
                input_device_index=device["index"],
                frames_per_buffer=max(1, rate // 100),
            ) as stream:
                while frames < target:
                    count = min(max(1, rate // 100), target - frames)
                    # An overflow raises; never silently present lost audio as contiguous.
                    block = stream.read(count, exception_on_overflow=True)
                    if len(block) != count * channels * 2:
                        raise ValueError("Short loopback audio block")
                    stats = pcm_stats(block)
                    samples += stats["samples"]
                    peak = max(peak, stats["peak"])
                    total_squared += stats["rms"] ** 2 * stats["samples"]
                    wav.writeframesraw(block)
                    frames += count
        return {
            "scope": "local Windows speaker loopback; not MoonBub playback",
            "device": device["name"],
            "rate": rate,
            "channels": channels,
            "endpoint_max_channels": native_channels,
            "format": "PCM signed 16-bit little-endian",
            "frames": frames,
            "audio_seconds": frames / rate,
            "wall_seconds": time.perf_counter() - started,
            "peak": peak,
            "rms": math.sqrt(total_squared / samples),
            "output": str(output),
        }


def main(argv=None):
    """@brief Capture a short local audio diagnostic and print its measured format."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(capture(args.seconds, args.output), indent=2))


if __name__ == "__main__":
    main()
