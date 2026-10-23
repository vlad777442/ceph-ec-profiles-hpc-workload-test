from pathlib import Path
import itertools,subprocess,json,hashlib,os,time
ROOT=Path(__file__).parent/'offline-correct-mapping';ROOT.mkdir(exist_ok=True)
PROFILE='plugin=optlrc,n=10,k=6,r=4,mapping=DDDD_DD___,ruleset-failure-domain=osd,crush-failure-domain=osd,stripe_unit=12288'
f=ROOT/'payload';expected=os.urandom(6*12288);f.write_bytes(expected)
with (ROOT/'encode.log').open('w') as log:subprocess.run(['ceph-erasure-code-tool','encode',PROFILE,'12288',','.join(map(str,range(10))),str(f)],stdout=log,stderr=subprocess.STDOUT,check=True)
f.rename(ROOT/'expected');results=[]
for count in range(1,3):
 for missing in itertools.combinations(range(10),count):
  have=','.join(str(i) for i in range(10) if i not in missing)
  with (ROOT/'latest-decode.log').open('w') as log:p=subprocess.run(['ceph-erasure-code-tool','decode',PROFILE,'12288',have,str(f)],stdout=log,stderr=subprocess.STDOUT,timeout=20)
  match=p.returncode==0 and f.read_bytes()==expected
  results.append({'missing':list(missing),'returncode':p.returncode,'checksum_equal':match})
  if p.returncode==0 and not match:print('Checksum mismatch',missing,flush=True)
 summary={str(n):{'patterns':sum(len(x['missing'])==n for x in results),'passed':sum(len(x['missing'])==n and x['checksum_equal'] for x in results)} for n in range(1,3)}
 (ROOT/'summary.json').write_text(json.dumps({'profile':PROFILE,'payload_sha256':hashlib.sha256(expected).hexdigest(),'counts':summary,'patterns':results},indent=2))
print(json.dumps(summary,indent=2))
