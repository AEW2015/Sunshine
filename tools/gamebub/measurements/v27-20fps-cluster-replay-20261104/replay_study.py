"""@brief Export and locally replay logged transport metadata, never original JPEG bytes.

Only loopback sockets are used. The pinned Python receiver is a transport
reference, not v27 firmware, its queue, QSPI, FPGA or a JPEG decoder.
"""
import csv
import hashlib
import json
import os
import socket
import sys
import time
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent
HERE = OUT.parents[1]
sys.path.insert(0, str(HERE))
from msv1 import VIDEO
from reference_loopback import ReferencePeer, load_reference, REVISION, REFERENCE_SHA256

WINDOWS = ((2001108, 2001112), (2004704, 2004812))


def export_schedule(rows, lower, upper):
    """@brief Retain every logged packet in a frame-ID window with source order intact."""
    sends = {r['frame_id']: r for r in rows if r['event'] == 'send'}
    result = []
    for row in rows:
        if row['event'] != 'packet_timing' or not lower <= row['frame_id'] <= upper:
            continue
        size = sends[row['frame_id']]['jpeg_bytes']
        for offset, count, stamp in row['packets']:
            result.append({'frame_id': row['frame_id'], 'capture_us': row['capture_us'],
                'jpeg_bytes': size, 'offset': offset, 'count': count,
                'post_send_s': stamp, 'flags': int(offset == 0) | (2 * int(offset + count == size))})
    return result


def datagrams(schedule):
    """@brief Rebuild synthetic zero-payload datagrams with recorded sizes and new CRCs."""
    for packet in schedule:
        size = packet['jpeg_bytes']
        crc = zlib.crc32(bytes(size))
        yield VIDEO.pack(b'MSV1', 1, 1, packet['flags'], packet['frame_id'], 720, 480,
            size, packet['offset'], packet['count'], 0, crc, packet['capture_us']) + bytes(packet['count'])


def inspect_schedule(schedule):
    """@brief Check original log ordering and adjacent tail-to-SOF gaps without sorting."""
    errors, boundaries, previous = [], [], None
    next_offset = 0
    for packet in schedule:
        if previous is not None:
            gap = (packet['post_send_s'] - previous['post_send_s']) * 1000
            if gap < 0:
                errors.append({'reason': 'timestamp moved backward', 'packet': packet})
            if packet['frame_id'] != previous['frame_id']:
                boundaries.append({'previous_id': previous['frame_id'],
                    'previous_tail_offset': previous['offset'], 'next_id': packet['frame_id'],
                    'next_offset': packet['offset'], 'tail_to_sof_gap_ms': gap})
                if previous['offset'] + previous['count'] != previous['jpeg_bytes']:
                    errors.append({'reason': 'previous frame incomplete', 'packet': previous})
                next_offset = 0
        if packet['offset'] != next_offset:
            errors.append({'reason': 'offset discontinuity', 'expected': next_offset, 'packet': packet})
        next_offset = packet['offset'] + packet['count']
        previous = packet
    return {'packets': len(schedule), 'frames': sum(p['offset'] == 0 for p in schedule),
        'order_errors': errors, 'frame_boundaries': boundaries}


def replay(reference, schedule, paced=False):
    """@brief Replay structural metadata in memory or at recorded gaps over localhost UDP."""
    packets = list(datagrams(schedule))
    if not paced:
        receiver = reference.Reassembler()
        completed, errors = [], []
        for index, raw in enumerate(packets):
            try:
                accepted = receiver.accept(raw)
            except ValueError as error:
                errors.append({'packet_index': index, 'reason': str(error)})
            else:
                if accepted is not None:
                    completed.append(accepted[0].frame_id)
        return {'completed_ids': completed, 'errors': errors}
    peer = ReferencePeer(reference)
    max_lateness = 0
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            sender.connect(('127.0.0.1', peer.port))
            start, origin = time.perf_counter(), schedule[0]['post_send_s']
            for item, raw in zip(schedule, packets):
                due = start + item['post_send_s'] - origin
                remaining = due - time.perf_counter()
                if remaining > 0:
                    time.sleep(remaining)
                sender.send(raw)
                max_lateness = max(max_lateness, (time.perf_counter() - due) * 1000)
            sender.settimeout(0.2)
            acks = 0
            try:
                while True:
                    sender.recv(2048)
                    acks += 1
            except TimeoutError:
                pass
    finally:
        stats = peer.close()
    return {'receiver': stats, 'acks_read': acks, 'max_post_send_lateness_ms': max_lateness,
        'nominal_schedule_s': schedule[-1]['post_send_s'] - schedule[0]['post_send_s']}


def study():
    """@brief Preserve schedules, baseline replays and explicit missing-SOF hypotheses."""
    source = OUT / 'video.jsonl'
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    reference = load_reference(os.environ.get('MOONBUB_REFERENCE', HERE / 'artifacts/moonbub-30fps-study'))
    result = {'scope': __doc__, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'reference_revision': REVISION, 'reference_sha256': REFERENCE_SHA256, 'windows': []}
    for lower, upper in WINDOWS:
        schedule = export_schedule(rows, lower, upper)
        path = OUT / f'schedule-{lower}-{upper}.tsv'
        with path.open('w', newline='') as output:
            writer = csv.DictWriter(output, fieldnames=list(schedule[0]), delimiter='\t')
            writer.writeheader()
            writer.writerows(schedule)
        item = {'range': [lower, upper], 'schedule_file': path.name,
            'schedule_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'inspection': inspect_schedule(schedule), 'unimpaired': replay(reference, schedule),
            'paced_localhost': replay(reference, schedule, paced=True)}
        result['windows'].append(item)
        print(json.dumps({'range':item['range'],'packets':item['inspection']['packets'],
            'frames':item['inspection']['frames'],'order_errors':len(item['inspection']['order_errors']),
            'offline_completed':len(item['unimpaired']['completed_ids']),
            'offline_errors':len(item['unimpaired']['errors']),'localhost':item['paced_localhost']}),flush=True)
    # Deliberately truncate an older frame and remove the next frame's SOF.
    # This is a hypothesis demonstration; it does not reconstruct observed RF traffic.
    cluster = export_schedule(rows, *WINDOWS[1])
    for old_id, new_id, old_expected, new_observed in ((2004772,2004773,16384,1024),
            (2004806,2004807,14336,6144)):
        old = [p for p in cluster if p['frame_id']==old_id and p['offset']<old_expected]
        new = [p for p in cluster if p['frame_id']==new_id and p['offset']>=new_observed]
        probe = replay(reference, old + new[:1])
        result.setdefault('injected_missing_sof_hypotheses', []).append({
            'active_older_frame':old_id,'incoming_newer_frame':new_id,
            'expected_old_offset':old_expected,'observed_new_offset':new_observed,
            'injected_old_tail_loss':True,'injected_new_prefix_loss':True,'reference_result':probe})
    (OUT/'schedule-replay-result.json').write_text(json.dumps(result,indent=2))


if __name__ == '__main__':
    study()
