#!/usr/bin/env python3
"""Time-weighted sustained RBD read decreases; selected trials, explicit exclusions."""
from pathlib import Path
from datetime import datetime,timezone
from dataclasses import dataclass
import argparse,csv,gzip,json,math,statistics,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
PROFILES=['reed-solomon','replicated-3','lrc','clay','optlrc'];HOSTS=['node12','node13']
def ts(s):return datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()
def utc(t):return datetime.fromtimestamp(t,timezone.utc).isoformat(timespec='milliseconds')
class CounterSeries:
 def __init__(self,times,rates,max_gap=6.):
  self.t=np.array(times,float);self.rate=np.array(rates,float)
  assert len(self.t)==len(self.rate) and len(self.t)>1 and np.all(np.diff(self.t)>0)
  dt=np.diff(self.t);self.valid=np.isfinite(self.rate[1:])&(self.rate[1:]>=0)&(dt<=max_gap)
  self.area=np.r_[0.,np.cumsum(np.where(self.valid,self.rate[1:]*dt,0.))]
  self.cover=np.r_[0.,np.cumsum(np.where(self.valid,dt,0.))]
 def cdf(self,x,coverage=False):
  x=np.asarray(x,float);i=np.clip(np.searchsorted(self.t,x,side='right')-1,0,len(self.t)-2)
  part=np.clip(x-self.t[i],0,self.t[i+1]-self.t[i]);rate=np.where(self.valid,1. if coverage else self.rate[1:],0.)
  prefix=self.cover if coverage else self.area
  value=prefix[i]+part*rate[i]
  return np.where(x<=self.t[0],0.,np.where(x>=self.t[-1],prefix[-1],value))
 def integral(self,a,b):return float(self.cdf(b)-self.cdf(a))
 def coverage(self,a,b):return float(self.cdf(b,True)-self.cdf(a,True))
@dataclass
class Pass:
 index:int;start:float;end:float;read_mib:float;coverage_fraction:float;ratio:float
 def contains(self,a,b,guard):return a>=self.start+guard-1e-6 and b<=self.end-guard+1e-6
 @property
 def trustworthy(self):return self.coverage_fraction>=.99 and .9<=self.ratio<=1.1
class Client:
 def __init__(self,path,args):
  self.path=path;self.result=json.loads((path/'results.json').read_text())
  with gzip.open(path/'performance.csv.gz','rt') as f:rows=list(csv.DictReader(f))
  self.series=CounterSeries([float(x['timestamp']) for x in rows],[float(x['io_read_mb']) if x['io_read_mb'] else np.nan for x in rows],args.max_sample_gap)
  self.passes=[]
  for p in self.result['passes']:
   i=p['pass_index'];a=ts(p['start_utc']);b=ts(p['end_utc'])
   with gzip.open(path/f'pass-{i:02d}-throughput.csv.gz','rt') as f:steps=list(csv.DictReader(f))
   logical=sum(int(x['global_data_read_bytes']) for x in steps)/1024**2
   assert len(steps)==3600 and logical==900*1024
   amount=self.series.integral(a,b);self.passes.append(Pass(i,a,b,amount,self.series.coverage(a,b)/(b-a),amount/logical))
 def active_pass(self,a,b,guard):return next((p for p in self.passes if p.contains(a,b,guard)),None)
 def progress(self,p,a,b):return ((self.series.integral(p.start,a)+self.series.integral(p.start,b))/2)/p.read_mib
 def reference_windows(self,width,args):
  out={}
  for p in self.passes:
   if not p.trustworthy:continue
   a=np.arange(math.ceil((p.start+args.boundary_guard)/args.grid)*args.grid,p.end-args.boundary_guard-width+1e-5,args.grid);b=a+width
   if not len(a):continue
   coverage=self.series.cdf(b,True)-self.series.cdf(a,True);ok=coverage>=width-.001
   values=(self.series.cdf(b)-self.series.cdf(a))/width
   progress=((self.series.cdf(a)+self.series.cdf(b))/2-self.series.cdf(p.start))/p.read_mib
   ok&=(values>=0);out[p.index]=(progress[ok],values[ok])
  return out

def reference_rate(references,pass_ids,progress,tolerance):
 sums=[];counts=[]
 for trial in references:
  total=0.;n=[]
  for host,index,q in zip(HOSTS,pass_ids,progress):
   if index not in trial[host]:return None
   x,y=trial[host][index];lo=np.searchsorted(x,q-tolerance,'left');hi=np.searchsorted(x,q+tolerance,'right')
   if hi==lo:return None
   total+=float(np.median(y[lo:hi]));n.append(int(hi-lo))
  sums.append(total);counts+=n
 if min(sums)<=0:return None
 return statistics.mean(sums),sums,min(counts)
