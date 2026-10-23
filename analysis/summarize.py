#!/usr/bin/env python3
"""Summarize selected trial means; clients within a trial are not replicates."""
from pathlib import Path
import json,csv,statistics,argparse
ROOT=Path(__file__).resolve().parents[1]
def summarize():
 groups={}
 for p in sorted((ROOT/'results').glob('*/*/trial-*/trial.json')):
  t=json.loads(p.read_text())
  if t['included']:groups.setdefault((t['profile'],t['condition']),[]).append(t)
 rows=[]
 for profile in ['reed-solomon','replicated-3','lrc','clay','optlrc']:
  no=groups[(profile,'no-fault')];fault=groups[(profile,'fault-osd3')];assert len(no)==len(fault)==3
  a=[r['mean_client_mib_s'] for r in no];b=[r['mean_client_mib_s'] for r in fault]
  rows.append({'profile':profile,'trials_per_condition':3,'no_fault_mib_s_per_client':statistics.mean(a),'no_fault_trial_sd':statistics.stdev(a),'fault_mib_s_per_client':statistics.mean(b),'fault_trial_sd':statistics.stdev(b),'whole_workload_drop_pct':100*(1-statistics.mean(b)/statistics.mean(a)),'repair_min_mean':statistics.mean(float(r['repair_min']) for r in fault),'fault_source_trials':','.join(str(r['source_trial']) for r in fault)})
 with (ROOT/'summaries/profile-comparison.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");w.writeheader();w.writerows(rows)
 lines=['# Selected-trial comparison','','Means are calculated from three two-client trial means per condition. Throughput is whole-workload logical MiB/s per client. SD is the sample standard deviation of trial means.','','| Configuration | No fault ± SD | Fault ± SD | Whole-job drop | Repair (min) |','|---|---:|---:|---:|---:|']
 for r in rows:lines.append(f"| {r['profile']} | {r['no_fault_mib_s_per_client']:.1f} ± {r['no_fault_trial_sd']:.1f} | {r['fault_mib_s_per_client']:.1f} ± {r['fault_trial_sd']:.1f} | {r['whole_workload_drop_pct']:.1f}% | {r['repair_min_mean']:.1f} |")
 lines+=['','Repair excludes the automatic down/out grace period and subsequent OSD restoration. Whole-job drop is not a maximum recovery-window dip. OptLRC fault source trials are 01, 03 and 04; 02 is retained but excluded. Configuration/redundancy/stripe, PG topology, occupancy, cache and scrub differences limit causal comparisons; see docs/METHODOLOGY.md.']
 (ROOT/'summaries/COMPARISON.md').write_text('\n'.join(lines)+'\n');return rows
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--plot',action='store_true');a=p.parse_args();rows=summarize()
 if a.plot:
  import matplotlib;matplotlib.use('Agg')
  import matplotlib.pyplot as plt
  fig,ax=plt.subplots(figsize=(9,4));x=list(range(len(rows)))
  ax.bar([i-.18 for i in x],[r['no_fault_mib_s_per_client'] for r in rows],width=.36,yerr=[r['no_fault_trial_sd'] for r in rows],capsize=3,label='No fault')
  ax.bar([i+.18 for i in x],[r['fault_mib_s_per_client'] for r in rows],width=.36,yerr=[r['fault_trial_sd'] for r in rows],capsize=3,label='Single OSD failure')
  ax.set_xticks(x,['RS(6,4)','Rep3 primary','LRC(6,2,4)','Clay(6,3,8)','OptLRC(10,6,4)']);ax.set_ylabel('Logical throughput per client (MiB/s)');ax.set_ylim(bottom=0);ax.legend();ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);fig.tight_layout()
  for ext in ['png','svg']:fig.savefig(ROOT/'summaries'/('throughput-comparison.'+ext),dpi=180)
