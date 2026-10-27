#!/usr/bin/env python3
"""Per-client rates at the selected aggregate peaks, not independent client peaks."""
from pathlib import Path
from types import SimpleNamespace
import csv,json,math,statistics,hashlib
import numpy as np
from throughput_drop import Client,ROOT,HOSTS
OUT=ROOT/'derived/throughput-drop'
ORDER=['reed-solomon','replicated-3','lrc','clay','optlrc']
def build_breakdown(out=OUT,plot=False):
 method=json.loads((out/'method.json').read_text());args=SimpleNamespace(max_sample_gap=method['max_counter_interval_s'],boundary_guard=method['boundary_guard_s'],grid=method['grid_s'])
 tolerance=method['progress_tolerance_fraction']
 with (out/'trial-maxima.csv').open() as f:peaks=[r for r in csv.DictReader(f) if r['metric']=='maximum_percentage' and r['scope']=='down_to_repair' and float(r['window_s'])==30]
 assert len(peaks)==15
 rows=[]
 for profile in ORDER:
  selected=[r for r in peaks if r['profile']==profile];winner=max(selected,key=lambda x:float(x['decrease_pct']))
  references=[]
  for t in sorted((ROOT/'results'/profile/'no-fault').glob('trial-*')):
   if json.loads((t/'trial.json').read_text())['included']:references.append({h:Client(t/h,args).reference_windows(30,args) for h in HOSTS})
  assert len(references)==3
  for peak in selected:
   a=float(peak['start_epoch']);b=float(peak['end_epoch']);trial=int(peak['source_trial']);group=[]
   for host in HOSTS:
    client=Client(ROOT/'results'/profile/'fault-osd3'/f'trial-{trial:02d}'/host,args);p=client.active_pass(a,b,args.boundary_guard)
    assert p is not None and p.trustworthy and client.series.coverage(a,b)>=30-.001
    q=client.progress(p,a,b);assert math.isclose(q,float(peak[host+'_progress_fraction']),rel_tol=1e-10)
    actual=client.series.integral(a,b)/30;refs=[];counts=[]
    for reference in references:
     x,y=reference[host][p.index];low=np.searchsorted(x,q-tolerance,'left');high=np.searchsorted(x,q+tolerance,'right');assert high>low
     refs.append(float(np.median(y[low:high])));counts.append(int(high-low))
    expected=statistics.mean(refs);assert expected>0
    row={'profile':profile,'source_trial':trial,'client':host,'profile_worst_aggregate_window':peak is winner,'start_utc':peak['start_utc'],'end_utc':peak['end_utc'],'start_epoch':a,'end_epoch':b,'phase':peak['phase'],'pass':p.index,'progress_fraction':q,'reference_client_rbd_mib_s':expected,'fault_client_rbd_mib_s':actual,'decrease_client_rbd_mib_s':expected-actual,'decrease_client_pct':100*(1-actual/expected),'reference_trial_min_client_mib_s':min(refs),'reference_trial_max_client_mib_s':max(refs),'min_matching_windows_per_reference_trial':min(counts),'aggregate_window_decrease_pct':float(peak['decrease_pct'])}
    rows.append(row);group.append(row)
   for key,source in [('fault_client_rbd_mib_s','fault_aggregate_mib_s'),('reference_client_rbd_mib_s','reference_aggregate_mib_s'),('decrease_client_rbd_mib_s','decrease_mib_s')]:assert math.isclose(sum(r[key] for r in group),float(peak[source]),rel_tol=1e-9,abs_tol=1e-6)
 with (out/'worst-aggregate-window-by-client.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
 (out/'client-window-method.json').write_text(json.dumps({'selection':'Each trial uses its already selected maximum-percentage aggregate 30-second window; profile_worst_aggregate_window selects the largest of the three aggregate peaks per profile.','reference':'Per-client mean across 3 reference-trial local medians; identical progress matching and eligibility to aggregate analysis.','important':'Client decreases here are evaluated at the aggregate peak, not independent per-client maxima. Client percentages do not add; the aggregate percentage is reference-rate-weighted. The two clients are dependent observations in one trial.','script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'trial_maxima_sha256':hashlib.sha256((out/'trial-maxima.csv').read_bytes()).hexdigest()},indent=2)+'\n')
 if plot:make_plot(out,[r for r in rows if r['profile_worst_aggregate_window']])
 return rows

def make_plot(out,rows):
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 fig,axes=plt.subplots(5,1,figsize=(9,12));upper=max(r['reference_client_rbd_mib_s'] for r in rows)*1.2
 for ax,profile in zip(axes,ORDER):
  pair=[r for r in rows if r['profile']==profile];assert len(pair)==2
  ax.bar([-.18,.82],[r['reference_client_rbd_mib_s'] for r in pair],width=.36,label='Matched reference')
  bars=ax.bar([.18,1.18],[r['fault_client_rbd_mib_s'] for r in pair],width=.36,label='Fault window')
  for bar,r in zip(bars,pair):ax.annotate(f"{r['decrease_client_pct']:.1f}% decrease",(bar.get_x()+bar.get_width()/2,bar.get_height()),xytext=(0,4),textcoords='offset points',ha='center',fontsize=8)
  ax.set_xticks([0,1],HOSTS);ax.set_ylim(0,upper);ax.set_ylabel('Client RBD MiB/s');ax.set_title(f"{profile}: same worst aggregate window, source trial {pair[0]['source_trial']:02d}");ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
 axes[0].legend(fontsize=8,loc='upper right');fig.tight_layout()
 for ext in ['png','svg']:fig.savefig(out/('worst-window-per-client.'+ext),dpi=180)
 plt.close(fig)
if __name__=='__main__':
 rows=build_breakdown(plot=True)
 for r in rows:
  if r['profile_worst_aggregate_window']:print(r['profile'],r['client'],round(r['reference_client_rbd_mib_s'],1),round(r['fault_client_rbd_mib_s'],1),round(r['decrease_client_pct'],1))