def phase_label(a,b,events):
 parts=[]
 for label,x,y in [('grace',events['down'],events['marked_out']),('remapping',events['marked_out'],events['recovering']),('active_repair',events['recovering'],events['healthy'])]:
  if min(b,y)>max(a,x):parts.append(label)
 return '+'.join(parts) or 'post_repair_osd_down'
def dump_csv(path,rows):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def analyze(args):
 out=ROOT/args.output;out.mkdir(parents=True,exist_ok=True);all_max=[];exclusions=[];audit=[];plot_data={};input_hashes={}
 for profile in PROFILES:
  print('Analyzing',profile,flush=True)
  base=ROOT/'results'/profile;baseline=[]
  for t in sorted((base/'no-fault').glob('trial-*')):
   if json.loads((t/'trial.json').read_text())['included']:baseline.append({h:Client(t/h,args) for h in HOSTS})
  assert len(baseline)==3
  for trial in baseline:
   for host,c in trial.items():
    for p in c.passes:audit.append({'profile':profile,'condition':'no-fault','client':host,'source':str(c.path.relative_to(ROOT)),'pass':p.index,'rbd_to_logical_read_ratio':p.ratio,'pass_counter_coverage':p.coverage_fraction,'progress_proxy_accepted':p.trustworthy})
  for t in sorted((base/'fault-osd3').glob('trial-*')):
   meta=json.loads((t/'trial.json').read_text())
   if not meta['included']:continue
   fault={h:Client(t/h,args) for h in HOSTS};r=fault['node12'].result
   events={k:ts(r['t_'+k]) for k in ['down','marked_out','recovering','healthy']}
   assert list(events.values())==sorted(events.values())
   for host,c in fault.items():
    for p in c.passes:audit.append({'profile':profile,'condition':'fault-osd3','client':host,'source':str(c.path.relative_to(ROOT)),'pass':p.index,'rbd_to_logical_read_ratio':p.ratio,'pass_counter_coverage':p.coverage_fraction,'progress_proxy_accepted':p.trustworthy})
   scopes={'down_to_repair':(events['down'],events['healthy']),'grace':(events['down'],events['marked_out']),'remapping':(events['marked_out'],events['recovering']),'active_repair':(events['recovering'],events['healthy']),'post_repair_osd_down':(events['healthy'],min(ts(c.result['t_analysis_end']) for c in fault.values()))}
   for width in args.windows:
    refs=[{h:c.reference_windows(width,args) for h,c in trial.items()} for trial in baseline]
    for scope,(start,end) in scopes.items():
     rows=[];valid=[];counts={};starts=np.arange(start,end-width+1e-5,args.grid) if end-start>=width else []
     for a in starts:
      b=a+width;passes=[fault[h].active_pass(a,b,args.boundary_guard) for h in HOSTS];reason='';progress=[];actual=None;ref=None
      if any(p is None for p in passes):reason='pass_transition_or_boundary_guard'
      elif any(not p.trustworthy for p in passes):reason='unreliable_pass_progress_proxy'
      elif any(fault[h].series.coverage(a,b)<width-.001 for h in HOSTS):reason='missing_or_long_gap_counter_coverage'
      else:
       progress=[fault[h].progress(p,a,b) for h,p in zip(HOSTS,passes)]
       actual=sum(fault[h].series.integral(a,b)/width for h in HOSTS)
       ref=reference_rate(refs,[p.index for p in passes],progress,args.progress_tolerance)
       if ref is None:reason='insufficient_matched_reference'
      row={'profile':profile,'source_trial':meta['source_trial'],'scope':scope,'window_s':width,'start_utc':utc(a),'end_utc':utc(b),'start_epoch':float(a),'end_epoch':float(b),'accepted':not reason,'exclusion_reason':reason,'phase':phase_label(a,b,events),'node12_pass':passes[0].index if passes[0] else '', 'node13_pass':passes[1].index if passes[1] else '', 'node12_progress_fraction':progress[0] if progress else '', 'node13_progress_fraction':progress[1] if progress else '', 'fault_aggregate_mib_s':actual if actual is not None else '', 'reference_aggregate_mib_s':ref[0] if ref else '', 'decrease_mib_s':ref[0]-actual if ref else '', 'decrease_pct':100*(1-actual/ref[0]) if ref else '', 'reference_trial_min_mib_s':min(ref[1]) if ref else '', 'reference_trial_max_mib_s':max(ref[1]) if ref else '', 'min_matching_windows_per_reference_client':ref[2] if ref else ''}
      rows.append(row);counts[reason or 'accepted']=counts.get(reason or 'accepted',0)+1
      if not reason:valid.append(row)
     path=out/'windows'/profile/f'trial-{meta["source_trial"]:02d}'/f'{scope}-{width:g}s.csv.gz';path.parent.mkdir(parents=True,exist_ok=True)
     if rows:
      with path.open('wb') as raw:
       with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as compressed:
        import io
        with io.TextIOWrapper(compressed,newline='') as stream:
         w=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
     exclusions.append({'profile':profile,'source_trial':meta['source_trial'],'scope':scope,'window_s':width,'candidate_windows':len(starts),'accepted_windows':len(valid),'pass_transition_or_boundary_guard':counts.get('pass_transition_or_boundary_guard',0),'unreliable_pass_progress_proxy':counts.get('unreliable_pass_progress_proxy',0),'missing_or_long_gap_counter_coverage':counts.get('missing_or_long_gap_counter_coverage',0),'insufficient_matched_reference':counts.get('insufficient_matched_reference',0)})
     if valid:
      for metric,key in [('maximum_percentage','decrease_pct'),('maximum_absolute','decrease_mib_s')]:
       best=max(valid,key=lambda x:x[key]);all_max.append({'metric':metric,**best})
     if width==30 and scope=='down_to_repair':plot_data.setdefault(profile,[]).append((meta['source_trial'],fault,events,rows,valid))
 dump_csv(out/'trial-maxima.csv',all_max);dump_csv(out/'exclusion-counts.csv',exclusions);dump_csv(out/'progress-proxy-audit.csv',audit)
 summaries=[]
 for profile in PROFILES:
  for scope in scopes:
   for width in args.windows:
    selected=[x for x in all_max if x['profile']==profile and x['scope']==scope and x['window_s']==width and x['metric']=='maximum_percentage']
    values=[x['decrease_pct'] for x in selected]
    summaries.append({'profile':profile,'scope':scope,'window_s':width,'trials_with_valid_windows':len(values),'mean_trial_max_decrease_pct':statistics.mean(values) if values else '', 'sample_sd_pct':statistics.stdev(values) if len(values)>1 else '', 'worst_observed_decrease_pct':max(values) if values else '', 'source_trials':','.join(str(x['source_trial']) for x in selected)})
 dump_csv(out/'profile-summary.csv',summaries)
 method={'metric':'Maximum sustained aggregate RBD read-throughput decrease during confirmed OSD down to repair complete','windows_s':args.windows,'grid_s':args.grid,'boundary_guard_s':args.boundary_guard,'max_counter_interval_s':args.max_sample_gap,'minimum_window_counter_coverage':'window length minus 0.001 seconds','progress_matching':'Per-client cumulative RBD read bytes normalized within pass; midpoint of window read-progress endpoints. Application CSV validates 3600 steps / 900 GiB per pass; exact per-step wall-clock progress unavailable.','progress_tolerance_fraction':args.progress_tolerance,'reference':'For each of 3 no-fault trials and each client: median of eligible same-duration same-pass windows within progress tolerance; sum client medians, then mean across the 3 trial estimates. Synthetic progress-conditioned aggregate, not a contemporaneous no-fault window.','progress_proxy_requirements':'Pass counter coverage >=99%; RBD/logical read ratio between 0.9 and 1.1. Audit recorded, not assumed.','selection':'Original primary-only replication; OptLRC faults 01/03/04; all other selected faults 01/02/03.','phase_boundary_policy':'Recovery-phase-crossing windows retained and labeled; pass-crossing windows excluded.','post_repair_scope':'Repair complete through earlier client analysis end; target OSD remains down until after both jobs finish.','interpretation':'Observed decrease relative to estimated matched reference, not a causal estimate; rolling-window overlap and search over many windows increase extreme-value sensitivity. No pointwise significance claim.'}
 (out/'method.json').write_text(json.dumps(method,indent=2)+'\n')
 write_report(out,summaries,all_max,exclusions,args)
 capture_provenance(out)
 if not args.no_plots:plots(out,plot_data,args.boundary_guard)
 return out

