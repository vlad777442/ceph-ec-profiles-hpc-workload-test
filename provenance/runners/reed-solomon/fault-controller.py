#!/usr/bin/env python3
"""Authorized single-OSD fault with adaptive two-client repeated-pass analysis."""
import csv,json,os,shlex,signal,subprocess,sys,threading,time
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,'/users/vlad777/research/experiment-script-improvements/scripts')
import measure_ceph_recovery as recovery
recovery.CEPH_NAME='client.admin'
ROOT=Path(__file__).resolve().parent;PLAN=json.loads((ROOT/'PLAN.json').read_text())
TRIAL=ROOT.name;REPO='/users/vlad777/ADIOS2-Examples';REMOTE=REPO+'/results/'+TRIAL
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10']
state={'phase':'preflight','trial_id':TRIAL,'osd_id':3,'clients':['node12','node13']}
jobs=[];attempted=False;unit=None;host=None;watcher=None;watch_stop=threading.Event();watch_errors=[];repair={}

def utc():return datetime.now(timezone.utc).isoformat()
def atomic(path,data):
    t=path.with_suffix('.tmp');t.write_text(json.dumps(data,indent=2));t.replace(path)
def ssh(client,args,**kwargs):
    r=subprocess.run([*SSH,'root@'+client,shlex.join(args)],timeout=kwargs.pop('timeout',45),**kwargs)
    if r.returncode:raise RuntimeError(f'SSH operation failed on {client}: '+str(getattr(r,'stderr',None)))
    return r

def publish(phase,**values):
    state.update(phase=phase,updated_utc=utc(),**values);atomic(ROOT/'state.json',state)
    for client,proc,log in jobs:
        code="from pathlib import Path;import sys; p=Path("+repr(REMOTE+'/control.json')+");t=p.with_suffix('.tmp');t.write_text(sys.stdin.read());t.replace(p)"
        ssh(client,['python3','-c',code],input=json.dumps(state),text=True,capture_output=True)

def progress(client):
    code="from pathlib import Path;print(Path("+repr(REMOTE+'/progress.json')+").read_text())"
    return json.loads(ssh(client,['python3','-c',code],capture_output=True,text=True).stdout)

def stop_clients():
    for client,proc,log in jobs:
        if proc.poll() is not None:continue
        code=("import json,os,signal; r=json.load(open("+repr(REMOTE+'/progress.json')+")); "
              f"trial={TRIAL!r}; pid=r['runner_pid']; "
              "args=open('/proc/'+str(pid)+'/cmdline','rb').read().split(bytes([0])); "
              "os.kill(pid,signal.SIGTERM) if r['trial_id']==trial and trial.encode() in args else None")
        try:ssh(client,['python3','-c',code],capture_output=True)
        except Exception:pass
    for client,proc,log in jobs:
        try:proc.wait(timeout=60)
        except subprocess.TimeoutExpired:proc.terminate()
        log.close()

