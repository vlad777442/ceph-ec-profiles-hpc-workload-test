from pathlib import Path
import concurrent.futures,json,shlex,subprocess
ROOT=Path(__file__).resolve().parent
CODE='''from pathlib import Path
import hashlib,json,mmap,os,socket,subprocess,time,sys,re
host=socket.gethostname().split('.')[0];begin=time.monotonic();since=float(sys.argv[1])
path=Path('/mnt/grayscott-optlrc/analysis/memory-repair-pilot-20261102-'+host+'.bin')
size=32*1024**2;count=256;assert path.stat().st_size==size*count
buf=mmap.mmap(-1,size);view=memoryview(buf);actual=hashlib.sha256();fd=os.open(path,os.O_RDONLY|os.O_DIRECT);blockhash=None
try:
 for i in range(count):
  n=os.readv(fd,[view]);assert n==size
  digest=hashlib.sha256(view).hexdigest()
  if blockhash is None:blockhash=digest
  assert digest==blockhash,'Written repeated block differs on direct readback'
  actual.update(view)
finally:os.close(fd)
recent=[]
for line in subprocess.check_output(['dmesg','--color=never'],text=True).splitlines():
 stamp=float(line.split(']')[0].strip('[').strip()) if line.startswith('[') else -1
 if stamp>=since and re.search(r'page allocation failure|copyup failed|Buffer I/O error|write result -|EXT4-fs.*(?:error|warning)',line):recent.append(line)
print(json.dumps({'host':host,'path':str(path),'bytes':size*count,'sha256':actual.hexdigest(),'direct_readback':True,'repeated_block_pattern_verified':True,'duration_seconds':time.monotonic()-begin,'kernel_errors':recent,'pass':not recent,'note':'Original write/direct-read hash equality passed before a diagnostic dmesg-format error; this independently verifies every block again. Kernel check covers all events since the memory adjustment.'}),flush=True)
assert not recent
'''
def test(host):
 adjustment=json.loads((ROOT/(host+'-memory-adjustment.json')).read_text())
 command='import time;print(time.monotonic()-(time.time()-'+str(adjustment['epoch'])+'))'
 since=subprocess.check_output(['ssh','-o','BatchMode=yes','root@'+host,shlex.join(['python3','-c',command])],text=True).strip()
 result=subprocess.run(['ssh','-o','BatchMode=yes','root@'+host,shlex.join(['python3','-u','-c',CODE,since])],capture_output=True,text=True,timeout=1800)
 (ROOT/(host+'-write-pilot-verified.stdout')).write_text(result.stdout);(ROOT/(host+'-write-pilot-verified.stderr')).write_text(result.stderr)
 assert result.returncode==0,(host,result.stdout,result.stderr)
 data=json.loads(result.stdout);(ROOT/(host+'-write-pilot-verified.json')).write_text(json.dumps(data,indent=2)+'\n');print(host,data,flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as p:list(p.map(test,['node12','node13']))