def write_report(out,summaries,maxima,exclusions,args):
 lines=['# Maximum sustained read-throughput decrease','','Primary metric: maximum **30-second** time-weighted aggregate RBD read-throughput decrease during confirmed OSD down to repair completion. Every fault window uses both clients on the same wall-clock interval. Baseline reference is progress-conditioned, as detailed below.','','| Configuration | Mean of 3 trial maxima ± sample SD | Worst observed | Trials |','|---|---:|---:|---|']
 for r in summaries:
  if r['scope']=='down_to_repair' and r['window_s']==30:
   lines.append(f"| {r['profile']} | {r['mean_trial_max_decrease_pct']:.1f}% ± {r['sample_sd_pct']:.1f} pp | {r['worst_observed_decrease_pct']:.1f}% | {r['source_trials']} |" if r['trials_with_valid_windows']==3 else f"| {r['profile']} | Insufficient valid windows | — | {r['source_trials']} |")
 lines+=['','## Rules fixed before calculating maxima','','- Only selected trials; replication is primary-only; OptLRC faults 01/03/04.','- Fault-search interval t_down → t_healthy; phase-specific and post-repair OSD-down results are secondary.','- Three-second grid; 10/30/60-second windows. Counter rates weighted by actual interval overlap; missing samples are not zero.','- Window must fit within one pass on each client, with six seconds trimmed from pass starts/ends. Entire window needs counter coverage; no exclusion based on how low its rate looks.','- Same rule for reference windows. Normal pass dips remain in plots and whole-job throughput.','', '## Progress-reference approximation','','The existing application CSVs do not contain per-step wall-clock timestamps. Progress is therefore inferred from cumulative RBD reads normalized within each recorded pass; application CSVs establish 3600 steps and 900 GiB per pass. Check progress-proxy-audit.csv for measured coverage and read-byte ratios. This does not establish exact simulation-step alignment.','','For each client, pass, and fault-window progress midpoint, eligible no-fault windows within ±1 percentage point of normalized progress are used. Their median throughput is calculated within each no-fault trial/client, client medians are summed, and the three trial estimates are averaged. Thus the reference is a synthetic progress-conditioned aggregate, not necessarily an observed simultaneous baseline window. Each fault window must have reference support from all three no-fault trials and both clients.','','## Interpretation','','These are observed sustained decreases, not proof that failure alone caused every difference. Search maxima depend on window size, temporal correlation, reference variation, cache state, and background activity. Trial maxima and sample SD describe three repetitions; clients and overlapping windows are not independent repetitions. Percentage and absolute-MiB/s maxima can select different windows; both are in trial-maxima.csv. No clipping of negative decreases or exclusion of genuine zero-throughput fault windows is applied.','','A recovery subphase shorter than the requested window, such as remapping, has no valid whole-phase maximum; it is not reported as zero. Windows crossing recovery phases remain eligible for the primary metric and have combined phase labels.','','## Outputs','','- trial-maxima.csv: percentage and absolute maxima, UTC windows, phases, passes, progress, rates, and baseline range.','- profile-summary.csv: 10/30/60-second and phase sensitivity summaries.','- windows/: accepted and rejected candidate windows with reasons, losslessly compressed.','- exclusion-counts.csv and progress-proxy-audit.csv: denominator/support audit.','- plots/: primary 30-second rolling measurements with pass-transition shading and worst windows.','- method.json: exact parameters and reference definition.']
 (out/'README.md').write_text('\n'.join(lines)+'\n')

