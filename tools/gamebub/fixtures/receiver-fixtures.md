# Pinned MoonBub receiver fixtures

The two `receiver-pattern-*` files are copied unchanged from the receiver team's
[MoonBub revision 75f8497](https://github.com/AEW2015/moonbub/tree/75f8497b6ffefadd8c0403728b93ccfbbfa02f52/host/fixtures).
They are synthetic test material, not game footage or a hardware capture.

| File | SHA-256 |
| --- | --- |
| `receiver-pattern-720x480-420-q65.jpg` | `8cc99ea7d50d1d20255e41ff7247b0770b3349e705c27152a41817418ce5c9de` |
| `receiver-pattern-msv1-packets.bin` | `78c58cfcc4860761c33bcc7021e3db14e9fa66ef5e9a385ae1e4c00c82a6447f` |

The packet fixture stores repeated big-endian 16-bit datagram lengths followed
by exact network datagrams. Its frame ID is `0x12345678` and timestamp is
`1234567890123` µs. Length prefixes are fixture framing, never UDP payload.
The regression test compares every byte produced by this host's packetizer.
