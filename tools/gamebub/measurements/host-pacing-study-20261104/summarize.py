"""@brief Preserve like-for-like localhost results and post-send gap distributions."""
import json
import math
import platform
import sys
import time
from pathlib import Path

out=Path(__file__).resolve().parent
def stats(values):
    """@brief Exact nearest-rank gap statistics in milliseconds."""
    values=sorted(values)
    return {'count':len(values),'min_ms':values[0],
        **{f'p{p}_ms':values[math.ceil(len(values)*p/100)-1] for p in (50,95,99)},
        'max_ms':values[-1]}

result={'scope':'Localhost transport only; neither original hardware losses nor playback verified',
    'python':sys.version,'platform':platform.platform(),'clock':str(time.get_clock_info('perf_counter')),
    'clip_sha256':'36ef854b29293c027dd161185dc0a2e9d03ec7854ea9039800164b03956d3a83',
    'runs':{},'wait_probe':json.loads((out/'wait-probe-summary.json').read_text())}
lengths=[]
for name in ('baseline','candidate'):
    rows=[json.loads(line) for line in (out/f'{name}-video.jsonl').read_text().splitlines()]
    summary=json.loads((out/f'{name}-result.json').read_text(encoding='utf-8-sig'))
    packets=[(r['frame_id'],p[0],p[2]) for r in rows if r['event']=='packet_timing' for p in r['packets']]
    gaps=[(b[2]-a[2])*1000 for a,b in zip(packets,packets[1:]) if a[0]==b[0]]
    summary['within_frame_gap_ms']=stats(gaps)
    summary['sent_complete']=sum(r['complete'] for r in rows if r['event']=='send')
    summary['partial_sends']=sum(not r['complete'] for r in rows if r['event']=='send')
    result['runs'][name]=summary
    lengths.append({r['frame_id']:r['bytes'] for r in rows if r['event']=='encode'})
result['same_encoded_length_by_slot']=lengths[0]==lengths[1]
(out/'host-study-result.json').write_text(json.dumps(result,indent=2))
for name,summary in result['runs'].items():
    print(name,json.dumps(summary['within_frame_gap_ms']))
print('same_encoded_length_by_slot',result['same_encoded_length_by_slot'])
