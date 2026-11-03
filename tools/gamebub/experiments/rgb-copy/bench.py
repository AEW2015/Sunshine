#!/usr/bin/env python3
"""Paired same-input scale+encode microbenchmark; no live capture or transport."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import time
import sys

HERE=Path(__file__).resolve().parent
GAMEBUB=HERE.parents[1]
sys.path.insert(0,str(GAMEBUB))
sys.path.insert(0,str(HERE))
from PIL import Image, __version__ as pillow_version, features
from host import canvas
from fast_canvas import fast_canvas
from msv1 import encode_receiver_jpeg


def percentile(values,q):
    v=sorted(values);return v[min(len(v)-1,int((len(v)-1)*q))]


def timed(fn,im,filt):
    t=time.perf_counter_ns();out=fn(im,filt);jpeg=bytes(encode_receiver_jpeg(out,65))
    return (time.perf_counter_ns()-t)/1e6,jpeg


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--iterations',type=int,default=150)
    p.add_argument('--output',type=Path,default=HERE/'results.json')
    args=p.parse_args()
    if args.iterations < 2: p.error('at least 2 iterations required')
    sources=[]; fixtures=sorted((GAMEBUB/'fixtures').glob('frame-*.png'))
    for path in fixtures:
        with Image.open(path) as image:
            # 16:9 content of existing 720x480 letterboxed fixture.
            content=image.convert('RGB').crop((0,37,720,442))
            sources.append(content.resize((1920,1080),Image.Resampling.LANCZOS))
    if len(sources)<2:raise RuntimeError('missing fixture set')
    rows=[]
    for filter_name in ('BILINEAR','BOX'):
        filt=Image.Resampling[filter_name]
        expected=[]
        # Check byte equality before timing for every input, including encoded JPEG.
        for image in sources:
            a,b=canvas(image,filt),fast_canvas(image,filt)
            if a.tobytes()!=b.tobytes():raise AssertionError('canvas mismatch')
            j1,j2=bytes(encode_receiver_jpeg(a,65)),bytes(encode_receiver_jpeg(b,65))
            if j1!=j2:raise AssertionError('JPEG mismatch')
            expected.append(hashlib.sha256(j1).hexdigest())
        for image in sources:
            timed(canvas,image,filt);timed(fast_canvas,image,filt)
        base=[];candidate=[]
        for i in range(args.iterations):
            im=sources[i%len(sources)]
            # Alternate order each pair to limit systematic warm-cache/order bias.
            for label,fn in ((('stock',canvas),('candidate',fast_canvas)) if i%2==0 else (('candidate',fast_canvas),('stock',canvas))):
                ms,jpeg=timed(fn,im,filt)
                if hashlib.sha256(jpeg).hexdigest()!=expected[i%len(expected)]:raise AssertionError('output changed')
                (base if label=='stock' else candidate).append(ms)
        ratios=[b/a for a,b in zip(base,candidate)]
        rows.append({'filter':filter_name,'iterations_per_variant':args.iterations,
                     'stock_ms_p50':statistics.median(base),'stock_ms_p95':percentile(base,.95),
                     'candidate_ms_p50':statistics.median(candidate),'candidate_ms_p95':percentile(candidate,.95),
                     'paired_ratio_candidate_over_stock_median':statistics.median(ratios),
                     'paired_candidate_faster_count':sum(b<a for a,b in zip(base,candidate)),
                     'outputs_byte_identical':True,'jpeg_sha256':expected})
    info={'scope':'Linux offline paired scale+strict JPEG encode; no capture/network/ESP32/FPGA',
          'source':'5 checked-in 720x480 synthetic fixtures cropped to 720x405 then upscaled to 1920x1080 before timing; not real 1080p gameplay',
          'fixture_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in fixtures},
          'pillow':pillow_version,'jpeg_library':features.version('jpg'),'python':platform.python_version(),
          'cpu':next((x.split(':',1)[1].strip() for x in Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('model name')),'unknown'),
          'rows':rows}
    args.output.write_text(json.dumps(info,indent=2)+'\n');print(json.dumps(info,indent=2))


if __name__=='__main__':main()
