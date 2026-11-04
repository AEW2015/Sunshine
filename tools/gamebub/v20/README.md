# v20 host and hardware development handoff

Pair this branch with Moonbub `handoff/gamebub-app-codec-v20-20261103`.
The copied JSON files are byte-identical to its hardware kit and checked by the
paired provenance manifest. No Sunshine native encoder mode is implemented here.

Start with the [hardware kit](https://github.com/AEW2015/moonbub/tree/handoff/gamebub-app-codec-v20-20261103/hardware/gamebub-v20),
[implementation tasks](https://github.com/AEW2015/moonbub/blob/handoff/gamebub-app-codec-v20-20261103/hardware/gamebub-v20/TASKS.md),
and [acceptance gates](https://github.com/AEW2015/moonbub/blob/handoff/gamebub-app-codec-v20-20261103/hardware/gamebub-v20/ACCEPTANCE.md).
The Moonbub branch includes a portable C11 inverse reference, compressed golden
arrays, readmemh export, complete AR03/AF03 fixtures and IT20 generated-tile streams.
IT20 is an offline fixture, not a new runtime codec.

For the first native host port, implement the mandatory-HUD policy: encode and
validate all requested exact RGB565 patches, reserve complete framed bytes, then
try at most four declared ROI/background quantization maps. Preserve source leases
until actual commit/discard. Reject the whole candidate when no map fits; every
losing build and patch/cache validation cost remains paid. The complete AR03 cap
is 49,152 bytes, including header, inner payload, UI framing and final CRC. The four
requested regions and map profiles are in development-profile.json.

Use the twenty isolated mandatory-HUD packet fixtures with their exact predictor
bank/id/tag preconditions. They prove original selected RGB565 words, YUV banks,
canonical reference tags, display outputs and AF03 feedback. The real complex
scene now preserves all four regions, but its background MSE rises and its forward
data projects to 11.376 Mb/s at 30 fps before controls/reverse/radio overhead. This
exceeds the old 8 Mb/s modeling assumption. Do not infer sustained native throughput
from the encoder loop or the scalar inverse replay.

FG19 is prospective negotiated endpoint work: GRANT reserves the exact frame slot,
PC18 returns only packet capacity, FINISHED frees only the request-control token,
RELEASE follows actual frame/read drain, and AF03 alone confirms a decoded reference.
Use wire-contract.json byte offsets and serialized control cases. Production
capability negotiation, epoch reset/rekey, reconnect and unknown-outcome recovery
are still required. Preserve the working JPEG path until the paired custom endpoint
passes its gates. Existing host byte caching does not implement receiver HUD-cache
reuse; that needs a separate identity/generation/loss contract.

Host developers can begin offline conformance immediately, with no board or
installed Sunshine service changes. Integrate a native mode only after the receiver
can validate its advertised profile and resource/service limits are measured.
