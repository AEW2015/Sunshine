# Host JPEG validation profile

An exploratory host-only profile used 60 Xonotic frames, three repetitions at
quality 75, 43–59 KB JPEG per frame, with operations interleaved. Other
localhost work ran concurrently; values are medians and are not isolated or
end-to-end playback results:

| Operation | Median |
| --- | ---: |
| JPEG encode/save | 1.898 ms |
| Syntax inspection | 0.222 ms |
| Full software decode | 2.376 ms |
| Full receiver-profile validation | 2.554 ms |
| Encode plus validation | 4.572 ms |
| CRC | 0.051 ms |
| Packetization including CRC of a previously validated JPEG | 0.129 ms |
| Packetization from raw JPEG bytes, requiring validation again | 2.717 ms |

Full decode accounts for a substantial share of validation time, but it
checks more than marker syntax; it does not prove decoded pixel correctness
or detect every entropy corruption. MSV1's frame CRC checks transport
integrity. Do not remove the decode, substitute a grayscale-only
decode, or validate only sampled frames without demonstrating equivalent
corruption detection and agreeing on the receiver requirements. The current
immutable validated-JPEG wrapper avoids a second validation on packetization.
The ignored local `artifacts/jpeg_profile_benchmark.py` and
`artifacts/jpeg-profile-benchmark.json` contain the exploratory procedure and
results. The measurement does not establish FPGA decode time or wire capacity.
