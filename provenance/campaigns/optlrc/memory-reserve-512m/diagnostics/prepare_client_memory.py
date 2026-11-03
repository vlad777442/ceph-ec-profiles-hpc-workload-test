from pathlib import Path
import concurrent.futures,json,shlex,subprocess
ROOT=Path(__file__).resolve().parent
CODE="""from pathlib import Path
import json,time
names=['min_free_kbytes','watermark_scale_factor','compaction_proactiveness']
before={k:Path('/proc/sys/vm/'+k).read_text().strip() for k in names}
buddy=Path('/proc/buddyinfo').read_text()
Path('/proc/sys/vm/min_free_kbytes').write_text('524288\\n')
Path('/proc/sys/vm/compact_memory').write_text('1\\n')
print(json.dumps({'epoch':time.time(),'before':before,'after':{k:Path('/proc/sys/vm/'+k).read_text().strip() for k in names},'buddyinfo_before':buddy,'buddyinfo_after':Path('/proc/buddyinfo').read_text(),'persistent':False,'purpose':'Mitigate order-5 GFP_NOIO allocation failures in kernel RBD clone copy-up; 512MiB free reserve, one-time compaction; no cache dropping'}))
"""
def apply(host):
 text=subprocess.check_output(['ssh','-o','BatchMode=yes','root@'+host,shlex.join(['python3','-c',CODE])],text=True,timeout=120)
 r=json.loads(text);(ROOT/(host+'-memory-adjustment.json')).write_text(json.dumps(r,indent=2)+'\n');print(host,r['before'],r['after'],flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as p:list(p.map(apply,['node12','node13']))
