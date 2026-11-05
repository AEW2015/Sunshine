# Bounded same-process CP23 sequence replay

The per-case CLI study paid process startup separately for every source. The
new `--composed-sequence` mode keeps one process while replaying hash-bound RGB8
exports. It is still an independent-key software benchmark: no P frames, HD22,
joint reference publication, custom network endpoint or hardware playback.

```powershell
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c './cmake-build-gamebub-v20/gamebub-v20-conformance.exe --composed-sequence MANIFEST.json 60 --budgeted-keys'
```

The count is strictly 1–1800. `--repeat`, `--budgeted-keys` and
`--profile-substages` are explicit independent flags and default off. Without
`--repeat`, a count larger than available sources rejects before encoding.
Each repeat cycle creates a fresh unchanged `sequence::Reader`, revalidates the
same manifest hash/count and charges that work. Every loaded RGB is rehashed.

Each iteration is a fresh codec epoch `iteration+1`, frame 0, HUD generation 1.
Original decoded source IDs, PTS, RGB hashes and cycle numbers remain separate.
These codec fixture epochs do not exercise live transport reset or a stateful
stream. Raw RGB, immutable Source, encoded packet and decoder temporaries leave
scope before a weak-owner expiry check and the next iteration. Only bounded
diagnostic metadata rows remain; the report's maximum is 1800 rows.

The whole benchmark wall includes source input/hash/snapshot, encoding, chosen
pair decoder/JA23 validation, retirement and metadata work. It ends before final
JSON serialization/stdout and process shutdown. Source preparation, encode,
output-hash and iteration distributions remain separate; external process CPU
and memory are measured by the owning runner and do not replace native fields.

## Correctness gate

The standalone CLI and complete native target build; all 173 scoped GameBub tests
pass across 24 suites. Five new tests cover bounded unique flags, repeat opt-in,
known first-source pair/ACK hashes, default/budgeted/profile equivalence, original
source identities versus fresh codec epochs, strict path/late hash failure and
recovery, high-entropy cap rejection, full source retirement and accounting.
The helper has 112/112 executable lines hit. Its 328/656 compiled branches include
JSON/allocation/exception paths; full branch coverage is not claimed.

Independent source review found no actionable correctness or lifetime defect.
The validated executable SHA256 is
`15a08cc10367e9f26531b8f6cf1503f97217ca3f8bf56bc9497087f8dcbf22af`.
Native log/XML and fresh coverage are under
`artifacts/composed-encoder-20261105/sequence-*`.

## Repeated same-process ABBA

After the long localhost AV soak ended and the root reserved a quiet slot,
four fresh owned processes ran default/budgeted/budgeted/default. Each process
ran 1800 iterations: 30 explicit cycles of the same 60 native decoded Xonotic
sources. This is a repeated short-prefix study, not 1800 unique game scenes.
Each pass produced 1020 fit and 780 cap-rejected frames, 5640 real entropy candidates
and 1800 confirmed source retirements. Budgeted passes skipped 4620 proven-oversize
inverse/tag finalizations. All 7200 row hashes, candidate maps/sizes/admission,
source IDs/PTS/hashes and codec identities match across strategies.

| Pass | Inclusive native benchmark wall | External cumulative CPU | Encode p50 / p95 |
| --- | --- | --- | --- |
| Default A1 |86.414 s |86.391 s |45.259 /56.252 ms |
| Budgeted B1 |63.222 s |63.203 s |29.298 /40.381 ms |
| Budgeted B2 |62.873 s |62.875 s |29.139 /40.171 ms |
| Default A2 |86.928 s |86.859 s |45.539 /56.716 ms |

The paired inclusive same-process wall decreases approximately 27.3%, with
unchanged output/admission. Source preparation p50 is about 3.0–3.14 ms and is
charged separately. The 43.3% cap rejection and above 33.333 ms encoding tails
remain; these results do not establish 30 fps complete encoding or playback.
Independent decoder/JA23 verification stays enabled in every selected frame.

## External resource scope

The runner starts only its own immutable executable with `Popen`, samples every
0.5 s, caps history at 1200 samples, and has a 600 s watchdog. Failure cleanup
terminates only its owned child, never Sunshine or another PID. Final cumulative
user/kernel CPU comes from `GetProcessTimes` on that child's still-owned handle
after exit. Handles close after the final query. Post-exit RSS is excluded.
All four runs finish normally with zero sampler/API failures or timeouts.

Observed OS peak working sets are 31.56/31.92/31.36/32.26 MB in pass order;
sampled maximum private bytes are 26.07/24.19/24.33/25.67 MB. Exact byte values
are preserved in the summary. Metadata retention grows intentionally to 1800 rows;
this must not be confused with retained raw frames or an unbounded cache.
OS peak fields are the largest lifetime peaks reported during live polls and
can miss a final unsampled exit window. Peak pagefile usage is reported by its
own name and is never labeled peak private bytes. External CPU includes native
startup, final JSON/stdout and shutdown, whereas native benchmark wall ends
before those final operations. Native `process_cpu_measured` and
`peak_memory_measured` remain false; external scope is recorded separately.

The source clip is 1024×600, resized to 691×405 at `(14,37)` in a 720×480 canvas;
720×405 is the viewport. Original clip SHA256 is
`36ef854b29293c027dd161185dc0a2e9d03ec7854ea9039800164b03956d3a83`;
manifest SHA256 is
`f27c9b4da3fd2d4999d17ac08768021a4e09711c4dfb73b60c67c1fcba16d1d9`.
The original clip is provenance, not reread during the benchmark; every exported
RGB is verified each iteration. No capture, clip decoding/scaling, RF path,
receiver decoder, physical presentation or end-to-end latency is measured.

Full native outputs, live resource samples and owner summaries remain in
`artifacts/native-composed-sequence-abba-20261105/`. The compact tracked
[JSON report](cp23-same-process-sequence-20261105.json) preserves aggregate
timings, exact provenance/source hashes, resource scopes, correctness and limits.
