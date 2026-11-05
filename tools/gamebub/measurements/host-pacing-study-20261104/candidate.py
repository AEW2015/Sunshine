"""@brief Localhost-only experiment with a bounded spin tail and unchanged packet pacer."""
import sys
from pathlib import Path
OUT=Path(__file__).resolve().parent
HERE=OUT.parents[1]
sys.path.insert(0,str(HERE))
import json
import time
from types import SimpleNamespace
import stream_sender
from reference_loopback import run_reference

def bounded_wait(seconds,original,clock=time.perf_counter,spin_seconds=.001):
    """@brief Wait to a local deadline; preserve long-wait liveness checks.

    @param seconds Existing sender-requested wait duration.
    @param original Existing guarded sleeper, retaining feedback expiry checks.
    @param clock Injectable monotonic clock.
    @param spin_seconds Maximum requested final busy-wait window.
    """
    if seconds>.05:
        original(seconds)
        return
    deadline=clock()+seconds
    if seconds>spin_seconds:
        original(seconds-spin_seconds)
    while clock()<deadline:
        pass

def install():
    """@brief Replace only this process's injected sleeper; do not alter production files."""
    original_send=stream_sender.send_frame
    def send(*args,**kwargs):
        """@brief Preserve all sender parameters and wrap its guarded wait callback."""
        original_wait=kwargs['sleeper']
        kwargs['sleeper']=lambda seconds:bounded_wait(seconds,original_wait)
        return original_send(*args,**kwargs)
    stream_sender.send_frame=send

if __name__=='__main__':
    install()
    args=SimpleNamespace(reference_repo=HERE/'artifacts/moonbub-30fps-study',
        clip=HERE/'artifacts/media/Xonotic-0-8-2-gameplay.webm',loop=True,
        log=OUT/'candidate-video.jsonl',frames=600,fps=20,mbps=4,
        max_age_ms=200,quality=25,min_quality=25,packet_timing=True)
    start=time.perf_counter()
    cpu=time.process_time()
    result=run_reference(args)
    result['experiment']={'name':'local bounded 1ms spin-tail wait',
        'wall_seconds':time.perf_counter()-start,'process_cpu_seconds':time.process_time()-cpu,
        'hardware_contacted':False,'production_files_changed':False}
    (OUT/'candidate-result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)
