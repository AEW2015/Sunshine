# First live game-video diagnostic on the handheld

On November 2, 2026, the standalone Windows test sender captured the host's
desktop with a game visible, scaled it into the 720x480 canvas, encoded
baseline 4:2:0 JPEG and sent it to the physical handheld's Test MJPEG receiver.
The operator confirmed that the game appeared on the handheld and updated.
This was **video only**, not normal Sunshine pairing or interactive gameplay;
no audio or Windows controller input was exercised.

Settings: target **1 fps**, MSV1 cap **0.5 Mbps**, JPEG quality initially 75
with adaptive range 20..75, maximum host frame age 3000 ms. One fixed UDP
source port and frame IDs newer than the prior fixture test were used. The
9.640-second run submitted and encoded 10 captures, sent 9 complete frames,
and suppressed one frame after a feedback timeout; the sender later recorded
feedback recovery. The receiver's reported cumulative received count rose from
7 to 16, while its dropped count stayed at 4. The operator confirmed visible
game updates, but did not provide new independent decode/display counts for
this run. Matching status-0 feedback can be a heartbeat, so these observations
do not prove that all nine received frames were displayed.

The sender's reported rate was **0.934 sent frames/s** over the full duration,
including the 300 ms final feedback grace period, and **0.183 Mbps** of MSV1
datagrams. All ten encodes used quality **75**; JPEG size had median 17,563
bytes and maximum 38,570. Capture-to-final-send host age for complete sends was
median **347.4 ms**, p95 **680.2 ms**, maximum **1546.4 ms**. This is not
glass-to-glass latency. Queue age had median 0.153 ms and maximum 0.204 ms.

The log had no dropped records or logging error and contains metadata only;
it remains in ignored local artifact `handheld-game-video-first.jsonl`. One
test at this rate does not establish sustained performance, Wi-Fi capacity,
30 fps capability, or visual quality across games. Sender and receiver source
ports, private addresses and the visible desktop image are not included here.
