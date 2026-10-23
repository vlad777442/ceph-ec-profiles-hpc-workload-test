#!/usr/bin/env python3
"""Exactly three sequential two-client no-fault controls, three passes per client.
No OSD control, cache dropping, dataset deletion or pool changes.
"""
import json,shlex,signal,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent;PLAN=json.loads((ROOT/'PLAN.json').read_text())
REPO='/users/vlad777/ADIOS2-Examples';SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10']
jobs=[];records=[];current=None;remote=None;failure=None

def utc():return datetime.now(timezone.utc).isoformat()
def atomic(p,data):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(data,indent=2));t.replace(p)
def ssh(host,args,**kwargs):
 r=subprocess.run([*SSH,'root@'+host,shlex.join(args)],timeout=kwargs.pop('timeout',45),**kwargs)
 if r.returncode:raise RuntimeError('SSH failed on '+host+': '+str(getattr(r,'stderr',None)))
 return r

def acceptable_pg_states(pg):
 allowed={"active","clean","scrubbing","deep"}
 states=pg.get("pgs_by_state",[])
 return pg.get("num_pgs",0)>0 and sum(s["count"] for s in states)==pg["num_pgs"] and all({"active","clean"}<=set(s["state_name"].split("+"))<=allowed for s in states)

def cluster():
 r=json.loads(subprocess.check_output(['sudo','-n','ceph','status','-f','json'],text=True))
 pg=r['pgmap'];clean=sum(s['count'] for s in pg['pgs_by_state'] if s['state_name']=='active+clean')
 if r['health']['status']!='HEALTH_OK' or r['osdmap']['num_up_osds']!=24 or r['osdmap']['num_in_osds']!=24 or not acceptable_pg_states(pg):raise RuntimeError('Require HEALTH_OK, all 24 up/in, and active clean PGs; scrubbing is recorded')
 return r

def stop_clients():
 for host,proc,log in jobs:
  if proc.poll() is not None:continue
  code=("import json,os,signal; r=json.load(open("+repr(remote+'/progress.json')+")); "
        f"trial={current!r};pid=r['runner_pid']; "
        "args=open('/proc/'+str(pid)+'/cmdline','rb').read().split(bytes([0])); "
        "os.kill(pid,signal.SIGTERM) if r['trial_id']==trial and trial.encode() in args else None")
  try:ssh(host,['python3','-c',code],capture_output=True)
  except Exception:pass
 for host,proc,log in jobs:
  try:proc.wait(timeout=60)
  except subprocess.TimeoutExpired:proc.terminate()
  log.close()

