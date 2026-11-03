from pathlib import Path
import concurrent.futures,subprocess,shlex,json
ROOT=Path(__file__).resolve().parent
REMOTE='/users/vlad777/optlrc-memory-repair-20261102'
CODE=r'''from pathlib import Path
import subprocess,shlex,socket,json,os,re,time
root=Path('/users/vlad777/optlrc-memory-repair-20261102');host=socket.gethostname().split('.')[0]
def run(argv):return subprocess.check_output(argv,text=True,stderr=subprocess.STDOUT,timeout=1200)
config='/users/vlad777/software/adios2/bin/adios2-config'
flags=shlex.split(run([config,'--cxx-flags']));libs=shlex.split(run([config,'--cxx-libs']))
run(['mpicxx','-O2',str(root/'bp5_write_pilot.cpp'),'-o',str(root/'bp5_write_pilot'),*flags,*libs])
output='/mnt/grayscott-optlrc/analysis/bp5-memory-repair-pilot-20261102-'+host+'.bp'
started=time.monotonic()-(time.time()-Path(output).stat().st_ctime) if Path(output).exists() else time.monotonic()
text='Existing diagnostic output retained' if Path(output).exists() else run(['sudo','-H','-u','vlad777','mpirun','--bind-to','core','-n','8',str(root/'bp5_write_pilot'),output])
for p in Path(output).iterdir():
 if p.is_file():
  fd=os.open(p,os.O_RDONLY)
  try:os.fsync(fd)
  finally:os.close(fd)
bpls='/users/vlad777/software/adios2/bin/bpls';listing=run([bpls,output]);assert listing.count('3600*')==2,listing
readback=run([bpls,'-d','-s','3599,0,0','-c','1,1,1',output,'U/pdf','V/pdf']);assert '3599' in readback and '-3599' in readback
recent=[]
for line in run(['dmesg','--color=never']).splitlines():
 stamp=float(line.split(']')[0].strip('[').strip()) if line.startswith('[') else -1
 if stamp>=started and re.search(r'page allocation failure|copyup failed|Buffer I/O error|write result -|EXT4-fs.*(?:error|warning)',line):recent.append(line)
print(json.dumps({'host':host,'output':output,'steps':3600,'ranks':8,'duration_seconds':time.monotonic()-started,'listing':listing,'final_readback':readback,'kernel_errors':recent,'pass':not recent}))
assert not recent
'''
def test(host):
 subprocess.run(['ssh','-o','BatchMode=yes','root@'+host,shlex.join(['install','-d','-o','vlad777','-g','ISU-Cloud',REMOTE])],check=True)
 subprocess.run(['scp',str(ROOT/'bp5_write_pilot.cpp'),'root@'+host+':'+REMOTE+'/bp5_write_pilot.cpp'],check=True,capture_output=True)
 result=subprocess.run(['ssh','-o','BatchMode=yes','root@'+host,shlex.join(['python3','-u','-c',CODE])],capture_output=True,text=True,timeout=1800)
 (ROOT/(host+'-bp5-pilot.stdout')).write_text(result.stdout);(ROOT/(host+'-bp5-pilot.stderr')).write_text(result.stderr)
 assert result.returncode==0,(host,result.stdout,result.stderr)
 data=json.loads(result.stdout);(ROOT/(host+'-bp5-pilot.json')).write_text(json.dumps(data,indent=2)+'\n');print(host,data,flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as p:list(p.map(test,['node12','node13']))
