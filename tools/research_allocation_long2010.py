from pathlib import Path
R=Path(__file__).resolve().parents[1]
s=(R/'tools/research_allocation_combinations.py').read_text(encoding='utf-8-sig').split('metrics=[]')[0]
s=s.replace("p=pd.read_csv(R/'data/equities.csv',index_col=0,parse_dates=True)","p=pd.read_csv(R/'data/validation/long2010/reconstructed_inputs.csv.gz',index_col=0,parse_dates=True).loc[:'2026-10-20']")
exec(s)
OUT=R/'release/model-research/studies/allocation-long2010';OUT.mkdir(exist_ok=True);ix=base.index
records=[];annual=[]
for drag in [0.,-.05338828097800662,-.10]:
 cl=p.reindex(ix)[['TQQQ','BRK.B','GLD','cash_return','SOXL','BITO','QQQ']].copy();cl.columns=['TQQQ','BRK.B','GLD','CASH','SOXL','BITO','QQQ'];cl.CASH=1.
 proxy=b.shift(1).reindex(ix);valid=proxy.notna();cl.BITO=proxy
 cl.loc[valid,'BITO']*=np.exp(drag*(ix[valid]-ix[valid][0]).days.to_numpy()/365.25)
 t=np.stack([v.reindex(ix).to_numpy() for v in variants.values()]);missing=cl.isna().to_numpy();assert not (t*np.broadcast_to(missing,t.shape)).any(),'Missing price exposure'
 cl=cl.ffill().fillna(1.).to_numpy();rf=p.cash_return.reindex(ix).fillna(0).to_numpy();div=np.zeros_like(cl)
 for mode in ['same_close_reference','next_close']:
  for extra in [0.,.003]:
   nv,tr=batch(t,cl,cl,rf,div,extra,mode)
   for k,name in enumerate(names):records.append(dict(drag=drag,mode=mode,extra=extra,name=name,start=str(ix[0].date()),end=str(ix[-1].date()),final=nv[k,-1],cagr=nv[k,-1]**(365.25/(ix[-1]-ix[0]).days)-1,trades=tr[k]))
   if mode=='same_close_reference' and extra==0:
    pd.DataFrame(nv.T,index=ix,columns=names).to_csv(OUT/f'nav_drag{drag:.6f}.csv.gz',compression='gzip')
    for year in sorted(set(ix.year)):
     ids=np.flatnonzero(ix.year==year);prior=nv[:,ids[0]-1] if ids[0] else np.ones(len(names))
     for k,name in enumerate(names):annual.append(dict(drag=drag,year=int(year),name=name,return_=nv[k,ids[-1]]/prior[k]-1))
f=pd.DataFrame(records);y=pd.DataFrame(annual);f.to_csv(OUT/'metrics.csv',index=False);y.to_csv(OUT/'annual.csv',index=False)
for drag in [0.,-.05338828097800662,-.10]:
 print('DRAG',drag);print(f[f.drag.eq(drag)&f['mode'].eq('same_close_reference')&f.extra.eq(0)].nlargest(8,'final')[['name','final','cagr']].to_string(index=False))
