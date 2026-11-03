# Desktop Duplication ten-minute localhost soak

On November 2, 2026 the standalone sender ran `--desktop --desktop-backend
ddagrab` against the hash-checked MoonBub Python reference at revision
`75f8497b6ffefadd8c0403728b93ccfbbfa02f52`, on the same Windows host. The
source was uncontrolled live desktop content; Desktop Duplication permits
repeated frames. This was not controlled moving game footage or fresh-frame
measurement. The host scaled and letterboxed the desktop to the
720x480 JPEG canvas using baseline 4:2:0, quality 75, and no restart markers.

The 600.325-second run included final feedback grace. Of 18,000 target slots,
71 were skipped. The remaining **17,929** frames were encoded, sent, and
reassembled by the reference peer (29.865 fps over reported duration). No
invalid datagrams, reply failures, pending feedback, pipeline errors, or
logging errors were reported; all 53,789 event records were written. JPEG
quality remained at 75. Average JPEG payload was 7.251 Mbps and average MSV1
traffic was 7.540 Mbps; these exclude UDP/IP/Wi-Fi overhead and audio, and the
configured MSV1 cap was 20 Mbps.

Host timestamp-to-final-send age was median 40.041 ms, p95 47.285 ms,
maximum 129.043 ms. The timestamp is assigned after retrieving a frame, so it
excludes capture wait and the source image's age. Encoded queue age was median
0.231 ms and p95 4.019 ms;
encoding was median 3.921 ms and p95 5.398 ms. These host-side ages are not
glass-to-glass latency. A few spot checks of the Python process reported about
80–82 MB of private memory; infrequent samples do not rule out leaks. The run
was interrupted once before this attempt to accommodate a separate hardware
test, then restarted from the beginning; the numbers above are from the full
uninterrupted run only.

Reproduce with a new log filename from `tools/gamebub`:

```powershell
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'py.exe -3.11 -m uv run --locked python reference_loopback.py --reference-repo /c/ai/moonbub-reference --desktop --desktop-backend ddagrab --frames 18000 --fps 30 --mbps 20 --max-age-ms 200 --quality 75 --min-quality 20 --log artifacts/ddagrab-soak-new.jsonl'
```

The summary and frame log are local ignored artifacts. No handheld, physical
Wi-Fi, QSPI, FPGA decoding, display, or audio participated in this soak.

# Separate 5 fps physical receiver run

Immediately before the soak, the desktop sender ran against the handheld for
100 target slots, frame IDs 89–188, at 5 fps with a 2 Mbps MSV1 cap, fixed JPEG
quality 25, a 200 ms host deadline, and 720x480 letterboxed output. The source
was live desktop capture, not a controlled moving-footage benchmark. All 100
frames were encoded; 92 were fully sent and eight were suppressed while
recovering from feedback silence. The sender logged 79 accepted and 10 rejected
matching feedback events, plus three abandoned pending feedback entries. The
last receiver feedback reported cumulative 82 received and 10 dropped; its
baseline was not independently recorded. Independently confirmed decode and
display counts were not available at the time of writing. Sent MSV1 traffic
averaged 0.538 Mbps over 20.538 seconds, below the configured cap. The frame
log is the ignored local artifact `handheld-continuous-q25-5fps-100.jsonl`.
The receiver rejected IDs 111, 133, 154, 164, 169, 171, 173, 175, 177, and
179. These results do not establish 30 fps hardware playback.