def interrupt(sig,frame):raise KeyboardInterrupt('Signal '+str(sig))
for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,interrupt)
try:
 for trial_number in range(1,PLAN['trials']+1):
  current='rep3-'+ROOT.parent.name+'-nofault'+f'-t{trial_number}';remote=REPO+'/results/'+current
  local=ROOT/f'trial-{trial_number:02d}';local.mkdir(exist_ok=False);jobs=[]
  atomic(local/'baseline-ceph.json',cluster())
  (local/'osd-df-before.json').write_text(subprocess.check_output(['sudo','-n','ceph','osd','df','-f','json'],text=True))
  for host in PLAN['clients']:
   active=subprocess.run([*SSH,'root@'+host,'pgrep -x adios2-pdf-calc'],capture_output=True)
   if active.returncode!=1:raise RuntimeError('Client not idle/reachable: '+host)
   subprocess.run(['scp',str(ROOT.parent.parent/'runner'/'run_replicated_workload.py'),'root@'+host+':'+REPO+'/scripts/run_replicated_workload.py'],check=True,capture_output=True)
   code="from pathlib import Path;import json; p=Path("+repr(remote)+");p.mkdir(parents=True,exist_ok=False);(p/'control.json').write_text(json.dumps({'phase':'analysis'}))"
   ssh(host,['sudo','-H','-u','vlad777','python3','-c',code])
  # Initial worker preflight is strict; wait for no current scrub before launch.
  initial_deadline=time.monotonic()+1800
  while any(s['state_name']!='active+clean' for s in cluster()['pgmap']['pgs_by_state']):
   if time.monotonic()>initial_deadline:raise TimeoutError('Initial scrub did not finish')
   time.sleep(5)
  barrier=time.time()+PLAN['shared_start_lead_s']
  atomic(ROOT/'state.json',{'phase':'running','trial':trial_number,'completed_trials':len(records),'current_trial':current,'start_at_epoch':barrier,'updated_utc':utc()})
  for host in PLAN['clients']:
   args=['sudo','-H','-u','vlad777','python3',REPO+'/scripts/run_replicated_workload.py',
         '--trial-dir',remote,'--trial-id',current,'--control',remote+'/control.json','--start-at',str(barrier),
         '--passes','3','--mpi-procs','8','--expected-steps','3600','--max-seconds',str(PLAN['max_workload_s'])]
   log=(local/(host+'.log')).open('w')
   proc=subprocess.Popen([*SSH,'root@'+host,shlex.join(args)],stdout=log,stderr=subprocess.STDOUT)
   jobs.append((host,proc,log))
  deadline=time.monotonic()+PLAN['max_workload_s']+300
  while any(proc.poll() is None for host,proc,log in jobs):
   if time.monotonic()>deadline:raise TimeoutError('Trial exceeded time limit')
   for host,proc,log in jobs:
    if proc.poll() not in (None,0):raise RuntimeError('Worker failed on '+host)
   if time.time()>=barrier:
    status=cluster()
    with (local/'cluster-state.jsonl').open('a') as f:f.write(json.dumps({'utc':utc(),'status':status})+'\n')
    perf=json.loads(subprocess.check_output(['sudo','-n','ceph','osd','perf','-f','json'],text=True))
    with (local/'osd-perf.jsonl').open('a') as f:f.write(json.dumps({'utc':utc(),'phase':'no_fault_analysis','perf':perf})+'\n')
    progress={}
    for host,proc,log in jobs:
     code="from pathlib import Path;print(Path("+repr(remote+'/progress.json')+").read_text())"
     progress[host]=json.loads(ssh(host,['python3','-c',code],capture_output=True,text=True).stdout)
    atomic(local/'client-progress.json',progress)
   time.sleep(5)
  trial_records=[]
  for host,proc,log in jobs:
   log.close();destination=local/'artifacts'/host;destination.mkdir(parents=True)
   subprocess.run(['scp','-r','root@'+host+':'+remote,str(destination)],check=True,capture_output=True)
   path=next(destination.rglob('results.json'));r=json.loads(path.read_text())
   if r['trial_status']!='complete' or not r['no_fault'] or r['external_fault'] or len(r['passes'])!=3 or r['logical_input_bytes']!=2700*1024**3:raise RuntimeError('Invalid three-pass no-fault result: '+host)
   plotting=subprocess.run(['python3',str(ROOT/'plot_io.py'),str(path.parent/'perf.csv'),str(path),str(path.parent/'nofault_io.png')],capture_output=True,text=True)
   if plotting.returncode:(local/(host+'-plot-error.txt')).write_text(plotting.stderr)
   trial_records.append({'host':host,'duration_s':r['duration_analysis_s'],'passes':len(r['passes']),'logical_mib_s':r['logical_throughput_mib_s'],'start_utc':r['t_analysis_start'],'end_utc':r['t_analysis_end']})
  # Save all observed scrub windows; do not silently discard maintenance samples.
  snapshots=[json.loads(line) for line in (local/'cluster-state.jsonl').read_text().splitlines()]
  scrub_samples=[{'utc':row['utc'],'pgs_by_state':row['status']['pgmap']['pgs_by_state']} for row in snapshots if any('scrubbing' in s['state_name'] for s in row['status']['pgmap']['pgs_by_state'])]
  atomic(local/'scrubbing-observations.json',{'samples':scrub_samples,'note':'Normal active/clean scrubbing is allowed and recorded; account for it in paper analysis.'})
  atomic(local/'final-ceph.json',cluster())
  starts=[datetime.fromisoformat(r['start_utc']).timestamp() for r in trial_records];ends=[datetime.fromisoformat(r['end_utc']).timestamp() for r in trial_records]
  record={'trial':trial_number,'clients':trial_records,'start_skew_s':max(starts)-min(starts),'scrub_observation_count':len(scrub_samples),'aggregate_logical_mib_s':5400*1024/(max(ends)-min(starts))}
  atomic(local/'summary.json',record);records.append(record)
  atomic(ROOT/'summary.json',{'complete':False,'completed_trials':records})
except (Exception,KeyboardInterrupt) as e:
 failure=str(e)
 for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,signal.SIG_IGN)
 stop_clients()
finally:
 complete=failure is None and len(records)==3
 atomic(ROOT/'summary.json',{'complete':complete,'error':failure,'trials':records})
 atomic(ROOT/'state.json',{'phase':'complete' if complete else 'failed','completed_trials':len(records),'error':failure,'finished_utc':utc()})
 lines=['# Three-pass two-client no-fault controls','', 'Status: '+('COMPLETE' if complete else 'FAILED / INCOMPLETE')+'.','',
        '| Trial | Client | Full passes | Workload (min) | Logical throughput (MiB/s) |','|---|---|---:|---:|---:|']
 for trial in records:
  for c in trial['clients']:lines.append(f"| {trial['trial']} | {c['host']} | {c['passes']} | {c['duration_s']/60:.1f} | {c['logical_mib_s']:.1f} |")
 if failure:lines.extend(['','Error: '+failure])
 lines.extend(['','Three independent sequential no-fault trials. Each client reads the fixed 900 GiB dataset three times with 8 ranks and 100 bins, validating between passes. Natural caches; no cache dropping. Scrub windows are retained in cluster-state.jsonl and scrubbing-observations.json. Each trial folder contains per-client plots, perf.csv, pass logs, validated application CSVs and metadata. All outputs are retained.'])
 (ROOT/'REPORT.md').write_text('\n'.join(lines)+'\n')
sys.exit(0 if failure is None and len(records)==3 else 1)
