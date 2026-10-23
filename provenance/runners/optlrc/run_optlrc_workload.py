#!/usr/bin/env python3
"""Repeated full analysis passes for a controller-owned recovery experiment.
This worker never changes OSD state. It completes exactly the requested full passes.
"""
import argparse,csv,json,os,signal,subprocess,sys,threading,time
from pathlib import Path
import run_optlrc_storage as common

def atomic(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2));temp.replace(path)
def control(path):
    value=json.loads(path.read_text())
    if value.get('abort'):raise RuntimeError('Controller aborted workload')
    return value

def full_pass_counts(csv_path,expected):
    with csv_path.open() as f:rows=list(csv.DictReader(f))
    if len(rows)!=expected:raise RuntimeError('Incomplete application CSV')
    return sum(int(r['global_data_read_bytes']) for r in rows),sum(int(r['global_data_written_bytes']) for r in rows)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--external-fault',action='store_true')
    p.add_argument('--protection',choices=['ec','replicated'],default='ec')
    p.add_argument('--failure-domain',choices=['osd','host'],default='osd')
    p.add_argument('--rbd-mount',default='/mnt/grayscott-optlrc')
    p.add_argument('--rbd-name',default='client.optlrc-'+common.socket.gethostname().split('.')[0])
    p.add_argument('--passes',type=int,default=3)
    p.add_argument('--trial-dir',required=True);p.add_argument('--trial-id',required=True)
    p.add_argument('--control',required=True);p.add_argument('--start-at',type=float,required=True)
    p.add_argument('--input',default='/mnt/grayscott-optlrc/gray-scott/gs-900g.bp')
    p.add_argument('--expected-steps',type=int,default=3600);p.add_argument('--mpi-procs',type=int,default=8)
    p.add_argument('--max-seconds',type=float,default=21600);p.add_argument('--monitor-interval',type=float,default=3)
    p.add_argument('--expected-data-pool',default='grayscott-optlrc-data');a=p.parse_args()
    if min(a.passes,a.expected_steps,a.mpi_procs,a.max_seconds,a.monitor_interval)<=0:p.error('Positive counts/timing required')
    out=Path(a.trial_dir);out.mkdir(parents=True,exist_ok=True);marker=Path(a.control)
    output_prefix=a.rbd_mount+'/analysis/'+a.trial_id+'-'+common.socket.gethostname().split('.')[0]
    args=common.parse_args(['--no-fault','--output',output_prefix+'-pass-001.bp','--input',a.input,
                           '--expected-steps',str(a.expected_steps),'--mpi-procs',str(a.mpi_procs),
                           '--expected-data-pool',a.expected_data_pool,'--monitor-interval',str(a.monitor_interval),
                           '--protection',a.protection,'--failure-domain',a.failure_domain,'--rbd-mount',a.rbd_mount]+(['--rbd-name',a.rbd_name] if a.rbd_name else []))
    baseline=common.preflight(args)
    result={'schema_version':3,'runner_pid':os.getpid(),'trial_id':a.trial_id,'trial_status':'running',
            'no_fault':not a.external_fault,'external_fault':a.external_fault,'protection':a.protection,'failure_domain':a.failure_domain,'expected_passes':a.passes,'bins':100,'hostname':common.socket.gethostname(),'mpi_procs':a.mpi_procs,
            'input':a.input,'baseline':baseline,'metadata':common.metadata(args),'worker_sha256':common.digest(__file__),
            'cache_policy':'natural across repeated passes; no cache dropping','passes':[],
            'stop_policy':'exactly requested full passes, with validation between passes','output_dir':str(out),
            'pool_label':'OptLRC(n=10,k=6,r=4), min_size=9, OSD failure domain'}
    progress={'runner_pid':os.getpid(),'trial_id':a.trial_id,'phase':'scheduled','completed_passes':0,'pass_pid':None}
    atomic(out/'progress.json',progress);atomic(out/'results.json',result)
    proc=[None];phase=['scheduled'];stop=threading.Event();ready=threading.Event();errors=[];monitor=None
    def interrupt(sig,frame):raise KeyboardInterrupt('Signal '+str(sig))
    for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,interrupt)
    rc=1;start=None
    try:
        monitor=threading.Thread(target=common.perf_monitor,args=(args,Path(baseline['mapping']['device']).name,proc,stop,out/'perf.csv',phase,errors,ready))
        monitor.start()
        if not ready.wait(30) or errors:raise RuntimeError('Monitor startup failed: '+str(errors))
        if time.time()>a.start_at:raise RuntimeError('Missed scheduled start')
        while time.time()<a.start_at:
            control(marker)
            if errors:raise RuntimeError('Monitor failed')
            time.sleep(.1)
        start=time.monotonic();result['t_analysis_start']=common.utc();progress['workload_start_utc']=result['t_analysis_start'];atomic(out/'progress.json',progress);atomic(out/'results.json',result)
        index=0
        while True:
            requested=control(marker)
            if index>=a.passes:break
            if time.monotonic()-start>a.max_seconds:raise TimeoutError('Maximum workload duration exceeded')
            if common.shutil.disk_usage(a.rbd_mount).free<20*1024**3:raise RuntimeError('Require 20 GiB output headroom')
            index+=1;output=output_prefix+f'-pass-{index:03d}.bp'
            if Path(output).exists() or Path(output+'_throughput.csv').exists():raise RuntimeError('Output already exists')
            command=['mpirun','--bind-to','core','--report-bindings','-n',str(a.mpi_procs),args.binary,a.input,output,str(args.bins)]
            if os.geteuid()==0:command.insert(1,'--allow-run-as-root')
            env=os.environ.copy();env['LD_LIBRARY_PATH']=common.ADIOS2_LIB+':'+env.get('LD_LIBRARY_PATH','')
            record={'pass_index':index,'output':output,'start_utc':common.utc()};pass_start=time.monotonic()
            progress.update(phase='analysis',pass_index=index,pass_start_utc=record['start_utc'])
            phase[0]=requested.get('phase','analysis')
            with (out/f'pass-{index:03d}.log').open('x') as log:
                proc[0]=subprocess.Popen(command,cwd=common.GS_DIR,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                progress['pass_pid']=proc[0].pid;atomic(out/'progress.json',progress)
                while True:
                    try:code=proc[0].wait(timeout=.2);break
                    except subprocess.TimeoutExpired:pass
                    requested=control(marker);phase[0]=requested.get('phase','analysis')
                    if errors:raise RuntimeError('Monitor failed: '+str(errors))
                    if time.monotonic()-start>a.max_seconds:raise TimeoutError('Workload timed out before repair/finish')
                record.update(end_utc=common.utc(),duration_s=time.monotonic()-pass_start,exit_code=code)
                if code:raise RuntimeError('MPI pass failed: '+str(code))
            progress.update(phase='validating',pass_pid=None);atomic(out/'progress.json',progress)
            counts=dict(common.bp_steps(output,args.bpls,['U/pdf','V/pdf']))
            if any(n!=a.expected_steps for n in counts.values()):raise RuntimeError('Output step count mismatch')
            sample=common.checked([args.bpls,'-d','-s',f'{a.expected_steps-1},0,0','-c','1,1,1',output,'U/pdf','V/pdf'],timeout=120)
            if common.re.search(r'(?i)\b(?:nan|inf|infinity)\b',sample):raise RuntimeError('Nonfinite output sample')
            source=Path(output+'_throughput.csv');copied=out/f'pass-{index:03d}-throughput.csv';common.shutil.copy2(source,copied)
            read_bytes,write_bytes=full_pass_counts(copied,a.expected_steps)
            if a.expected_steps==3600 and read_bytes!=900*1024**3:raise RuntimeError('Logical input-byte total mismatch')
            record.update(output_steps=counts,logical_input_bytes=read_bytes,logical_output_bytes=write_bytes,logical_mib_s=read_bytes/common.MIB/record['duration_s'],throughput_csv=str(copied),final_step_sample=sample)
            result['passes'].append(record);progress['completed_passes']=index
            atomic(out/'results.json',result);atomic(out/'progress.json',progress)
        result.update(trial_status='complete',t_analysis_end=common.utc(),duration_analysis_s=time.monotonic()-start,
                      logical_input_bytes=sum(r['logical_input_bytes'] for r in result['passes']))
        result['logical_throughput_mib_s']=result['logical_input_bytes']/common.MIB/result['duration_analysis_s']
        result['stop_control']=control(marker);rc=0
    except (Exception,KeyboardInterrupt) as e:
        result.update(trial_status='failed',error=str(e),t_analysis_end=common.utc())
    finally:
        for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,signal.SIG_IGN)
        try:common.terminate_process(proc[0])
        except Exception as e:result['cleanup_error']=str(e);rc=1
        stop.set()
        if monitor:monitor.join(timeout=10)
        if errors or (monitor and monitor.is_alive()):result['monitor_errors']=errors or ['monitor did not stop'];rc=1
        if rc:result['trial_status']='failed'
        result['exit_code']=rc;atomic(out/'results.json',result)
        progress.update(phase='workload-complete' if rc==0 else 'failed',pass_pid=None)
        atomic(out/'progress.json',progress)
    return rc
if __name__=='__main__':sys.exit(main())
