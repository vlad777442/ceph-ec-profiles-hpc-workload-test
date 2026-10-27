#!/usr/bin/env python3
"""Add absolute rates beside sustained drops without mixing metric scopes."""
from pathlib import Path
import csv,json,math
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'derived/throughput-drop'
ORDER=['reed-solomon','replicated-3','lrc','clay','optlrc']
START='<!-- absolute-throughput-context:start -->';END='<!-- absolute-throughput-context:end -->'
def add_context(out=OUT,plot=False):
 with (ROOT/'summaries/profile-comparison.csv').open() as f:jobs={r['profile']:r for r in csv.DictReader(f)}
 with (out/'trial-maxima.csv').open() as f:peaks=[r for r in csv.DictReader(f) if r['metric']=='maximum_percentage' and r['scope']=='down_to_repair' and float(r['window_s'])==30]
 assert len(peaks)==15
 rows=[]
 for profile in ORDER:
  subset=[r for r in peaks if r['profile']==profile];assert len(subset)==3
  peak=max(subset,key=lambda r:float(r['decrease_pct']));job=jobs[profile]
  fault=float(peak['fault_aggregate_mib_s']);reference=float(peak['reference_aggregate_mib_s']);drop=float(peak['decrease_pct'])
  assert math.isclose(drop,100*(1-fault/reference),rel_tol=1e-9)
  rows.append({'profile':profile,'whole_job_no_fault_logical_mib_s_per_client':float(job['no_fault_mib_s_per_client']),'whole_job_no_fault_trial_sd':float(job['no_fault_trial_sd']),'whole_job_fault_logical_mib_s_per_client':float(job['fault_mib_s_per_client']),'whole_job_fault_trial_sd':float(job['fault_trial_sd']),'worst_30s_source_trial':int(peak['source_trial']),'window_start_utc':peak['start_utc'],'window_end_utc':peak['end_utc'],'window_phase':peak['phase'],'matched_reference_aggregate_rbd_mib_s':reference,'fault_aggregate_rbd_mib_s':fault,'decrease_aggregate_rbd_mib_s':reference-fault,'decrease_pct':drop})
 with (out/'throughput-context.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
 with (out/'worst-window-throughput-by-trial.csv').open('w',newline='') as f:
  fields=['profile','source_trial','start_utc','end_utc','phase','fault_aggregate_mib_s','reference_aggregate_mib_s','decrease_mib_s','decrease_pct']
  w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows({k:r[k] for k in fields} for r in peaks)
 from client_window_breakdown import build_breakdown
 client_rows=build_breakdown(out,plot=plot)
 lines=[START,'## Absolute throughput context','','Whole-job rates below are **logical application MiB/s per client**, averaged over the three selected trial means. These include compute, output and normal pass transitions.','','| Configuration | No-fault whole job | Fault whole job |','|---|---:|---:|']
 for r in rows:lines.append(f"| {r['profile']} | {r['whole_job_no_fault_logical_mib_s_per_client']:.1f} | {r['whole_job_fault_logical_mib_s_per_client']:.1f} |")
 lines+=['','The following rates are **aggregate RBD read MiB/s across both clients**, measured/estimated at each profile\'s worst valid 30-second **percentage-decrease** window. Each row is one window from the indicated trial, not an average of the three maxima. Reference throughput is the progress-conditioned no-fault estimate.','','| Configuration | Source trial | Reference aggregate RBD | Fault aggregate RBD | Absolute decrease | Percentage decrease |','|---|---:|---:|---:|---:|---:|']
 for r in rows:lines.append(f"| {r['profile']} | {r['worst_30s_source_trial']:02d} | {r['matched_reference_aggregate_rbd_mib_s']:.1f} | {r['fault_aggregate_rbd_mib_s']:.1f} | {r['decrease_aggregate_rbd_mib_s']:.1f} | {r['decrease_pct']:.1f}% |")
 lines+=['','These two tables use different measurement scopes and client aggregation; do not compare their rates directly or divide aggregate RBD rates by two to claim measured per-client job throughput. The maximum absolute decrease can occur in a different window; it remains separately recorded in trial-maxima.csv.','','See throughput-context.csv for exact UTC windows and phases, and worst-window-throughput-by-trial.csv for all 15 trial-level maxima.','','![Whole-job and worst-window absolute throughput](throughput-context.png)','',END]
 lines=lines[:-1]+['### Each client at the same worst aggregate window','','All rates below are **per-client RBD read MiB/s**, using the exact same 30-second window for node12 and node13 within each profile. They are not each client’s independently selected maximum.','','| Configuration | Client | Reference RBD | Fault RBD | Client decrease |','|---|---|---:|---:|---:|']
 for r in client_rows:
  if r['profile_worst_aggregate_window']:lines.append(f"| {r['profile']} | {r['client']} | {r['reference_client_rbd_mib_s']:.1f} | {r['fault_client_rbd_mib_s']:.1f} | {r['decrease_client_pct']:.1f}% |")
 lines+=['','Per-client rates and absolute decreases sum to the aggregate rates/decrease; the client percentages do not add. The aggregate percentage is reference-rate-weighted. The clients are dependent observations, not two experimental repetitions. Full per-client values at all 15 trial aggregate maxima are in worst-aggregate-window-by-client.csv.','','![Per-client rates at the same worst aggregate windows](worst-window-per-client.png)','',END]
 report=out/'README.md';text=report.read_text()
 if START in text:
  a=text.index(START);b=text.index(END,a)+len(END);text=text[:a]+'\n'.join(lines)+text[b:]
 else:
  marker='## Rules fixed before calculating maxima';text=text.replace(marker,'\n'.join(lines)+'\n\n'+marker)
 report.write_text(text)
 if plot:make_plot(out,rows)
 return rows

def make_plot(out,rows):
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 fig,axes=plt.subplots(2,1,figsize=(10,8));x=list(range(5));labels=['RS(6,4)','Rep3 primary','LRC(6,2,4)','Clay(6,3,8)','OptLRC(10,6,4)']
 for ax in axes:ax.set_xticks(x,labels);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);ax.set_ylim(bottom=0)
 ax=axes[0];ax.bar([i-.18 for i in x],[r['whole_job_no_fault_logical_mib_s_per_client'] for r in rows],width=.36,yerr=[r['whole_job_no_fault_trial_sd'] for r in rows],capsize=3,label='No fault')
 ax.bar([i+.18 for i in x],[r['whole_job_fault_logical_mib_s_per_client'] for r in rows],width=.36,yerr=[r['whole_job_fault_trial_sd'] for r in rows],capsize=3,label='Fault')
 ax.set_ylabel('Logical MiB/s per client');ax.set_title('Whole-job throughput: mean of 3 trials ± sample SD');ax.legend(fontsize=8)
 ax=axes[1];ax.bar([i-.18 for i in x],[r['matched_reference_aggregate_rbd_mib_s'] for r in rows],width=.36,label='Progress-conditioned reference')
 ax.bar([i+.18 for i in x],[r['fault_aggregate_rbd_mib_s'] for r in rows],width=.36,label='Fault window')
 ax.set_ylabel('Aggregate RBD read MiB/s');ax.set_title('Absolute rates at each profile’s worst 30-second percentage-drop window');ax.legend(fontsize=8)
 fig.tight_layout()
 for ext in ['png','svg']:fig.savefig(out/('throughput-context.'+ext),dpi=180)
 plt.close(fig)
if __name__=='__main__':
 for row in add_context(plot=True):print(row['profile'],round(row['matched_reference_aggregate_rbd_mib_s'],1),round(row['fault_aggregate_rbd_mib_s'],1),round(row['decrease_pct'],1))