def plots(out,data,guard=6.):
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 for profile,trials in data.items():
  fig,axes=plt.subplots(len(trials)*2,1,figsize=(11,3.5*len(trials)),squeeze=False)
  for index,(trial,fault,e,rows,valid) in enumerate(trials):
   a0=axes[2*index,0];a1=axes[2*index+1,0];origin=e['down'];end=e['healthy'];t=np.arange(origin,end,3.)
   raw=sum(np.interp(t,c.series.t,c.series.rate) for c in fault.values());a0.plot((t-origin)/60,raw,color='0.75',lw=.5,label='Raw aggregate RBD read')
   x=np.array([(r['start_epoch']+r['end_epoch'])/2 for r in rows]);actual=[r['fault_aggregate_mib_s'] if r['accepted'] else np.nan for r in rows];reference=[r['reference_aggregate_mib_s'] if r['accepted'] else np.nan for r in rows];drop=[r['decrease_pct'] if r['accepted'] else np.nan for r in rows]
   a0.plot((x-origin)/60,actual,color='#126e82',lw=1,label='Valid 30s fault throughput');a0.plot((x-origin)/60,reference,color='#dd8d00',lw=1,label='Progress-conditioned reference');a1.plot((x-origin)/60,drop,color='#a02040',lw=1)
   for ax in [a0,a1]:
    for key,label,color in [('marked_out','OSD out','#5b2c6f'),('recovering','Repair start','#238443')]:ax.axvline((e[key]-origin)/60,color=color,ls='--',lw=.8,label=label)
    for c in fault.values():
     for p,q in zip(c.passes,c.passes[1:]):
      left=max(origin,p.end-guard);right=min(end,q.start+guard)
      if right>left:ax.axvspan((left-origin)/60,(right-origin)/60,color='0.5',alpha=.15)
    if valid:
     best=max(valid,key=lambda r:r['decrease_pct']);ax.axvspan((best['start_epoch']-origin)/60,(best['end_epoch']-origin)/60,color='#ffb000',alpha=.3)
    ax.grid(alpha=.2);ax.set_xlim(0,(end-origin)/60)
   a0.set_ylim(bottom=0);a0.set_title(f'{profile}, fault source trial {trial:02d}');a0.set_ylabel('Aggregate MiB/s');a0.legend(fontsize=7,loc='upper right');a1.set_ylabel('Decrease (%)');a1.set_xlabel('Minutes after confirmed OSD down');a1.axhline(0,color='0.5',lw=.6)
  fig.tight_layout();(out/'plots').mkdir(exist_ok=True)
  fig.savefig(out/'plots'/f'{profile}-30s.png',dpi=160);plt.close(fig)

