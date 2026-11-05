"""Descriptive circular-block resampling of realised net excess performance.

Not future-return probabilities, not PBO, not a claim of a fully valid White
Reality Check. The centred maximum is a partial-family snooping diagnostic.
"""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from adaptive_family import ROOT,saved_nav

OUT=ROOT/'release/selection-uncertainty'
PRIMARY='bounded::entry_only';B=2000;SEED=20261105

def block_means(d,L,B,rng):
    n,k=d.shape;extended=np.vstack([d,d[:L-1]]);prefix=np.vstack([np.zeros((1,k)),np.cumsum(extended,axis=0)])
    starts=np.arange(n);full=prefix[starts+L]-prefix[starts];q,r=divmod(n,L)
    partial=prefix[starts+r]-prefix[starts] if r else None
    output=[]
    for lo in range(0,B,200):
        count=min(200,B-lo);sample=rng.integers(0,n,size=(count,q+(r>0)))
        total=full[sample[:,:q]].sum(axis=1)
        if r:total+=partial[sample[:,-1]]
        output.append(total/n)
    return np.vstack(output)

def main():
    OUT.mkdir(parents=True,exist_ok=True);rows=[];leaders=[]
    for period,mode in [('actual_BITO','next_open'),('long_synthetic','next_close')]:
        nav=saved_nav(period,mode);lr=np.log(nav/nav.shift(1)).dropna();ex=lr.sub(lr.baseline,axis=0).drop(columns='baseline')
        names=list(ex);primary=names.index(PRIMARY);d=ex.to_numpy();observed=d.mean(axis=0);best=int(np.argmax(observed))
        # Equal realised vectors do not constitute independent alternatives.
        unique=np.unique(np.round(d.T,12),axis=0).shape[0]
        for j,name in enumerate(names):leaders.append(dict(period=period,model=name,annual_log_excess=observed[j]*252))
        for L in [21,63]:
            sampled=block_means(d,L,B,np.random.default_rng(SEED+L))
            primary_means=sampled[:,primary]*252
            centred=sampled-observed
            null_max=np.maximum(0,centred.max(axis=1));best_stat=max(0.,observed[best])
            family_tail=(1+np.count_nonzero(null_max>=best_stat))/(B+1)
            lo,med,hi=np.quantile(primary_means,[.025,.5,.975])
            rows.append(dict(period=period,mode=mode,block_sessions=L,repetitions=B,defined_experts=len(names),unique_realised_paths=int(unique),
                primary_observed_annual_log_excess=float(observed[primary]*252),resampled_p025=float(lo),resampled_median=float(med),resampled_p975=float(hi),
                resampled_positive_fraction=float(np.mean(primary_means>0)),
                family_best=names[best],centred_family_tail_fraction=float(family_tail)))
    pd.DataFrame(rows).to_csv(OUT/'block_diagnostics.csv',index=False);pd.DataFrame(leaders).to_csv(OUT/'family_scores.csv',index=False)
    protocol=dict(seed=SEED,repetitions=B,block_lengths=[21,63],primary=PRIMARY,
        data='realised daily net log NAV differences vs same baseline, joint blocks across experts',
        null_diagnostic='centre each expert mean to zero then resample same blocks; compare max null mean to observed max',
        limitations=['NOT probability strategy will profit in future','NOT PBO or fully calibrated family-wide significance',
            'only current goal family, excludes earlier many studies and baseline optimisation','signals and orders NOT regenerated inside bootstrap',
            'stationarity and block adequacy assumptions uncertain; few episodes cannot be made plentiful by resampling',
            'percentile bands describe resampled observed performance, not guaranteed future coverage'],
        method_context='https://doi.org/10.1111/1468-0262.00152',
        code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8');print(pd.DataFrame(rows).to_string(index=False))

if __name__=='__main__':main()
