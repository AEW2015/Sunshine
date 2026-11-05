"""@brief Isolate unchanged MSV1 pacing waits and UDP sends on localhost only.

The spin-tail alternative is a laboratory experiment, not a shipping change.
No global timer-resolution changes, hardware traffic or input injection occur.
"""
import sys
from pathlib import Path
OUT=Path(__file__).resolve().parent
HERE=OUT.parents[1]
sys.path.insert(0,str(HERE))
import hashlib
import json
import math
import socket
import time
from host import canvas,clip_frames
from msv1 import Pacer,send_frame,encode_receiver_jpeg
from reference_loopback import ReferencePeer,load_reference

def stats(values):
    """@brief Summarize exact nearest-rank quantiles of measured milliseconds."""
    data=sorted(values)
    return {'count':len(data),'min':data[0],
        **{f'p{p}':data[math.ceil(len(data)*p/100)-1] for p in (50,95,99)},'max':data[-1]}

def probe(reference,jpeg,mode,index):
    """@brief Inject measured waits/sends into the unchanged real packet pacer."""
    peer=ReferencePeer(reference)
    waits,send_times,gaps,late=[],[],[],[]
    spin_ns=0
    previous=None
    frames=80
    clock=time.perf_counter
    class TimedSocket:
        """@brief Record API duration around successful localhost sends."""
        def send(self,raw):
            start=time.perf_counter_ns()
            count=sock.send(raw)
            send_times.append((time.perf_counter_ns()-start)/1e6)
            return count
    def sleeper(seconds):
        """@brief Measure requested deadline and wake overshoot for one wait."""
        nonlocal spin_ns
        start=time.perf_counter_ns()
        target=clock()+seconds
        if mode=='sleep':
            time.sleep(seconds)
        else:
            if seconds>.001:
                time.sleep(seconds-.001)
            spin_start=time.perf_counter_ns()
            while clock()<target:
                pass
            spin_ns+=time.perf_counter_ns()-spin_start
        finished=time.perf_counter_ns()
        waits.append({'requested_ms':seconds*1000,'elapsed_ms':(finished-start)/1e6,
            'overshoot_ms':max(0,(clock()-target)*1000)})
    def packet(raw,stamp):
        """@brief Measure post-send gap relative to the unchanged pacer's next deadline."""
        nonlocal previous
        if previous is not None:
            prior_stamp,prior_size=previous
            gaps.append((stamp-prior_stamp)*1000)
            late.append((stamp-prior_stamp-prior_size/500000)*1000)
        previous=(stamp,len(raw))
    start=clock()
    cpu_start=time.process_time()
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
        sock.connect(('127.0.0.1',peer.port))
        sock.setblocking(False)
        pacer=Pacer()
        for frame in range(frames):
            done,_=send_frame(TimedSocket(),jpeg,frame,frame+1,500000,clock()+1,
                clock=clock,sleeper=sleeper,pacer=pacer,on_packet=packet)
            if not done:
                raise RuntimeError('Unexpected localhost deadline failure')
        sender_seconds=clock()-start
        process_cpu=time.process_time()-cpu_start
        sock.settimeout(.2)
        acks=0
        try:
            while True:
                sock.recv(2048)
                acks+=1
        except TimeoutError:
            pass
    received=peer.close()
    result={'mode':mode,'frames':frames,'jpeg_bytes':len(jpeg),'datagrams':len(send_times),
        'sender_seconds':sender_seconds,'process_cpu_seconds':process_cpu,
        'spin_seconds':spin_ns/1e9,'receiver':received,'acks':acks,
        'gap_ms':stats(gaps),'post_send_deadline_lateness_ms':stats(late),
        'sleep_requested_ms':stats([w['requested_ms'] for w in waits]),
        'sleep_overshoot_ms':stats([w['overshoot_ms'] for w in waits]),
        'send_api_duration_ms':stats(send_times)}
    (OUT/f'wait-probe-{index}-{mode}.json').write_text(json.dumps({'summary':result,'waits':waits},indent=2))
    print(json.dumps(result),flush=True)
    return result

if __name__=='__main__':
    source=HERE/'artifacts/media/Xonotic-0-8-2-gameplay.webm'
    frames=clip_frames(source,20)
    try:
        jpeg=encode_receiver_jpeg(canvas(next(frames)),25)
    finally:
        frames.close()
    reference=load_reference(HERE/'artifacts/moonbub-30fps-study')
    results=[probe(reference,jpeg,mode,index) for index,mode in enumerate(('sleep','spin_tail','spin_tail','sleep'))]
    (OUT/'wait-probe-summary.json').write_text(json.dumps({'scope':__doc__,
        'jpeg_sha256':hashlib.sha256(jpeg).hexdigest(),'results':results},indent=2))
