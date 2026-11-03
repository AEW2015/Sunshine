# Host-only RGB copy avoidance experiment

This is an isolated function prototype and microbenchmark. It does not modify
Sunshine, the installed service, the sender, the FPGA or a production path.
`fast_canvas` follows the existing `host.canvas` geometry, but avoids
`image.convert("RGB")` when a Pillow image is already RGB. Pillow's conversion
of an already RGB image creates a full-sized copy. Resizing still returns a
new image, and the returned 720×480 canvas is newly allocated. Non-RGB inputs
retain the original conversion; PyAV frames delegate to the existing path.

**Ownership condition:** the caller must keep the source image alive and must
not mutate it concurrently until `fast_canvas` returns. This matters for a
capture backend that reuses its pixel buffer. The prototype does not establish
that DXGI/DXcam buffers satisfy the condition, and it does not change the
existing sender. A safe integration must first establish source lifetime and
avoid racing capture-buffer reuse; otherwise retain the copy.

## Paired measurements

On Linux (Ryzen 7 H 255), Python 3.14.4, Pillow 13.0.0 reporting JPEG ABI 6.2
and PyAV 19.0.2, the benchmark cropped five tracked synthetic 720×480 fixture
PNGs to their 720×405 content and upscaled them **once before timing** to
1920×1080 RGB. Each measurement includes letterbox scaling, strict receiver-
profile q65 JPEG encode and validation, but excludes screen capture, frame
acquisition, network, ESP32, QSPI and display. These are upscaled synthetic
fixtures, not native 1080p gameplay.

Each run performed 120 matched pairs per filter after warmups; stock/candidate
order alternated each pair. Every paired canvas and JPEG was byte-identical
for these inputs. Results are milliseconds (p50/p95):

| Filter | Run | Existing | Candidate | Candidate faster |
| --- | ---: | ---: | ---: | ---: |
| Bilinear | 1 | 10.456 / 10.597 | 9.847 / 10.047 | 118/120 pairs |
| Bilinear | 2 | 10.476 / 10.774 | 9.778 / 10.014 | 120/120 pairs |
| BOX | 1 | 7.397 / 7.531 | 6.770 / 6.870 | 120/120 pairs |
| BOX | 2 | 7.386 / 7.630 | 6.725 / 6.912 | 119/120 pairs |

These measurements indicate roughly 0.6–0.7 ms saved in this isolated Linux
workload, not a demonstrated end-to-end FPS increase. Capture and scaling are
known Windows bottlenecks, but this host is not the Windows gaming laptop;
repeat with a real, owned Windows capture buffer, controlled gameplay and the
actual receiver before judging the benefit. No concurrent source mutation was
modeled. JPEG hashes, environment and fixture hashes are in `results.json` and
`results-repeat.json`; raw individual pair times are not recorded. The two
runs were sequential on one shared machine and are not a statistical guarantee.

## Reproduce

Install Python 3.11–3.14 and the host-lab dependencies in
`tools/gamebub/pyproject.toml`; the recorded environment used the versions
above. From the repository root:

```sh
PYTHONPATH=tools/gamebub:tools/gamebub/experiments/rgb-copy \
  python -m unittest discover -s tools/gamebub/experiments/rgb-copy -p 'test_*.py' -v
PYTHONPATH=tools/gamebub \
  python tools/gamebub/experiments/rgb-copy/bench.py --iterations 120 --output /tmp/rgb-copy-results.json
```

Tests cover RGB, RGBA, L and palette sources; wide, tall, native and tiny
sizes; both filters; byte-exact canvas/JPEG output; non-mutation and ownership
after return; and delegation of PyAV video frames. These tests do not simulate
a concurrent writer or prove screenshot-library buffer lifetime.

The isolated tests passed (3 tests). A broader run on this Linux/Pillow 13
setup ran 107 host-lab tests and reported one failure plus five skips: the
existing `test_assets_reproduce_the_committed_manifest` expects the Windows-
generated PNG file hashes. Regenerating the manifest separately showed that
only its 15 `png_sha256` fields differed; JPEG hashes and all other manifest
fields matched. This prototype does not modify the existing fixture test or
its committed data.
