#!/usr/bin/env python3
"""Authorized four-trial OptLRC extension; fail closed on audit or trial error."""
from pathlib import Path
from datetime import datetime,timezone
import concurrent.futures,fcntl,hashlib,json,os,shlex,signal,subprocess,sys,time
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parent;REPO=Path('/users/vlad777/ceph-ec-profiles-hpc-workload-test')
sys.path.insert(0,str(BASE/'runner'))
from health_policy import acceptable_health
from kernel_guard import KernelGuard
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10'];child=None;sampler=None;completed=[];guard=None
def utc():return datetime.now(timezone.utc).isoformat()
def atomic(p,value):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(value,indent=2)+'\n');t.replace(p)
def state(phase,**kw):
 atomic(ROOT/'state.json',{'phase':phase,'updated_utc':utc(),'pid':os.getpid(),'completed_stages':completed,**kw});print(utc(),phase,kw,flush=True)
def run(args,timeout=60):return subprocess.check_output(args,text=True,stderr=subprocess.PIPE,timeout=timeout)
def ssh(host,args,timeout=120):return run([*SSH,'root@'+host,shlex.join(args)],timeout)
def ceph(*args):return json.loads(run(['sudo','-n','ceph',*args,'-f','json']))
def healthy():
 s=ceph('status');o=s['osdmap'];pg=s['pgmap']
 return acceptable_health(s) and o['num_up_osds']==o['num_in_osds']==24 and all(x['state_name']=='active+clean' for x in pg['pgs_by_state'])
def wait_healthy():
 until=time.monotonic()+1800
 while not healthy():
  if time.monotonic()>until:raise RuntimeError('Cluster not clean with all 24 OSDs up/in before deadline')
  time.sleep(5)