def capture_provenance(out):
 import subprocess
 files={}
 for trial in sorted((ROOT/'results').glob('*/*/trial-*/trial.json')):
  if not json.loads(trial.read_text())['included']:continue
  used=[trial]
  for h in HOSTS:
   used += [trial.parent/h/'results.json',trial.parent/h/'performance.csv.gz']
   used += [trial.parent/h/f'pass-{i:02d}-throughput.csv.gz' for i in range(1,4)]
  for p in used:files[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
 commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True).stdout.strip()
 info={'source_data_git_head_at_analysis':commit,'analysis_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'numpy_version':np.__version__,'inputs_sha256':files}
 (out/'provenance.json').write_text(json.dumps(info,indent=2)+'\n')

def plots_from_saved(args):
 out=ROOT/args.output;data={};method=json.loads((out/'method.json').read_text())
 for profile in PROFILES:
  for t in sorted((ROOT/'results'/profile/'fault-osd3').glob('trial-*')):
   meta=json.loads((t/'trial.json').read_text())
   if not meta['included']:continue
   fault={h:Client(t/h,args) for h in HOSTS};r=fault['node12'].result;events={k:ts(r['t_'+k]) for k in ['down','marked_out','recovering','healthy']}
   with gzip.open(out/'windows'/profile/f'trial-{meta["source_trial"]:02d}'/'down_to_repair-30s.csv.gz','rt') as f:rows=list(csv.DictReader(f))
   for row in rows:
    row['accepted']=row['accepted']=='True'
    for k in ['start_epoch','end_epoch','fault_aggregate_mib_s','reference_aggregate_mib_s','decrease_pct']:row[k]=float(row[k]) if row[k] else np.nan
   data.setdefault(profile,[]).append((meta['source_trial'],fault,events,rows,[r for r in rows if r['accepted']]))
 plots(out,data,method['boundary_guard_s'])

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',default='derived/throughput-drop');p.add_argument('--windows',type=float,nargs='+',default=[10.,30.,60.]);p.add_argument('--grid',type=float,default=3.);p.add_argument('--boundary-guard',type=float,default=6.);p.add_argument('--max-sample-gap',type=float,default=6.);p.add_argument('--progress-tolerance',type=float,default=.01);p.add_argument('--no-plots',action='store_true');p.add_argument('--plots-only',action='store_true');a=p.parse_args()
 if min([*a.windows,a.grid,a.max_sample_gap,a.progress_tolerance])<=0 or a.boundary_guard<0:p.error('Positive windows/grid/gap/tolerance required')
 if a.plots_only:plots_from_saved(a)
 else:
  if 30. not in a.windows:p.error('Include the primary 30-second window in --windows')
  print(analyze(a))
