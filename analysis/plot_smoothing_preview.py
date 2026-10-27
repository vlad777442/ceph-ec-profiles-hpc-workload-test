#!/usr/bin/env python3
"""Preview original samples versus fixed, time-weighted 30-second read bins."""
import argparse,csv,json,hashlib
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from throughput_drop import Client,ROOT,HOSTS,ts

def render(folder,output):
 meta=json.loads((folder/'trial.json').read_text())
 profile=meta['profile'];condition=meta['condition'];trial=folder.name
 output.mkdir(parents=True,exist_ok=True)
 clients=[Client(folder/h,SimpleNamespace(max_sample_gap=6)) for h in HOSTS]
 origin=min(ts(c.result['t_analysis_start']) for c in clients)
 end=max(ts(c.result['t_analysis_end']) for c in clients)
 starts=np.arange(origin,end-30+1e-6,30.)
 fig,axes=plt.subplots(3,1,figsize=(12,9),sharex=True)
 values=[];records=[]
 for host,c,ax in zip(HOSTS,clients,axes):
  t=(c.series.t-origin)/60
  ax.plot(t,c.series.rate,color='0.65',alpha=.45,lw=.5,label='Original counter samples')
  means=[]
  for a in starts:
   b=a+30;p=c.active_pass(a,b,6)
   rate=c.series.integral(a,b)/30 if p and c.series.coverage(a,b)>=29.999 else np.nan
   means.append(rate)
   records.append({'client':host,'start_epoch':a,'end_epoch':b,'read_mib_s':rate,'eligible':bool(np.isfinite(rate))})
  values.append(np.array(means))
  ax.plot((starts+15-origin)/60,means,color='#146c94',lw=1.5,label='30-second time-weighted mean')
  ax.set_title(host,loc='left',fontsize=11)
  for p in c.passes:
   if p.index>1:ax.axvline((p.start-origin)/60,color='0.45',ls=':',lw=.9)
  ax.axvline((ts(c.result['t_analysis_end'])-origin)/60,color='#7d3c98',lw=1,label='Client analysis ended')
 # Sum only contemporaneous eligible client bins; missing values remain gaps.
 combined=values[0]+values[1]
 axes[2].plot((starts+15-origin)/60,combined,color='#146c94',lw=1.5,label='Combined 30-second mean')
 axes[2].set_title('Both clients combined',loc='left',fontsize=11)
 for ax in axes:
  r=clients[0].result
  phases=[('Baseline',origin,ts(r['t_down']),'#d9eaf7'),
          ('OSD down / grace',ts(r['t_down']),ts(r['t_marked_out']),'#f5b7b1'),
          ('Remapping',ts(r['t_marked_out']),ts(r['t_recovering']),'#f8c471'),
          ('Active recovery',ts(r['t_recovering']),ts(r['t_healthy']),'#f9e79f'),
          ('Repair complete; OSD still down',ts(r['t_healthy']),end,'#c8e6c9')] if r.get('t_down') else [('No fault',origin,end,'#d9eaf7')]
  for label,a,b,color in phases:
   if b>a:ax.axvspan((a-origin)/60,(b-origin)/60,color=color,alpha=.4,zorder=0,label=label)
  for field,color,label in [('t_fault_injected','#c0392b','OSD stopped'),('t_marked_out','#d68910','OSD out'),('t_healthy','#238443','Repair complete')]:
   if r.get(field):ax.axvline((ts(r[field])-origin)/60,color=color,ls='--',lw=1,label=label)
  ax.set_ylabel('RBD read (MiB/s)');ax.set_ylim(bottom=0);ax.grid(alpha=.2)
 axes[0].legend(fontsize=7,ncol=3,loc='lower right')
 axes[2].legend(fontsize=7,ncol=3,loc='lower right')
 axes[2].set_xlabel('Minutes from first client analysis start')
 axes[2].set_xlim(0,(end-origin)/60+1)
 fig.suptitle(f'{profile} / {condition} / {trial}\n30-second bins with shaded cluster phases; gaps at pass boundaries',fontsize=13)
 fig.tight_layout(rect=[0,0,1,.94])
 for ext in ['png','svg']:fig.savefig(output/f'throughput-30s.{ext}',dpi=170)
 plt.close(fig)
 with (output/'throughput-30s.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(records[0]),lineterminator='\n');w.writeheader();w.writerows(records)
 assert np.isfinite(combined).sum()>0
 sources=[folder/'trial.json']+[folder/h/name for h in HOSTS for name in ['results.json','performance.csv.gz']]
 (output/'provenance.json').write_text(json.dumps({'source_trial':str(folder.relative_to(ROOT)),'bin_seconds':30,'boundary_guard_seconds':6,'max_counter_gap_seconds':6,'valid_combined_bins':int(np.isfinite(combined).sum()),'total_bins':len(starts),'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},indent=2)+'\n')
 return output/'throughput-30s.png'

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--all',action='store_true');args=parser.parse_args()
 base=ROOT/'derived/smoothed-throughput'
 folders=sorted((ROOT/'results').glob('*/*/trial-*')) if args.all else [ROOT/'results/reed-solomon/fault-osd3/trial-02']
 links=[]
 for folder in folders:
  meta=json.loads((folder/'trial.json').read_text())
  if not meta['included']:continue
  dest=base/folder.relative_to(ROOT/'results')
  plot=render(folder,dest)
  label=f"{meta['profile']} / {meta['condition']} / {folder.name}"
  links.append(f"- [{label}]({plot.relative_to(base)})")
  print(label,flush=True)
 base.mkdir(parents=True,exist_ok=True)
 (base/'README.md').write_text('# Smoothed throughput plots\n\nFixed, nonoverlapping 30-second bins anchored at the first client analysis start. Rates are time-weighted RBD read MiB/s. Each client bin must fit within one pass with a six-second guard at each boundary and full valid counter coverage (maximum interval six seconds). Aggregate curves sum contemporaneous eligible client bins; missing values remain gaps. Gray curves show original samples. Blue shading is before failure (or the entire no-fault run), red is OSD-down grace, orange is remapping when nonzero, yellow is active recovery, and green is repair complete with the target OSD still down. Dashed lines mark events; dotted lines mark pass starts on client panels. Smoothing can straddle recovery events; event lines show the original timestamps. Original figures and numerical maximum-drop analysis are unchanged.\n\nEach folder contains PNG, SVG, per-client binned CSV, and source hashes. Only included trials are plotted; OptLRC fault trial 02 remains excluded. Reproduce: `python3 analysis/plot_smoothing_preview.py --all`.\n\n'+'\n'.join(links)+'\n')
 print(f'Generated {len(links)} plots: {base}',flush=True)
if __name__=='__main__':main()
