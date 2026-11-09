from pathlib import Path
R=Path(__file__).resolve().parents[1];src=(R/'tools/research_allocation_long2010.py').read_text(encoding='utf-8-sig');exec(src.split('records=[];annual=[]')[0])
import pandas as pd,numpy as np
names0=['current','L0_BTC_off','L20_BTC_off','L40_BTC_off','L80_CASH_off','L80_mom63_126_off','L0_mom63_trend'];out=[]
for start in ['2010-02-11','2012-01-01','2015-01-01','2018-01-01','2020-01-01','2022-01-01','2024-01-01']:
 dates=base.loc[start:].index;cl=p.reindex(dates)[['TQQQ','BRK.B','GLD','cash_return','SOXL','BITO','QQQ']].copy();cl.iloc[:,3]=1.
 proxy=b.shift(1).reindex(dates);valid=proxy.notna();cl.iloc[:,5]=proxy;cl.loc[valid,cl.columns[5]]*=np.exp(-.05338828097800662*(dates[valid]-dates[valid][0]).days.to_numpy()/365.25)
 cl=cl.ffill().fillna(1.).to_numpy();t=np.stack([variants[n].reindex(dates).to_numpy() for n in names0]);rf=p.cash_return.reindex(dates).fillna(0).to_numpy()
 nv,_=batch(t,cl,cl,rf,np.zeros_like(cl),0,'same_close_reference')
 for k,n in enumerate(names0):out.append(dict(start=str(dates[0].date()),end=str(dates[-1].date()),name=n,final=nv[k,-1],cagr=nv[k,-1]**(365.25/(dates[-1]-dates[0]).days)-1))
f=pd.DataFrame(out);f.to_csv(OUT/'start_sensitivity.csv',index=False);print(f.pivot(index='start',columns='name',values='cagr').round(4).to_string())
# Detailed cross-scenario selected results.
f=pd.read_csv(OUT/'metrics.csv');print(f[f.name.isin(names0)&f.extra.eq(0)&f['mode'].eq('same_close_reference')].to_string(index=False))

