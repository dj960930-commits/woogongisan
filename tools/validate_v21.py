"""Independent replay and evidence for V2.1, without changing live data."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from models.registry import load_model
from models.performance import replay


def stats(nav, dates, trades):
    dd=nav/np.maximum.accumulate(np.r_[1.,nav])[1:]-1
    daily=nav/np.r_[1.,nav[:-1]]-1
    cagr=float(nav[-1]**(365.25/(dates[-1]-dates[0]).days)-1)
    longest=count=0
    for value in dd:
        count=count+1 if value < -1e-10 else 0
        longest=max(longest,count)
    return dict(cagr=cagr,mdd=float(dd.min()),calmar=float(cagr/-dd.min()),
                final=float(nav[-1]),total_return=float(nav[-1]-1),
                trade_days=int(trades.sum()),worst_day=float(daily.min()),
                cvar95=float(np.sort(daily)[:max(1,int(np.ceil(len(daily)*.05)))].mean()),
                underwater_sessions=longest)


def main():
    current=load_model('woogong-v2')
    model=load_model('woogong-v2.1')
    prices=pd.read_csv(ROOT/'data/equities.csv',index_col=0,parse_dates=True)
    btc=pd.read_csv(ROOT/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
    targets,ind=model.evaluate(prices,btc)
    previous,_=current.evaluate(prices,btc)
    np.testing.assert_allclose(previous,pd.read_csv(ROOT/'data/validation/v2/reference_targets.csv.gz',index_col=0,parse_dates=True),atol=1e-12,rtol=0)
    # Reference policy was generated in the prior research, not by this adapter.
    from models import core_v1
    source=(ROOT/'models/core_v1.py').read_text(encoding='utf-8')
    source=source.replace(' clipped[:,2]+=np.where',' native=clipped[:,2].copy()\n clipped[:,2]+=np.where')
    source=source.replace(' return targets,indicators',' indicators["native_btc"]=native\n return targets,indicators')
    source=source.replace('.6/np.maximum(lever','.7/np.maximum(lever')
    scope=dict(core_v1.__dict__)
    exec(compile(source,str(ROOT/'models/core_v1.py'),'exec'),scope)
    raw,rawind=scope['evaluate'](prices,btc)
    expected=previous.copy()
    attack=ind.state.eq(0)
    expected.loc[attack]=raw.loc[attack]
    freed=(raw.BITO-rawind.native_btc).clip(lower=0).where(attack,0)
    expected.BITO-=freed;expected.CASH+=freed
    np.testing.assert_allclose(targets,expected,atol=1e-12,rtol=0)
    np.testing.assert_array_equal(targets.loc[~attack],previous.loc[~attack])
    output=ROOT/'data/validation/v21';output.mkdir(exist_ok=True)
    targets.to_csv(output/'reference_targets.csv.gz',compression='gzip')
    rows=[];primary_nav=None;primary_ix=None;annual=[]
    for period in ['actual_BITO','long_synthetic']:
        data=np.load(ROOT/f'data/validation/v2/inputs_{period}.npz')
        dates=pd.DatetimeIndex(data['dates'])
        for selected,t in [(model,targets),(current,previous)]:
            modes=['same_close_reference','next_close']+(['next_open'] if period=='actual_BITO' else [])
            for mode in modes:
                for extra in [0.,.003]:
                    nav,trades,_,_=replay(t.reindex(dates),data['cl'],data['rf'],data['div'],mode,data['op'],extra,model.band)
                    rows.append(dict(period=period,model=selected.id,mode=mode,slippage=extra,**stats(nav,dates,trades)))
                    if mode=='same_close_reference' and extra==0:
                        for year in sorted(set(dates.year)):
                            positions=np.flatnonzero(dates.year==year)
                            start=nav[positions[0]-1] if positions[0] else 1.
                            annual.append(dict(period=period,model=selected.id,year=int(year),
                                               return_=float(nav[positions[-1]]/start-1)))
                    if selected.id==model.id and period=='actual_BITO' and mode=='same_close_reference' and extra==0:
                        primary_nav=nav;primary_ix=dates
    # Frozen long proxy uses exactly the established 2010 input construction.
    longprices=pd.read_csv(ROOT/'data/validation/long2010/reconstructed_inputs.csv.gz',index_col=0,parse_dates=True).loc[:prices.index[-1]]
    for drag in [0.,-.05338828097800662,-.10]:
        for selected in [model,current]:
            t,_=selected.evaluate(longprices,btc)
            dates=t.index
            close=longprices.reindex(dates)[['TQQQ','BRK.B','GLD','cash_return','SOXL','BITO']].copy()
            close.columns=list(t.columns);close.CASH=1.
            proxy=btc.shift(1).reindex(dates);valid=proxy.notna()
            close.BITO=proxy
            close.loc[valid,'BITO']*=np.exp(drag*(dates[valid]-dates[valid][0]).days.to_numpy()/365.25)
            assert not (t.to_numpy()*close.isna().to_numpy()).any()
            cl=close.ffill().fillna(1.).to_numpy()
            rf=longprices.cash_return.reindex(dates).fillna(0).to_numpy()
            for mode in ['same_close_reference','next_close']:
                for extra in [0.,.003]:
                    nav,trades,_,_=replay(t,cl,rf,execution=mode,opening=cl,extra_cost=extra,band=model.band)
                    rows.append(dict(period='conditional_2010',model=selected.id,mode=mode,slippage=extra,
                                     annual_log_drag=drag,**stats(nav,dates,trades)))
    pd.DataFrame(rows).to_csv(output/'metrics.csv',index=False)
    pd.DataFrame(annual).to_csv(output/'annual.csv',index=False)
    def find(period,selected,mode='same_close_reference',extra=0):
        return next(row for row in rows if row['period']==period and row['model']==selected and row['mode']==mode and row['slippage']==extra)
    principal=find('actual_BITO',model.id)
    synthetic=find('long_synthetic',model.id)
    draw=primary_nav/np.maximum.accumulate(np.r_[1.,primary_nav])[1:]-1
    inputs=[ROOT/'data/equities.csv',ROOT/'data/btc.csv',ROOT/'data/validation/v2/inputs_actual_BITO.npz',
            ROOT/'data/validation/v2/inputs_long_synthetic.npz',ROOT/'data/validation/long2010/reconstructed_inputs.csv.gz',Path(__file__)]
    evidence={**model.metadata(),**{key:principal[key] for key in ('cagr','mdd','calmar')},
              'kind':'observed_BITO_same_close_reference','data_end':str(primary_ix[-1].date()),
              'execution':'same_close_reference',
              'label':'V2.1 · 당일 확정 종가 후 동일 가격 체결 가정 · 편도0.1% · USD·세전',
              'synthetic_cagr':synthetic['cagr'],
              'synthetic_label':'2015~2026 BTC 대용 · 실제 BITO 운용 성과 아님',
              'scenarios':rows,
              'curve':[dict(date=str(primary_ix[i].date()),nav=float(primary_nav[i]),drawdown=float(draw[i]))
                       for i in list(range(0,len(primary_ix)-1,5))+[len(primary_ix)-1]],
              'execution_review':dict(start=str(primary_ix[0].date()),end=str(primary_ix[-1].date()),
                                      basis='다음 거래일 시가 · 편도0.1% · USD·세전',
                                      selected=find('actual_BITO',model.id,'next_open'),
                                      baseline=find('actual_BITO',current.id,'next_open')),
              'validation':dict(target_rows=len(targets),independent_oos=False,actual_after_hours_fills_verified=False,
                                 live_broker_fills_verified=False,reference_policy_parity=True,
                                 source_hashes={str(file.relative_to(ROOT)):hashlib.sha256(file.read_bytes()).hexdigest() for file in inputs},
                                 note='193설정의 사후 연구. 2010대용은 혼합가격·BTC추적비용 가정. 현재 모델은 실제 매매 수익 인증이 아닌 신호 설정.')}
    (ROOT/f'models/evidence/{model.id}.backtest.json').write_text(json.dumps(evidence,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    print('V2.1 reference parity passed',len(targets),'days',model.fingerprint)
    print('Reference',principal)
    print('Next open',evidence['execution_review'])


if __name__=='__main__':
    main()
