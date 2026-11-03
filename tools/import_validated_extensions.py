#!/usr/bin/env python3
"""Import completed OptLRC memory-reserve cohort without changing original analyses."""
from pathlib import Path
from datetime import datetime
import csv,gzip,hashlib,json,shutil,statistics
ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path('/users/vlad777/research/erasure-coding/optlrc/five-trial-repair-20261102')
DIAG=SOURCE.parent/'five-trial-extension-20261101/diagnostics'
COHORT='memory-reserve-512m'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def safe_json(value):
 if isinstance(value,dict):return {k:('[REDACTED]' if k.lower() in ['key','secret','password','token','access_token'] else safe_json(v)) for k,v in value.items()}
 if isinstance(value,list):return [safe_json(x) for x in value]
 return value
def main():
 state=json.loads((SOURCE/'state.json').read_text());assert state['phase']=='complete' and state['input_integrity_passed_both_clients']
 mappings=[]
 def put(src,dest):
  dest.parent.mkdir(parents=True,exist_ok=True)
  if dest.suffix=='.gz':
   with src.open('rb') as r,dest.open('wb') as raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as w:shutil.copyfileobj(r,w)
   transform='deterministic lossless gzip'
  elif src.suffix=='.json':dest.write_text(json.dumps(safe_json(json.loads(src.read_text())),indent=2)+'\n');transform='JSON serialization and credential-field redaction'
  elif src.name=='plot_io.py':dest.write_text(''.join(line.rstrip()+'\n' for line in src.read_text().splitlines()));transform='Python source trailing-whitespace normalization'
  else:shutil.copy2(src,dest);transform='byte-preserving copy'
  mappings.append({'repository_file':str(dest.relative_to(ROOT)),'source_file':str(src),'source_sha256':digest(src),'packaged_sha256':digest(dest),'transform':transform})
 rows=[]
 for condition in ['no-fault','fault-osd3']:
  for number in [5,6]:
   source=SOURCE/condition/f'trial-{number:02d}';dest=ROOT/'results/optlrc'/('cohort-'+COHORT)/condition/source.name
   assert not dest.exists(),'Refuse to overwrite imported results'
   records=[]
   for host in ['node12','node13']:
    client=source/host;r=json.loads((client/'results.json').read_text());assert r['trial_status']=='complete' and len(r['passes'])==3 and r['logical_input_bytes']==2700*1024**3
    records.append(r)
    for name,target in [('results.json','results.json'),('perf.csv','performance.csv.gz'),('nofault_io.png' if condition=='no-fault' else 'fault_io.png','plot.png')]:put(client/name,dest/host/target)
    for i in range(1,4):
     put(client/f'pass-{i:03d}-throughput.csv',dest/host/f'pass-{i:02d}-throughput.csv.gz');put(client/f'pass-{i:03d}.log',dest/host/f'pass-{i:02d}.log.gz')
   for p in source.iterdir():
    if p.is_file() and (p.suffix in ['.json','.jsonl']) and p.name not in ['PLAN.json','client-progress.json']:
     put(p,dest/'cluster'/(p.name+'.gz' if p.suffix=='.jsonl' else p.name))
   rates=[r['logical_throughput_mib_s'] for r in records];starts=[datetime.fromisoformat(r['t_analysis_start']).timestamp() for r in records];ends=[datetime.fromisoformat(r['t_analysis_end']).timestamp() for r in records]
   repair=down=''
   if condition=='fault-osd3':
    events=json.loads((source/'recovery.json').read_text())['events'];stamp=lambda k:datetime.fromisoformat(events[k]).timestamp();repair=(stamp('healthy')-stamp('recovering'))/60;down=(stamp('healthy')-stamp('down'))/60
   row={'profile':'optlrc','condition':condition,'source_trial':number,'included':True,'exclusion_reason':'','cohort':COHORT,'include_in_original_comparison':False,'clients':2,'passes_per_client':3,'mean_client_mib_s':statistics.mean(rates),'aggregate_mib_s':5400*1024/(max(ends)-min(starts)),'mean_client_duration_min':statistics.mean(r['duration_analysis_s'] for r in records)/60,'repair_min':repair,'down_to_clean_min':down,'folder':str(dest.relative_to(ROOT)),'min_free_kbytes':524288,'input_hashes_before_and_after_match':True}
   (dest/'trial.json').write_text(json.dumps(row,indent=2)+'\n');rows.append(row)
   (dest/'README.md').write_text(f"# OptLRC {condition} source trial {number:02d}\n\nValidated additional trial, cohort `{COHORT}`. Two clients, eight MPI ranks/client, three full passes, 100 bins. Full input hashes matched before and after the four-trial extension. Both clients used temporary vm.min_free_kbytes=524288 (original90112), with one-time compaction before pilots and no cache dropping. This trial is valid within the additional cohort but excluded from the original three-trial comparison/normalized figures/drop references. Keep cohort labels when comparing or pooling. Configuration/mitigation evidence: ../../../../../provenance/campaigns/optlrc/{COHORT}/. Failed no-fault04 is retained outside the main results and documented in campaign provenance.\n")
 provenance=ROOT/'provenance/campaigns/optlrc'/COHORT
 for p in SOURCE.iterdir():
  if p.is_file() and p.suffix in ['.py','.md','.json','.jsonl','.log']:
   put(p,provenance/(p.name+'.gz' if p.suffix in ['.log','.jsonl'] else p.name))
 for name in ['no-fault/controller.py','no-fault/plot_io.py','fault-osd3/trial-05/controller.py','fault-osd3/trial-06/controller.py']:
  put(SOURCE/name,provenance/'controllers'/name)
 for p in DIAG.iterdir():
  if p.is_file() and p.suffix in ['.json','.md','.py','.cpp','.txt']:
   put(p,provenance/'diagnostics'/(p.name+'.gz' if p.suffix=='.txt' else p.name))
 excluded=SOURCE.parent/'five-trial-extension-20261101/trial-selection.json';put(excluded,provenance/'excluded-attempts.json')
 for p in (SOURCE/'osd-host-telemetry').glob('*.jsonl'):put(p,ROOT/'telemetry/optlrc'/COHORT/(p.name+'.gz'))
 with (ROOT/'summaries'/('trials-'+COHORT+'.csv')).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
 lines=['# Additional OptLRC trials: memory-reserve-512m','','Separate cohort: the client memory reserve changed from 90112 to 524288 KiB after an RBD copy-up allocation/write failure. Original comparison figures and drop references continue to use the original three trials per condition. These are two additional independent trials per condition, not five trials in an unchanged environment.','','| Condition | Trial | Mean client MiB/s | Mean duration (min) | Repair (min) |','|---|---:|---:|---:|---:|']
 for r in rows:lines.append(f"| {r['condition']} | {r['source_trial']} | {r['mean_client_mib_s']:.2f} | {r['mean_client_duration_min']:.2f} | {float(r['repair_min']):.2f} |" if r['repair_min']!='' else f"| {r['condition']} | {r['source_trial']} | {r['mean_client_mib_s']:.2f} | {r['mean_client_duration_min']:.2f} | — |")
 lines+=['','Both clients completed and validated all three passes in each trial. No new kernel allocation/write errors were observed during the repaired campaign. Complete input checksums matched before and after. The two clients within a trial are dependent observations. The failed extension no-fault04 is excluded, with diagnosis in provenance/campaigns/optlrc/memory-reserve-512m/. Source code, original settings, policy change, original/packaged file hashes and compressed telemetry are preserved.']
 (ROOT/'summaries'/('EXTENSION-'+COHORT+'.md')).write_text('\n'.join(lines)+'\n')
 (provenance/'import-file-sources.json').write_text(json.dumps(mappings,indent=2)+'\n')
 print('Imported four validated OptLRC trials into a separate cohort')
if __name__=='__main__':main()
