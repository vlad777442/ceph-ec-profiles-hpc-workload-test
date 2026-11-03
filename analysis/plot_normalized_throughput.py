#!/usr/bin/env python3
"""Normalize original-cohort whole-job throughput to replication within condition."""
from pathlib import Path
import csv,hashlib,json,statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'derived/normalized-throughput'
PROFILES=['replicated-3','reed-solomon','lrc','clay','optlrc']
LABELS=['Replication-3','RS\n(6,4)','Ceph LRC\n(6,2,4)','Clay\n(6,3,8)','OptLRC*\n(10,6,4)']
COLORS=['#767676','#277da1','#43aa8b','#e9a23b','#9369ad']
def write_csv(path,rows):
 with path.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def main():
 OUT.mkdir(parents=True,exist_ok=True);inputs={};summary=[];trial_rows=[]
 for condition in ['no-fault','fault-osd3']:
  values={}
  for profile in PROFILES:
   selected=[]
   for folder in sorted((ROOT/'results'/profile/condition).glob('trial-*')):
    path=folder/'trial.json';inputs[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    trial=json.loads(path.read_text())
    if not trial['included']:continue
    client_values=[]
    for host in ['node12','node13']:
     path=folder/host/'results.json';inputs[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest();r=json.loads(path.read_text())
     assert r['trial_status']=='complete' and len(r['passes'])==3 and r['logical_input_bytes']==2700*1024**3
     rate=r['logical_input_bytes']/1024**2/r['duration_analysis_s']
     assert abs(rate-r['logical_throughput_mib_s'])<1e-6
     client_values.append(rate)
    rate=statistics.mean(client_values);assert abs(rate-trial['mean_client_mib_s'])<1e-6
    selected.append((trial['source_trial'],rate))
   assert len(selected)==3,(profile,condition)
   values[profile]=selected
  baseline=statistics.mean(v for _,v in values['replicated-3'])
  for profile in PROFILES:
   rates=[v for _,v in values[profile]];mean=statistics.mean(rates)
   summary.append({'condition':condition,'profile':profile,'trials':len(rates),'mean_logical_mib_s_per_client':mean,'trial_sd_mib_s_per_client':statistics.stdev(rates),'replication_mean_mib_s_per_client':baseline,'relative_throughput':mean/baseline,'difference_from_replication_pct':100*(mean/baseline-1),'source_trials':','.join(str(t) for t,_ in values[profile])})
   for trial,rate in values[profile]:trial_rows.append({'condition':condition,'profile':profile,'source_trial':trial,'logical_mib_s_per_client':rate,'relative_to_condition_replication_mean':rate/baseline})
  fig,ax=plt.subplots(figsize=(10,5.5));x=np.arange(len(PROFILES));ratios=[statistics.mean(v for _,v in values[p])/baseline for p in PROFILES]
  bars=ax.bar(x,ratios,color=COLORS,width=.62,alpha=.9,zorder=2)
  for i,profile in enumerate(PROFILES):
   ys=[v/baseline for _,v in values[profile]]
   ax.scatter(x[i]+np.array([-.11,0,.11]),ys,s=24,facecolors='white',edgecolors='black',linewidths=.8,zorder=4,label='Individual trial / replication mean' if i==0 else None)
   mean=statistics.mean(v for _,v in values[profile])
   ax.text(x[i],max(ys)+.045,f'{ratios[i]:.3f}×\n{mean:.1f} MiB/s',ha='center',va='bottom',fontsize=10)
  ax.axhline(1,color='#303030',ls='--',lw=1.2,label='Replication-3 mean = 1.0×',zorder=3)
  ax.set_xticks(x,LABELS);ax.set_ylim(0,2.05);ax.set_ylabel('Relative whole-job throughput (higher is better)')
  title='No-fault jobs' if condition=='no-fault' else 'Single-OSD fault jobs'
  ax.set_title(title+' — normalized to 3-way replication',fontsize=14,pad=13)
  ax.grid(axis='y',alpha=.2,zorder=0);ax.set_axisbelow(True);ax.legend(loc='upper left',fontsize=8,frameon=False)
  fig.text(.5,.045,'Three original trials per condition; two-client mean per trial. Bars: ratio of means; dots: individual trials.',ha='center',fontsize=8)
  fig.text(.5,.018,'* OptLRC uses a restricted local-only decoder. Fault rates cover the entire job, including before and after repair.',ha='center',fontsize=8)
  fig.tight_layout(rect=[0,.09,1,1])
  for ext in ['png','svg','pdf']:
   dest=OUT/(condition+'.'+ext);fig.savefig(dest,dpi=200)
   if ext=='svg':dest.write_text(''.join(line.rstrip()+'\n' for line in dest.read_text().splitlines()))
  plt.close(fig)
 write_csv(OUT/'profile-summary.csv',summary);write_csv(OUT/'individual-trials.csv',trial_rows)
 method={'metric':'Whole-job logical MiB/s per client: total logical bytes across three passes divided by recorded client analysis wall time; mean of both clients within trial, then equal mean of three trials.','normalization':'Profile trial-mean average divided by replication-3 trial-mean average in the same condition. Replication no-fault and replication fault use separate denominators.','figure_markers':'Bars are ratios of means. White dots are each trial mean divided by the condition-specific replication mean. No confidence intervals are claimed. Dots share an estimated denominator; clients/passes are not independent trials.','cohort':'Original three selected trials per condition for all profiles. Repaired-memory-policy OptLRC extension is excluded from these figures. Fault OptLRC trials 01/03/04; excluded trial02 retained in raw bundle.','fault_scope':'Entire fault-injection job, not only OSD-out or active-repair period. Not a measure of within-profile fault slowdown.','limitations':'Coding redundancy, min_size, stripe geometry, PG topology, occupancy, cache and scrub activity differ across configurations. Normalization does not remove these confounders.','source_sha256':inputs,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 (OUT/'method-and-provenance.json').write_text(json.dumps(method,indent=2)+'\n')
 lines=['# Throughput relative to replication-3','','Whole-job logical throughput per client, using the original three selected trials per condition. Each trial first averages its two clients; the bars divide the profile mean by the replication-3 mean for the same condition. Replication is 1.0× separately in each figure. Higher values indicate higher throughput.','','![No-fault normalized throughput](no-fault.png)','','![Fault normalized throughput](fault-osd3.png)','','White dots show all three trial means divided by the same replication mean, not paired trial ratios or confidence intervals. Original three-trial references are retained for every profile; the new OptLRC trials with changed memory settings are not mixed into this comparison.','','| Configuration | No-fault relative throughput | Fault relative throughput |','|---|---:|---:|']
 for p in PROFILES:
  a=next(r for r in summary if r['profile']==p and r['condition']=='no-fault');b=next(r for r in summary if r['profile']==p and r['condition']=='fault-osd3');lines.append(f"| {p} | {a['relative_throughput']:.3f}× | {b['relative_throughput']:.3f}× |")
 lines+=['','Fault throughput covers the complete workload, including the periods before injection and after repair. It does not represent throughput only while OSD3 is out, maximum sustained drop, or slowdown against the same profile without fault. Throughput is logical application data / total job wall time, including compute and output, not read-phase-only bandwidth. Absolute units are MiB/s; ratios are dimensionless.','','OptLRC uses a restricted local-only decoder. Configuration/PG/cache/scrub differences limit algorithm-level causal conclusions; see ../../docs/METHODOLOGY.md.','','Each figure is available as PNG, SVG and PDF. Exact means and ratios are in profile-summary.csv; all 30 trial values are in individual-trials.csv; method-and-provenance.json records source hashes and selection.','','Reproduce: `python3 analysis/plot_normalized_throughput.py`.']
 (OUT/'README.md').write_text('\n'.join(lines)+'\n')
 for r in summary:print(r['condition'],r['profile'],f"{r['relative_throughput']:.4f}x")
if __name__=='__main__':main()
