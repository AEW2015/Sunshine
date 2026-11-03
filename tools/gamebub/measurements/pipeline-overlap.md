# Host-only overlap experiment

On the Windows host, a 10.016-second run sampled the first 300 frames of the
Big Buck Bunny animation source documented in [bbb-source.json](bbb-source.json).
The capture thread decoded and bilinear-scaled to a 720x480 letterboxed canvas;
the pipeline encoded JPEG 4:2:0 at fixed quality 75 while a second worker slept
for the time required to serialize the JPEG payload on a simulated 20 Mbps
link. The model included no packet overhead, Wi-Fi, feedback, or receiver.

Of 300 submitted frames, 299 were encoded and 297 completed the simulated send
(29.65 fps). One frame expired before encoding, one before send, and one was
rejected because its predicted completion exceeded the 66.7 ms capture-age
budget. Completed payload averaged 30,169 bytes/frame and 7.16 Mbps, with
62.0 ms p95 host completion age. The callback checks the budget before sleeping;
OS scheduling may overshoot. This run uses fixed quality and a shorter segment
than previous adaptive-quality measurements, so their FPS values are not a
controlled comparison. It does not establish hardware playback or latency.

Reproduce from `tools/gamebub` after the lab setup and Big Buck Bunny download
in the README, with a fresh working directory and minimal background load:

```python
import time
from pathlib import Path
from host import Profile, canvas, clip_frames, encode
from pipeline import Frame, VideoPipeline

start = time.monotonic_ns()
sizes, ages = [], []


def send(frame, jpeg):
    delay = len(jpeg) * 8 / 20_000_000
    if time.monotonic_ns() + int(delay * 1e9) > frame.captured_ns + 66_700_000:
        return False
    time.sleep(delay)
    sizes.append(len(jpeg))
    ages.append((time.monotonic_ns() - frame.captured_ns) / 1e6)
    return True


p = VideoPipeline(lambda img: encode(img, 75, Profile())[0], send, 66_700_000, 262144)
frames = clip_frames(Path("artifacts/media/BigBuckBunny-1080p30-30s.mp4"), 30)
for i in range(300):
    delay = (start + i * 1_000_000_000 // 30 - time.monotonic_ns()) / 1e9
    if delay > 0:
        time.sleep(delay)
    captured = time.monotonic_ns()
    frame = next(frames)
    p.submit(Frame(i, captured, time.time_ns() // 1000, canvas(frame)))
frames.close()
p.close()
duration = (time.monotonic_ns() - start) / 1e9
print(p.snapshot(), "duration", duration, "completed fps", len(sizes) / duration)
print(
    "payload Mbps",
    sum(sizes) * 8 / duration / 1e6,
    "mean bytes",
    sum(sizes) / len(sizes),
    "p95 host age ms",
    sorted(ages)[int(0.95 * (len(ages) - 1))],
)
```
