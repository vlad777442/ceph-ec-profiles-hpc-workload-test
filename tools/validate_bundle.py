#!/usr/bin/env python3
"""Check completeness, selection, measurement consistency and excluded file types."""
from pathlib import Path
import json,gzip,csv,hashlib,re,math
ROOT=Path(__file__).resolve().parents[1]
count=0;selected={};issues=[]
for p in ROOT.rglob('*'):
 if '.git' in p.parts:continue
 assert not p.is_symlink(),'Symlink is not portable: '+str(p)
 if not p.is_file():continue
 assert p.stat().st_size<50*1024**2,'File exceeds 50MiB: '+str(p)
 assert p.suffix not in ['.so','.tgz','.tar','.keyring','.pem','.p12','.bp'],p
 assert p.name not in ['id_rsa','id_ed25519'],p
 if p.suffix in ['.json','.md','.py','.txt','.csv','.xml','.cff','.gitignore']:
  text=p.read_text()
  assert not re.search(r'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----',text),p
  assert not re.search(r'(?m)^\s*key\s*=\s*AQ[A-Za-z0-9+/=]{30,}',text),p
for p in sorted((ROOT/'results').rglob('trial.json')):
 t=json.loads(p.read_text());count+=1
 if t['included']:selected[(t['profile'],t['condition'],t.get('cohort','original'))]=selected.get((t['profile'],t['condition'],t.get('cohort','original')),0)+1
 values=[]
 for host in ['node12','node13']:
  d=p.parent/host;r=json.loads((d/'results.json').read_text());assert r['trial_status']=='complete' and len(r['passes'])==3 and r['mpi_procs']==8
  if 'bins' in r:assert r['bins']==100
  else:assert all(re.search(r'3600\*\{256,\s*100\}',x['final_step_sample']) for x in r['passes']),'Missing bin count and output-shape evidence'
  assert r['logical_input_bytes']==2700*1024**3
  rate=r['logical_input_bytes']/1024**2/r['duration_analysis_s'];assert math.isclose(rate,r['logical_throughput_mib_s'],rel_tol=1e-9)
  values.append(rate);assert (d/'plot.png').is_file()
  with gzip.open(d/'performance.csv.gz','rt') as f:assert len(list(csv.DictReader(f)))>1
  for n in range(1,4):
   with gzip.open(d/f'pass-{n:02d}-throughput.csv.gz','rt') as f:a=list(csv.DictReader(f))
   assert len(a)==3600 and sum(int(x['global_data_read_bytes']) for x in a)==900*1024**3
   with gzip.open(d/f'pass-{n:02d}.log.gz','rb') as f:assert f.read()
 assert math.isclose(sum(values)/2,t['mean_client_mib_s'],rel_tol=1e-9)
inventory=json.loads((ROOT/'provenance/trial-inventory.json').read_text())
actual={str(p.parent.relative_to(ROOT)) for p in (ROOT/'results').rglob('trial.json')}
assert actual=={r['folder'] for r in inventory},'Trial inventory mismatch'
expected={}
for t in inventory:
 if t['included']:
  k=(t['profile'],t['condition'],t['cohort']);expected[k]=expected.get(k,0)+1
assert count==len(inventory) and selected==expected,(count,selected)
for p in (ROOT/'results').rglob('trial.json'):
 t=json.loads(p.read_text())
 if t.get('cohort')=='memory-reserve-512m':
  assert t['min_free_kbytes']==524288 and not t['include_in_original_comparison'] and t['input_hashes_before_and_after_match']

for p in ROOT.rglob('*.gz'):
 if '.git' not in p.parts:
  with gzip.open(p,'rb') as f:
   while f.read(1024**2):pass
print(f'PASS: {count} retained trials; {sum(selected.values())} selected across explicitly separated cohorts; {count*2} client records and {count*6} full-pass CSVs validated. No symlinks, forbidden artifacts, oversized files or detected private keys.')
