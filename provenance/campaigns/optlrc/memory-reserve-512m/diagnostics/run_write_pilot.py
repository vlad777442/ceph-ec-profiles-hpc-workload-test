from pathlib import Path
import concurrent.futures,json,shlex,subprocess
ROOT=Path(__file__).resolve().parent
CODE=r'''from pathlib import Path
import hashlib,json,mmap,os,re,socket,subprocess,time
host=socket.gethostname().split('.')[0];started=time.monotonic()
path=Path('/mnt/grayscott-optlrc/analysis/memory-repair-pilot-20261102-'+host+'.bin')
size=32*1024**2;count=256
buf=mmap.mmap(-1,size);buf[:]=os.urandom(size);view=memoryview(buf)
fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_DIRECT,0o600);expected=hashlib.sha256()
try:
 for i in range(count):
  n=os.write(fd,view);assert n==size;expected.update(view)
 os.fsync(fd)
finally:os.close(fd)
write_s=time.monotonic()-started
actual=hashlib.sha256();fd=os.open(path,os.O_RDONLY|os.O_DIRECT)
try:
 for i in range(count):
  n=os.readv(fd,[view]);assert n==size;actual.update(view)
finally:os.close(fd)
assert actual.digest()==expected.digest(),'Direct readback mismatch'
log=subprocess.check_output(['dmesg','--color=never'],text=True)
recent=[]
for line in log.splitlines():
 stamp=float(line.split(']')[0].strip('[').strip()) if line.startswith('[') else -1
 if stamp>=started and re.search(r'page allocation failure|copyup failed|Buffer I/O error|write result -|EXT4-fs.*(?:error|warning)',line):recent.append(line)
print(json.dumps({'host':host,'path':str(path),'bytes':size*count,'sha256':actual.hexdigest(),'direct_write_and_read':True,'write_seconds':write_s,'total_seconds':time.monotonic()-started,'kernel_errors':recent,'pass':not recent,'min_free_kbytes':Path('/proc/sys/vm/min_free_kbytes').read_text().strip()}),flush=True)
assert not recent,'Kernel error during pilot'
'''
def test(host):
 result=subprocess.run(['ssh','-o','BatchMode=yes','root@'+host,shlex.join(['python3','-u','-c',CODE])],text=True,capture_output=True,timeout=1800)
 (ROOT/(host+'-write-pilot.stdout')).write_text(result.stdout);(ROOT/(host+'-write-pilot.stderr')).write_text(result.stderr)
 assert result.returncode==0,(host,result.stderr)
 data=json.loads(result.stdout);(ROOT/(host+'-write-pilot.json')).write_text(json.dumps(data,indent=2)+'\n');print(host,data,flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as p:list(p.map(test,['node12','node13']))