def interrupt(sig,frame):raise KeyboardInterrupt('Signal '+str(sig))
for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,interrupt)
error=None;complete=False;records=[]
try:
    cluster=json.loads(subprocess.check_output(['sudo','-n','ceph','status','-f','json'],text=True))
    atomic(ROOT/'baseline-ceph.json',cluster)
    if cluster['health']['status']!='HEALTH_OK':raise RuntimeError('Require HEALTH_OK')
    target=recovery.recovery_snapshot(3)
    if not target['osd']['up'] or not target['osd']['in'] or not target['all_clean']:raise RuntimeError('Target/baseline not healthy')
    location=json.loads(subprocess.check_output(['sudo','-n','ceph','osd','find','3','-f','json'],text=True))
    host=location.get('host') or location['crush_location']['host'];unit='ceph-osd@3.service'
    loaded=ssh(host,['systemctl','show',unit,'--property=LoadState','--property=ActiveState'],capture_output=True,text=True).stdout
    if 'LoadState=loaded' not in loaded or 'ActiveState=active' not in loaded:raise RuntimeError('Actual osd.3 unit not active')
    atomic(ROOT/'verified-control.json',{'host':host,'unit':unit})
    for client in PLAN['clients']:
        active=subprocess.run([*SSH,'root@'+client,'pgrep -x adios2-pdf-calc'],capture_output=True)
        if active.returncode!=1:raise RuntimeError('Client not idle/reachable: '+client)
        subprocess.run(['scp',str(ROOT/'run_sustained_analysis.py'),'root@'+client+':'+REPO+'/scripts/run_sustained_analysis.py'],check=True,capture_output=True)
        code="from pathlib import Path;import json; p=Path("+repr(REMOTE)+");p.mkdir(parents=True,exist_ok=False);(p/'control.json').write_text(json.dumps({'phase':'scheduled'}))"
        ssh(client,['sudo','-H','-u','vlad777','python3','-c',code])
    barrier=time.time()+90
    for client in PLAN['clients']:
        command=['sudo','-H','-u','vlad777','python3',REPO+'/scripts/run_sustained_analysis.py',
                 '--trial-dir',REMOTE,'--trial-id',TRIAL,'--control',REMOTE+'/control.json',
                 '--start-at',str(barrier),'--mpi-procs','8','--expected-steps','3600','--max-seconds',str(PLAN['max_workload_s'])]
        log=(ROOT/(client+'.log')).open('w')
        proc=subprocess.Popen([*SSH,'root@'+client,shlex.join(command)],stdout=log,stderr=subprocess.STDOUT)
        jobs.append((client,proc,log))
    publish('scheduled',start_at_epoch=barrier)
    fault_at=barrier+PLAN['fault_delay_s'];max_deadline=time.monotonic()+PLAN['max_workload_s']+120
    post_repair_deadline=None;stop_requested=False;last_phase='scheduled';next_poll=0
    while True:
        if time.monotonic()>max_deadline:raise TimeoutError('Maximum experiment duration exceeded')
        if time.monotonic()<next_poll:time.sleep(.2);continue
        next_poll=time.monotonic()+5
        for client,proc,log in jobs:
            code=proc.poll()
            if code is not None:
                if not stop_requested or code:raise RuntimeError(f'{client} ended before valid stop, exit={code}')
        if all(proc.poll() is not None for client,proc,log in jobs):break
        if time.time()<barrier:continue
        statuses={client:progress(client) for client,proc,log in jobs}
        osd_perf=json.loads(subprocess.check_output(['sudo','-n','ceph','osd','perf','-f','json'],text=True))
        with (ROOT/'osd-perf.jsonl').open('a') as f:f.write(json.dumps({'utc':utc(),'phase':state['phase'],'perf':osd_perf})+'\n')
        atomic(ROOT/'client-progress.json',statuses)
        if not attempted and time.time()>=fault_at:
            if any(s['phase']!='analysis' or not s['pass_pid'] for s in statuses.values()):raise RuntimeError('Both clients must be analyzing when fault is injected')
            publish('fault_requested',t_fault_requested=utc(),fault_workload_status=statuses)
            attempted=True
            ssh(host,['systemctl','stop',unit],capture_output=True)
            stopped=ssh(host,['systemctl','show',unit,'--property=ActiveState','--value'],capture_output=True,text=True).stdout.strip()
            if stopped not in ('inactive','failed'):raise RuntimeError('OSD service stop was not confirmed')
            publish('grace_period',t_fault_injected=utc())
            def observe():
                try:repair.update(recovery.watch_recovery(3,PLAN['recovery_timeout_s'],PLAN['controller_poll_interval_s'],str(ROOT/'recovery-events.jsonl'),stop_event=watch_stop))
                except Exception as e:watch_errors.append(str(e))
            watcher=threading.Thread(target=observe);watcher.start()
        if watch_errors:raise RuntimeError('Recovery observer failed: '+str(watch_errors))
        if watcher and not watcher.is_alive():
            if not repair.get('complete'):raise RuntimeError('Repair timed out under sustained load')
            if post_repair_deadline is None:
                atomic(ROOT/'recovery.json',repair)
                post_repair_deadline=time.monotonic()+PLAN['post_repair_load_s']
                publish('post_repair_analysis',repair_completed_utc=repair['events']['healthy'],post_repair_load_s=PLAN['post_repair_load_s'])
                last_phase='post_repair_analysis'
        if attempted and post_repair_deadline is None:
            snapshot=recovery.recovery_snapshot(3)
            phase='grace_period' if snapshot['osd']['in'] else 'fault_recovery'
            if phase!=last_phase:publish(phase);last_phase=phase
        if post_repair_deadline is not None and time.monotonic()>=post_repair_deadline and not stop_requested:
            publish('finish_current_pass',stop_after_pass=True,stop_requested_utc=utc())
            stop_requested=True
    for client,proc,log in jobs:
        log.close();local=ROOT/'artifacts'/client;local.mkdir(parents=True)
        subprocess.run(['scp','-r','root@'+client+':'+REMOTE,str(local)],check=True,capture_output=True)
        r=json.loads(next(local.rglob('results.json')).read_text())
        if r['trial_status']!='complete' or not r['passes']:raise RuntimeError('Workload validation failed on '+client)
        if datetime.fromisoformat(r['t_analysis_end'])<=datetime.fromisoformat(repair['events']['healthy']):raise RuntimeError('Repair did not finish within workload window')
        if (datetime.fromisoformat(r['t_analysis_end'])-datetime.fromisoformat(repair['events']['healthy'])).total_seconds()<PLAN['post_repair_load_s']:raise RuntimeError('Insufficient post-repair load window')
        records.append(r)
    complete=True
