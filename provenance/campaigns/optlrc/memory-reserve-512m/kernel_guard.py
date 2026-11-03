"""Watch only new client kernel events; abort on allocation or storage errors."""
import re,subprocess
PATTERN=re.compile(r'page allocation failure|copyup failed|Buffer I/O error|blk_update_request:.*(?:error|failed)|rbd:.*(?:write result -|write.* result -)|EXT4-fs.*(?:error|warning)',re.I)
def has_failure(text):return bool(PATTERN.search(text))
class KernelGuard:
 def __init__(self,root):self.root=root;self.jobs=[]
 def start(self):
  for host in ['node12','node13']:
   p=self.root/(host+'-kernel-live.log');log=p.open('x');err=(self.root/(host+'-kernel-live.stderr')).open('x')
   proc=subprocess.Popen(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','root@'+host,'exec stdbuf -oL dmesg --follow-new --color=never'],stdout=log,stderr=err)
   self.jobs.append({'host':host,'proc':proc,'log':log,'err':err,'reader':p.open(),'pending':''})
 def check(self):
  for j in self.jobs:
   if j['proc'].poll() is not None:raise RuntimeError(j['host']+' kernel watcher disconnected')
   text=j['pending']+j['reader'].read();lines=text.splitlines(keepends=True);j['pending']=''
   if lines and not lines[-1].endswith('\n'):j['pending']=lines.pop()
   for line in lines:
    if has_failure(line):raise RuntimeError(j['host']+' kernel guard: '+line.strip())
 def close(self):
  for j in self.jobs:
   if j['proc'].poll() is None:
    j['proc'].terminate()
    try:j['proc'].wait(timeout=15)
    except subprocess.TimeoutExpired:j['proc'].kill();j['proc'].wait(timeout=10)
   for k in ['log','err','reader']:j[k].close()
