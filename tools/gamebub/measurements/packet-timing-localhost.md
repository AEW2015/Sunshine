# Continuous sender packet timing check

The opt-in `--packet-timing` records successful MSV1 datagram socket sends in
bounded per-frame JSONL events; it does not record image bytes or destination
addresses. A concurrent-load localhost check used 300 target slots of the
Xonotic source, 30 fps, quality 75, 20 Mbps cap and 200 ms age bound. The pinned
receiver reference accepted 287 complete frames; the sender reported one raw
frame and 12 encoded frames replaced. There were 287 packet timing records
covering 12,928 sends, and no logged events were dropped. The run lasted 10.325
seconds including feedback grace. A separate one-hour reference soak and other
work ran at the same time; this is not an isolated benchmark or a comparison of
logging overhead. The receiver was a local Python reassembler, not the handheld.

To reproduce from `tools/gamebub`, use a new log path:

```powershell
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'py.exe -3.11 -m uv run --locked python reference_loopback.py --reference-repo /c/ai/moonbub-reference --clip artifacts/media/Xonotic-0-8-2-gameplay.webm --frames 300 --fps 30 --mbps 20 --max-age-ms 200 --quality 75 --min-quality 20 --packet-timing --log artifacts/packet-timing-new.jsonl'
```

The frame log and summary from this run are ignored local artifacts. Send times
are after socket calls and do not establish Wi-Fi airtime or receiver arrival.
The bounded logger may drop timing records, especially in long or high-rate
runs; check `logging.dropped` and `packet_timing_enqueue_dropped` before using
an absent event as evidence. The default sender leaves this instrumentation off.
