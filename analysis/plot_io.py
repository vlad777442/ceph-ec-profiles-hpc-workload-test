#!/usr/bin/env python3
"""Regenerate client I/O figures from original measurements and canonical labels."""
import argparse,csv,gzip,json
from pathlib import Path
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
def stamp(x):return datetime.fromisoformat(x.replace('Z','+00:00')).timestamp() if x else None
def render(job):
 p=ROOT/job['performance'];r=json.loads((ROOT/job['results']).read_text());start=stamp(r['t_analysis_start']);end=stamp(r['t_analysis_end'])
 with gzip.open(p,'rt') as f:rows=list(csv.DictReader(f))
 t=[];read=[];write=[]
 for x in rows:
  try:a=float(x['timestamp']);b=float(x['io_read_mb']);c=float(x['io_write_mb'])
  except (ValueError,KeyError):continue
  t.append((a-start)/60);read.append(b);write.append(c)
 fig,axes=plt.subplots(2,1,figsize=(10,5),sharex=True)
 for ax,values,label in zip(axes,[read,write],['RBD read (MiB/s)','RBD write (MiB/s)']):
  ax.plot(t,values,lw=.7,color='#146c94');ax.set_ylabel(label);ax.grid(alpha=.2)
  for event,color in [('t_fault_injected','#c0392b'),('t_marked_out','#d68910'),('t_healthy','#238443')]:
   if r.get(event):ax.axvline((stamp(r[event])-start)/60,color=color,ls='--',lw=1,label={'t_fault_injected':'OSD stopped','t_marked_out':'OSD out','t_healthy':'Repair complete'}[event])
  for record in r['passes'][1:]:ax.axvline((stamp(record['start_utc'])-start)/60,color='0.55',ls=':',lw=.8)
  ax.axvline((end-start)/60,color='#7d3c98',lw=1.2,label='Analysis completed')
 axes[0].legend(fontsize=7,loc='upper right');axes[0].set_title(job['label']+' — '+r['hostname'].split('.')[0])
 axes[1].set_xlabel('Minutes from analysis start');fig.tight_layout();dest=ROOT/job['plot'];fig.savefig(dest,dpi=150);plt.close(fig)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--all',action='store_true');p.add_argument('--job',type=int);a=p.parse_args();jobs=json.loads((ROOT/'provenance/plot-jobs.json').read_text())
 for job in jobs if a.all else [jobs[a.job or 0]]:render(job)