except (Exception,KeyboardInterrupt) as e:
    error=str(e)
    try:publish('failed',abort=True,error=error)
    except Exception:atomic(ROOT/'state.json',{'phase':'failed','error':error})
    stop_clients()
finally:
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,signal.SIG_IGN)
    watch_stop.set()
    if watcher:watcher.join(timeout=40)
    if attempted:
        try:
            # Always restart the exact verified OSD unit, even after partial stop failure.
            ssh(host,['systemctl','start',unit],capture_output=True)
            subprocess.run(['sudo','-n','ceph','osd','in','3'],check=True,capture_output=True)
            restoration=recovery.watch_recovery(3,PLAN['recovery_timeout_s'],5,str(ROOT/'restoration-events.jsonl'),require_restored=True)
            atomic(ROOT/'restoration.json',restoration)
            if not restoration['complete']:raise RuntimeError('Restoration timed out')
        except Exception as e:error=(error or '')+' Restoration error: '+str(e);complete=False
    try:
        final=json.loads(subprocess.check_output(['sudo','-n','ceph','status','-f','json'],text=True));atomic(ROOT/'final-ceph.json',final)
        if final['health']['status']!='HEALTH_OK':error=(error or '')+' Final cluster not HEALTH_OK';complete=False
    except Exception as e:error=(error or '')+' Final status failed: '+str(e);complete=False
    summary={'complete':complete,'error':error,'repair':repair,'workloads':[{'host':r['hostname'],'passes':len(r['passes']),'duration_s':r['duration_analysis_s'],'logical_input_bytes':r['logical_input_bytes'],'logical_mib_s':r['logical_throughput_mib_s'],'repair_within_workload':True,'post_repair_s':(datetime.fromisoformat(r['t_analysis_end'])-datetime.fromisoformat(repair['events']['healthy'])).total_seconds()} for r in records]}
    atomic(ROOT/'summary.json',summary)
    if complete:
        for client in PLAN['clients']:
            path=next((ROOT/'artifacts'/client).rglob('results.json'));r=json.loads(path.read_text())
            r.update(osd_id=3,no_fault=False,t_fault_injected=state['t_fault_injected'],pool_label='grayscott-900g RS(6,4), OSD failure domain')
            for k,v in repair['events'].items():r['t_'+k]=v
            r['duration_grace_period_s']=(datetime.fromisoformat(r['t_marked_out'])-datetime.fromisoformat(r['t_down'])).total_seconds()
            if r.get('t_recovering'):r['duration_recovery_s']=(datetime.fromisoformat(r['t_healthy'])-datetime.fromisoformat(r['t_recovering'])).total_seconds()
            atomic(path,r)
            plotted=subprocess.run(['python3',str(ROOT/'plot_sustained_io.py'),str(path.parent/'perf.csv'),str(path),str(path.parent/'fault_io.png')],capture_output=True,text=True)
            if plotted.returncode:atomic(ROOT/(client+'-plot-error.json'),{'error':plotted.stderr})
        atomic(ROOT/'state.json',dict(state,phase='complete',completed_utc=utc()))
    else:atomic(ROOT/'state.json',dict(state,phase='failed',error=error))
    lines=['# Sustained two-client osd.3 fault trial','', 'Status: '+('COMPLETE' if complete else 'FAILED / INCOMPLETE')+'.','',
           'Repeated full passes over the same 900 GiB input; 8 MPI ranks per client; natural caches. The controller requested a stop 15 minutes after data repair completed; each client then finished its current full pass. Pass boundaries and brief validation/relaunch gaps are recorded. OSD restoration occurs after the workload ends.','']
    for r in summary['workloads']:lines.append(f"- {r['host']}: {r['passes']} passes, {r['duration_s']/60:.1f} minutes, {r['post_repair_s']/60:.1f} minutes after repair completed.")
    if error:lines.extend(['','Error: '+error])
    lines.extend(['','See summary.json, recovery.json, restoration.json and artifacts/ for raw metrics, pass logs, validated outputs and figures. An equivalent repeated-pass no-fault control is needed for paper comparisons.'])
    (ROOT/'REPORT.md').write_text('\n'.join(lines)+'\n')
sys.exit(0 if complete else 1)
