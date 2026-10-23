#!/usr/bin/env python3
"""Plot trial-level maximum sustained decreases and their sample dispersion."""
from pathlib import Path
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'derived/throughput-drop'
if __name__=='__main__':
 with (OUT/'profile-summary.csv').open() as f:rows=[x for x in csv.DictReader(f) if x['scope']=='down_to_repair' and float(x['window_s'])==30]
 order=['reed-solomon','replicated-3','lrc','clay','optlrc'];rows=sorted(rows,key=lambda x:order.index(x['profile']))
 assert len(rows)==5 and all(int(x['trials_with_valid_windows'])==3 for x in rows)
 fig,ax=plt.subplots(figsize=(9,4.5));x=list(range(5))
 ax.bar(x,[float(r['mean_trial_max_decrease_pct']) for r in rows],yerr=[float(r['sample_sd_pct']) for r in rows],capsize=4,color='#287da4',label='Mean of 3 trial maxima ± sample SD')
 ax.scatter(x,[float(r['worst_observed_decrease_pct']) for r in rows],color='#a02b4a',marker='D',s=35,label='Worst observed trial')
 ax.set_xticks(x,['RS(6,4)','Rep3 primary','LRC(6,2,4)','Clay(6,3,8)','OptLRC(10,6,4)']);ax.set_ylabel('Maximum sustained decrease (%)');ax.set_ylim(bottom=0);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);ax.legend(fontsize=8);fig.tight_layout()
 for ext in ['png','svg']:fig.savefig(OUT/('maximum-drop-comparison.'+ext),dpi=180)
