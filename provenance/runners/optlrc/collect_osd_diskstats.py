"""Read-only raw OSD-host disk, CPU and network counters every five seconds."""
from pathlib import Path
import subprocess,signal,time,sys,os
ROOT=Path(sys.argv[1]);ROOT.mkdir(exist_ok=True)
CODE="""from pathlib import Path
import json,time
while True:
 print(json.dumps({'epoch':time.time(),'diskstats':Path('/proc/diskstats').read_text(),'cpu':Path('/proc/stat').read_text().splitlines()[0],'network':Path('/proc/net/dev').read_text()}),flush=True)
 time.sleep(5)
"""
procs=[]
def stop(sig,frame):raise KeyboardInterrupt()
for sig in [signal.SIGINT,signal.SIGTERM]:signal.signal(sig,stop)
try:
 import shlex
 for i in range(12):
  h='node'+str(i);out=(ROOT/(h+'.jsonl')).open('x');err=(ROOT/(h+'.stderr')).open('x')
  command=['python3','-u','-c',CODE] if i==0 else ['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','root@'+h,shlex.join(['python3','-u','-c',CODE])]
  p=subprocess.Popen(command,stdout=out,stderr=err,start_new_session=True);procs.append((p,out,err))
 while True:
  if any(p.poll() is not None for p,_,_ in procs):raise RuntimeError('OSD host telemetry disconnected')
  time.sleep(2)
except KeyboardInterrupt:pass
finally:
 for p,out,err in procs:
  if p.poll() is None:os.killpg(p.pid,signal.SIGTERM)
 for p,out,err in procs:
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL)
  out.close();err.close()
