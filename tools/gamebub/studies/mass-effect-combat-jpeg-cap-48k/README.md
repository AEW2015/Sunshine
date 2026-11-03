# Mass Effect combat JPEG frame-size and retry study

This isolated study uses the Sunshine 30 fps study checkout's existing
`host.clip_frames`, `host.canvas`, and `host.encode` functions. It also compares
`host.encode` directly with the sender's `msv1.encode_receiver_jpeg` function.
The complete local `media/mass-effect-combat.mp4` is sampled at native 25 fps,
producing the same 720×480 canvas with a centered 720×405 viewport and black
letterbox. The source has 1,493 frames. No cadence duplicates are added.

The fixed-quality sweep encodes every canvas at Pillow JPEG qualities 35, 50,
65, 75, 80, 85, 90 and 95. The profile is baseline 4:2:0, no restart markers,
no progressive mode, and no optimized Huffman tables. These quality numbers
are encoder settings, not perceptual quality scores. Encoding validation uses a
16 MiB hard limit so the study can measure frames above the 48 KiB cap, which
is 49,152 JPEG bytes inclusive.

A paired offline policy comparison starts every frame at q90:

- **Drop-only:** discard a q90 JPEG if it exceeds the cap.
- **One retry:** re-encode that same canvas once at q80 if q90 exceeds the cap;
  send the retry if it fits, otherwise drop it.

The two policies share the same q90 frame encodes. Retry timing measures one
additional host encode only for oversize frames. Host encode timings include
JPEG inspection and software decode validation, so they are Linux host
measurements, not Windows real-time frame deadlines.

The encoder comparison runs both `host.encode` and the actual sender function
`msv1.encode_receiver_jpeg` for every frame at q80 and q90, and records full
byte equality and size deltas. This checks whether the fixed-quality study
sizes transfer to the sender encoder implementation. It does not exercise
sender quality adaptation or packetization.

Run from the prototype root's virtual environment:

```sh
/home/lori/gamebub-streaming-prototype/.venv/bin/python \
  repos/sunshine-30fps-study/tools/gamebub/studies/mass-effect-combat-jpeg-cap-48k/run.py
/home/lori/gamebub-streaming-prototype/.venv/bin/python \
  repos/sunshine-30fps-study/tools/gamebub/studies/mass-effect-combat-jpeg-cap-48k/retry-policy.py
/home/lori/gamebub-streaming-prototype/.venv/bin/python \
  repos/sunshine-30fps-study/tools/gamebub/studies/mass-effect-combat-jpeg-cap-48k/compare-encoders.py
```

`results.json`, `SUMMARY.md`, and `per-frame.csv` contain the size sweep.
`retry-policy-results.json`, `POLICY-SUMMARY.md`, and
`retry-policy-per-frame.csv` contain the drop/retry comparison.
`encoder-comparison.json`, `encoder-comparison-per-frame.csv`, and
`ENCODER-COMPARISON.md` contain the q80/q90 host-versus-sender byte comparison. Result JSON records the local
source hash and relevant encoder/profile details.

The input is a previously compressed 512×288 H.264 MP4 at 25 fps, approximately
59.72 seconds long. Its existing compression artifacts, low source resolution
and short combat scene limit how representative it is of direct high-resolution
gameplay. The cap applies to JPEG payload bytes only; MSV1 framing, UDP/IP
overhead, network transfer, and receiver/display behavior are excluded.
Nothing is transmitted and no sender code is changed. Results do not establish
a sustainable rate or a recommended quality for live gameplay.
