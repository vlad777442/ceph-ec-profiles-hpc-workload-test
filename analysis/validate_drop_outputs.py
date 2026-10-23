#!/usr/bin/env python3
"""Independent peak-window checks against raw counter intervals and pass bounds."""
from pathlib import Path
from datetime import datetime
import csv,gzip,json,math
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'derived/throughput-drop'
def ts(s):return datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()
def close(a,b):assert math.isclose(float(a),float(b),rel_tol=1e-7,abs_tol=1e-5),(a,b)
with (OUT/'trial-maxima.csv').open() as f:rows=list(csv.DictReader(f))
primary=[r for r in rows if float(r['window_s'])==30 and r['scope']=='down_to_repair'];assert len(primary)==30
for r in primary:
 a=float(r['start_epoch']);b=float(r['end_epoch']);close(b-a,30);rates=[]
 for host in ['node12','node13']:
  p=ROOT/'results'/r['profile']/'fault-osd3'/('trial-%02d'%int(r['source_trial']))/host
  data=json.loads((p/'results.json').read_text());assert ts(data['t_down'])<=a and b<=ts(data['t_healthy'])+1e-5
  assert any(a>=ts(x['start_utc'])+6-1e-5 and b<=ts(x['end_utc'])-6+1e-5 for x in data['passes'])
  with gzip.open(p/'performance.csv.gz','rt') as f:samples=list(csv.DictReader(f))
  total=covered=0.
  for previous,current in zip(samples,samples[1:]):
   x=float(previous['timestamp']);y=float(current['timestamp']);overlap=max(0.,min(y,b)-max(x,a))
   if not overlap:continue
   assert y-x<=6 and current['io_read_mb']!='';rate=float(current['io_read_mb']);assert rate>=0
   total+=rate*overlap;covered+=overlap
  close(covered,30);rates.append(total/30)
 close(sum(rates),r['fault_aggregate_mib_s']);reference=float(r['reference_aggregate_mib_s']);assert reference>0
 close(100*(1-sum(rates)/reference),r['decrease_pct']);close(reference-sum(rates),r['decrease_mib_s'])
# Check extrema against the complete accepted candidate series, not just the report.
checked=set()
for r in primary:
 key=(r['profile'],r['source_trial'])
 if key in checked:continue
 p=OUT/'windows'/r['profile']/('trial-%02d'%int(r['source_trial']))/'down_to_repair-30s.csv.gz'
 with gzip.open(p,'rt') as f:candidates=[x for x in csv.DictReader(f) if x['accepted']=='True']
 for metric,column in [('maximum_percentage','decrease_pct'),('maximum_absolute','decrease_mib_s')]:
  winner=next(x for x in primary if (x['profile'],x['source_trial'])==key and x['metric']==metric)
  close(winner[column],max(float(x[column]) for x in candidates))
 checked.add(key)
print('PASS: all 30 primary peak records independently match raw interval integrals, pass guards, event bounds, arithmetic and full-window extrema.')