def interrupt(sig,frame):raise KeyboardInterrupt('Campaign interrupted')
for sig in [signal.SIGTERM,signal.SIGINT]:signal.signal(sig,interrupt)
lock=(BASE/'extension-campaign.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
EXPECTED=BASE/'preparation-20261021T222232Z/migration/verification/destination-manifest.jsonl'
HASH_CODE="""from pathlib import Path
import hashlib,json
root=Path('/mnt/grayscott-optlrc/gray-scott/gs-900g.bp')
for p in sorted(root.rglob('*')):
 if not p.is_file():continue
 before=p.stat();h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(16*1024*1024),b''):h.update(chunk)
 after=p.stat();assert before.st_size==after.st_size and before.st_mtime_ns==after.st_mtime_ns
 print(json.dumps({'path':str(p.relative_to(root)),'bytes':before.st_size,'sha256':h.hexdigest()}),flush=True)
"""
def verify_inputs(label):
 expected=[json.loads(x) for x in EXPECTED.read_text().splitlines()]
 def check(host):
  dest=ROOT/(host+'-'+label+'-input-manifest.jsonl')
  with dest.open('x') as log:
   proc=subprocess.Popen([*SSH,'root@'+host,shlex.join(['python3','-u','-c',HASH_CODE])],stdout=log,stderr=subprocess.PIPE,text=True)
   try:
    _,err=proc.communicate(timeout=21600)
    if proc.returncode:raise RuntimeError(host+' input hash failed: '+err)
   except BaseException:
    if proc.poll() is None:proc.terminate();proc.wait(timeout=20)
    raise
  assert [json.loads(x) for x in dest.read_text().splitlines()]==expected,host+' checksum mismatch'
  print(utc(),host,label,'input hashes verified',flush=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(check,['node12','node13']))
try:
 for host in ['node12','node13']:
  pilot=json.loads((BASE/'five-trial-extension-20261101/diagnostics'/(host+'-bp5-pilot.json')).read_text());assert pilot['pass'] and not pilot['kernel_errors']
  direct=json.loads((BASE/'five-trial-extension-20261101/diagnostics'/(host+'-write-pilot-verified.json')).read_text());assert direct['pass'] and direct['bytes']==8*1024**3
  assert ssh(host,['cat','/proc/sys/vm/min_free_kbytes']).strip()=='524288','Repair memory policy missing'
 guard=KernelGuard(ROOT);guard.start()
 state('configuration_audit')
 reference=json.loads((REPO/'configurations/optlrc.json').read_text())
 current=ceph('status');atomic(ROOT/'ceph-before.json',current)
 assert acceptable_health(current),'Unexpected cluster warning'
 assert current['pgmap']['num_pgs']==832 and current['pgmap']['num_pools']==13,'PG/pool topology changed'
 pool=ceph('osd','pool','get','grayscott-optlrc-data','all');atomic(ROOT/'pool-before.json',pool)
 for key in ['size','min_size','pg_num','pgp_num','crush_rule','erasure_code_profile','fast_read','pg_autoscale_mode','allow_ec_overwrites']:
  assert pool[key]==reference['data_pool'][key],('pool mismatch',key,pool.get(key))
 ec=ceph('osd','erasure-code-profile','get','optlrc-10-6-4-osd');assert ec==reference['ec_profile'],'EC profile changed'
 atomic(ROOT/'ec-profile.json',ec)
 rule=ceph('osd','crush','rule','dump','grayscott-optlrc-data');atomic(ROOT/'crush-rule.json',rule)
 assert any(x.get('type')=='osd' and 'choose' in x['op'] for x in rule['steps']),'OSD failure domain required'
 assert run(['sudo','-n','ceph','config','get','osd','mon_osd_down_out_interval']).strip()=='600'
 atomic(ROOT/'osd-df-before.json',ceph('osd','df'));atomic(ROOT/'config-dump-before.json',ceph('config','dump'))
 plugin='f9799e0bb8eed7cdbe5fd39b254d8b298a694a2e4af8d2f0e643bb5dc576d65f'
 def check_plugin(i):
  h='node'+str(i);cmd=['sha256sum','/usr/lib/ceph/erasure-code/libec_optlrc.so']
  value=(run(cmd) if i==0 else ssh(h,cmd)).split()[0];assert value==plugin,h+' plugin changed';return h,value
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:atomic(ROOT/'plugin-hashes.json',dict(pool.map(check_plugin,range(12))))
 for host in ['node12','node13']:
  code="""from pathlib import Path
import hashlib,json,os,shutil,subprocess,time
repo=Path('/users/vlad777/ADIOS2-Examples');mount=Path('/mnt/grayscott-optlrc')
r={'epoch':time.time(),'free_bytes':shutil.disk_usage(mount).free,'hashes':{}}
for name in ['build-grayscott/adios2-pdf-calc','scripts/run_optlrc_storage.py','adios2.xml']:
 r['hashes'][name]=hashlib.sha256((repo/name).read_bytes()).hexdigest()
r['vm_min_free_kbytes']=Path('/proc/sys/vm/min_free_kbytes').read_text().strip()
r['buddyinfo']=Path('/proc/buddyinfo').read_text()
r['mount']=json.loads(subprocess.check_output(['findmnt','-J','-M',str(mount)],text=True))
r['mappings']=json.loads(subprocess.check_output(['rbd','device','list','--format','json'],text=True))
r['mpi']=subprocess.check_output(['mpirun','--version'],text=True)
assert subprocess.run(['pgrep','-x','adios2-pdf-calc'],capture_output=True).returncode==1,'Workload already running'
assert subprocess.run(['pgrep','-f','[r]un_optlrc_workload.py'],capture_output=True).returncode==1,'Worker already running'
print(json.dumps(r))
"""
  before=time.time();info=json.loads(ssh(host,['python3','-c',code]));after=time.time()
  assert abs(info['epoch']-(before+after)/2)<2,'Client clock skew'
  assert info['vm_min_free_kbytes']=='524288','Client memory reserve changed'
  assert info['free_bytes']>100*1024**3,'Require >100GiB free for four output sets'
  assert info['hashes']['build-grayscott/adios2-pdf-calc']==reference['software']['binary_sha256'],'Binary changed'
  assert info['hashes']['scripts/run_optlrc_storage.py']==reference['software']['script_sha256'],'Storage runner changed'
  assert info['hashes']['adios2.xml']==reference['software']['xml_sha256'],'XML changed'
  assert '4.1.2' in info['mpi'],'MPI version changed'
  atomic(ROOT/(host+'-audit.json'),info)
  mappings=info['mappings'];mappings=list(mappings.values()) if isinstance(mappings,dict) else mappings
  source=info['mount']['filesystems'][0]['source'];mapping=next(x for x in mappings if x['device']==source)
  expected_image='dataset-900g' if host=='node12' else 'dataset-900g-node13'
  assert mapping['pool']=='grayscott-optlrc-meta' and mapping['name']==expected_image,'Unexpected mapped image'
  image=json.loads(run(['sudo','-n','rbd','info',mapping['pool']+'/'+mapping['name'],'--format','json']))
  assert image['data_pool']=='grayscott-optlrc-data' and image['object_size']==33554432 and image['size']==1234803097600
  atomic(ROOT/(host+'-image.json'),image)
  worker_hash=ssh(host,['sha256sum','/users/vlad777/ADIOS2-Examples/scripts/run_optlrc_workload.py']).split()[0]
  assert worker_hash==hashlib.sha256((BASE/'runner/run_optlrc_workload.py').read_bytes()).hexdigest(),'Worker source changed'
 state('verifying_input_checksums',note='Full read-only SHA256 of both inputs; workloads begin only after both match the original manifest')
 verify_inputs('before');guard.check()
 atomic(ROOT/'preflight-passed.json',{'utc':utc(),'configuration_matches':True,'both_input_sha256_match':True,'cache_note':'Natural cache policy; full input integrity scan before campaign recorded explicitly'})
 state('waiting_for_clean_cluster');wait_healthy()
 telemetry=ROOT/'osd-host-telemetry';sampler=subprocess.Popen(['python3',str(BASE/'runner/collect_osd_diskstats.py'),str(telemetry)])
 until=time.monotonic()+45
 while not all((telemetry/f'node{i}.jsonl').exists() and (telemetry/f'node{i}.jsonl').stat().st_size>0 for i in range(12)):
  if sampler.poll() is not None or time.monotonic()>until:raise RuntimeError('OSD telemetry startup failed')
  time.sleep(1)
 for condition,number in [('no-fault',5),('fault-osd3',5),('no-fault',6),('fault-osd3',6)]:
  guard.check()
  state('waiting_for_clean_cluster',next_condition=condition,next_trial=number);wait_healthy()
  controller=ROOT/'no-fault/controller.py' if condition=='no-fault' else ROOT/'fault-osd3'/f'trial-{number:02d}'/'controller.py'
  command=['python3',str(controller)]+([str(number)] if condition=='no-fault' else [])
  state('running',condition=condition,trial=number,controller=str(controller))
  with (ROOT/f'{condition}-{number:02d}-controller.log').open('x') as log:
   child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
   while child.poll() is None:
    guard.check()
    if sampler.poll() is not None:raise RuntimeError('OSD telemetry failed')
    time.sleep(2)
   if child.returncode:raise RuntimeError('Controller failed: '+str(controller))
  guard.check()
  folder=ROOT/condition/f'trial-{number:02d}'
  for host in ['node12','node13']:
   source=next((folder/'artifacts'/host).rglob('results.json')).parent
   r=json.loads((source/'results.json').read_text());assert r['trial_status']=='complete' and len(r['passes'])==3 and r['logical_input_bytes']==2700*1024**3
   (folder/host).symlink_to(source.relative_to(folder))
  if condition=='fault-osd3':
   summary=json.loads((folder/'summary.json').read_text());assert summary['complete'] and all(x['repair_within_workload'] for x in summary['workloads'])
  completed.append({'condition':condition,'trial':number,'folder':str(folder)})
  atomic(ROOT/'completed-trials.json',completed)
 if sampler and sampler.poll() is None:sampler.terminate();sampler.wait(timeout=30);sampler=None
 state('verifying_final_input_checksums');verify_inputs('after');guard.check();wait_healthy()
 state('complete',new_trials_completed=4,total_selected_trials_per_condition=5,input_integrity_passed_both_clients=True)
except BaseException as e:
 for sig in [signal.SIGTERM,signal.SIGINT]:signal.signal(sig,signal.SIG_IGN)
 if child and child.poll() is None:
  child.terminate()
  try:child.wait(timeout=18000)
  except subprocess.TimeoutExpired:pass
 state('failed',error=repr(e));raise
finally:
 if guard:guard.close()
 if sampler and sampler.poll() is None:sampler.terminate();sampler.wait(timeout=30)
