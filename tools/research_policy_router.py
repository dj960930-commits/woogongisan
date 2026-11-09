"""Same-ledger expert selection with stateful actions and past-only annual routing."""
import json,hashlib
import numpy as np
import pandas as pd
from research_defense_redesign import ROOT,AUDIT,replay,metrics
from models.registry import load_model

OUT=ROOT/'release/model-research/studies/policy-router'
PROTOCOL=dict(signals=[[5,21],[21,63]],fractions=[.5,1.],directions=[1,2],
    actions='existing / other defensive asset / cash',
    entry='short disagrees and original EMA advantage weakening over21 sessions',
    hold='freeze chosen asset until short reverses, defense ends, original asset changes, or state1',
    cash='ablation on/off: both below own SMA63 and both21-session cash excess negative; separate action, not automatic in every expert',
    legacy='retain original Cross/D25 cash; no short intervention state1',
    refit='annual, only prior closed month returns, minimum24 months',
    objective='counterfactual same-policy net log NAV increments over baseline',
    uncertainty='optional mean minus1.28*SE of consecutive3-month blocks; heuristic, not calibrated confidence',
    comparison='expanding pooled, expanding direction-specific, rolling36month direction-specific, conservative direction-specific',
    caveat='retrospective policy design after viewing history, not independent OOS')

def experts(p,btc,cash_enabled=False):
    base,ind=load_model('woogong-1.3-d').evaluate(p,btc);ix=base.index;b=base.to_numpy()
    long=np.where(b[:,2]>0,2,np.where(b[:,1]>0,1,3));state=ind.state.to_numpy()
    gap=np.log(ind.defense_fast/ind.defense_slow);weak=np.where(long==2,gap.diff(21)<0,gap.diff(21)>0)
    x=p[['BRK.B','GLD']];cash=(1+p.cash_return).cumprod()
    ex=np.log(x/x.shift(21)).sub(np.log(cash/cash.shift(21)),axis=0)
    both=((x<x.rolling(63).mean())&(ex<0)).all(axis=1).reindex(ix).to_numpy()
    ts={'baseline':b};meta={}
    for f,s in [(5,21),(21,63)]:
        r=p.GLD/p['BRK.B'];short=pd.Series(np.where(r.ewm(span=f,adjust=False,min_periods=f).mean()>r.ewm(span=s,adjust=False,min_periods=s).mean(),2,1),index=p.index).reindex(ix).to_numpy()
        for direction in [1,2]:
            for fraction in [.5,1.]:
                name=f'ema{f}_{s}_from{direction}_w{fraction}'+('_cash' if cash_enabled else '');t=b.copy();active=None
                for i in range(len(ix)):
                    if state[i] in [0,1] or long[i]!=direction:active=None;continue
                    if active is not None and ((active!=3 and short[i]!=active) or (active==3 and not both[i])):active=None
                    if cash_enabled and both[i]:active=3
                    elif active is None and weak[i] and short[i]!=long[i]:active=int(short[i])
                    if active is not None:
                        budget=(b[i,1]+b[i,2])*fraction;t[i,1:3]*=1-fraction;t[i,active]+=budget
                assert np.allclose(t.sum(axis=1),1) and np.allclose(t[state==0],b[state==0])
                ts[name]=t;meta[name]=direction
    return ix,ts,meta,long

def main():
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'protocol.json').write_text(json.dumps(PROTOCOL,indent=2),encoding='utf-8')
    p=pd.read_csv(ROOT/'data/equities.csv',index_col=0,parse_dates=True)
    btc=pd.read_csv(ROOT/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
    bi,ts,meta,long=experts(p,btc);_,ct,cm,_=experts(p,btc,True);ts.update(ct);meta.update(cm)
    _,st,_,_=experts(p.loc[:'2023-12-29'],btc.loc[:'2023-12-29']);_,cs,_,_=experts(p.loc[:'2023-12-29'],btc.loc[:'2023-12-29'],True);st.update(cs)
    for name in ts:np.testing.assert_allclose(ts[name][bi<='2023-12-29'],st[name],atol=1e-12,rtol=0)
    future=p.copy();future.loc[future.index>'2023-12-29',['QQQ','BRK.B','GLD','TQQQ','SOXL']]*=2
    _,ft,_,_=experts(future,btc);_,fc,_,_=experts(future,btc,True);ft.update(fc)
    for name in ts:np.testing.assert_allclose(ts[name][bi<='2023-12-29'],ft[name][bi<='2023-12-29'],atol=1e-12,rtol=0)
    allrows=[];logs=[]
    for period in ['actual_BITO','long_synthetic']:
        z=np.load(AUDIT/f'inputs_{period}.npz');ix=pd.DatetimeIndex(z['dates']);pos=bi.get_indexer(ix);names=list(ts)
        arr=np.stack([ts[n][pos] for n in names]);ll=long[pos];mode='next_open' if period=='actual_BITO' else 'next_close'
        # All experts run the exact dynamic actions on the same ledger. Labels
        # are the realised counterfactual net NAV returns, not frozen21day holds.
        trainnav,*_=replay(arr,z['op'],z['cl'],z['rf'],z['div'],mode,0,1)
        counter=pd.DataFrame(trainnav.T,index=ix,columns=names)
        month=counter.resample('ME').last();month=month.loc[month.index<=ix[-1]]
        logret=np.log(month/month.shift(1)).dropna();excess=logret.sub(logret.baseline,axis=0)
        routed=[];router_names=[]
        for policy in ['pooled','direction','rolling36','conservative']:
            t=arr[0].copy()
            for year in sorted(set(ix.year)):
                history=excess.loc[excess.index<pd.Timestamp(year=year,month=1,day=1)]
                if policy=='rolling36':history=history.tail(36)
                picks={}
                for direction in ([0] if policy=='pooled' else [1,2]):
                    pool=[n for n in names[1:] if direction==0 or meta[n]==direction]
                    scores={}
                    for n in pool:
                        if len(history)<24:continue
                        score=float(history[n].mean())
                        if policy=='conservative':
                            v=history[n].to_numpy();v=v[-(len(v)//3)*3:].reshape(-1,3).mean(axis=1)
                            score-=1.28*v.std(ddof=1)/np.sqrt(len(v))
                        scores[n]=score
                    pick=max(scores,key=scores.get) if scores else None
                    if pick is not None and scores[pick]<=0:pick=None
                    picks[direction]=pick
                    assert len(history)==0 or history.index[-1]<pd.Timestamp(year=year,month=1,day=1)
                    logs.append(dict(period=period,router=policy,year=int(year),direction=direction,months=len(history),pick=pick,score=scores.get(pick,0),last_training_month=str(history.index[-1].date()) if len(history) else None))
                for j in np.flatnonzero(ix.year==year):
                    pick=picks.get(0) if policy=='pooled' else picks.get(int(ll[j]))
                    if pick is not None:t[j]=arr[names.index(pick),j]
            routed.append(t);router_names.append('router_'+policy)
        targets=np.concatenate([arr,np.stack(routed)]);labels=names+router_names
        scenarios=[(mode,0,1),(mode,.003,1),(mode,.003,3)]
        if period=='actual_BITO':scenarios.append(('next_close',0,1))
        for execution,slip,delay in scenarios:
            nav,tr,turn,fee=replay(targets,z['op'],z['cl'],z['rf'],z['div'],execution,slip,delay)
            if period=='actual_BITO' and execution=='next_open' and slip==0:
                old=np.load(AUDIT/'nav_next_open_s0_d1_f1_cash00.npz');np.testing.assert_allclose(nav[0],old['nav'][list(old['names']).index('V1.3-D')],atol=1e-10,rtol=1e-10)
            for k,name in enumerate(labels):
                for window,start in [('full',ix[0]),('post2024',pd.Timestamp('2024-01-01'))]:
                    use=np.flatnonzero(ix>=start);lo=max(0,use[0]-1)
                    allrows.append(dict(period=period,model=name,window=window,mode=execution,slippage=slip,delay=delay,**metrics(nav[k,lo:],ix[lo:],tr[k,lo:],turn[k,lo:],fee[k,lo:])))
            if slip==0 and delay==1:pd.DataFrame(nav.T,index=ix,columns=labels).to_csv(OUT/f'nav_{period}_{execution}.csv')
    results=pd.DataFrame(allrows);results.to_csv(OUT/'metrics.csv',index=False);pd.DataFrame(logs).to_csv(OUT/'selection_log.csv',index=False)
    info=dict(protocol=PROTOCOL,fingerprint=load_model('woogong-1.3-d').fingerprint,checks=['2023 signal-prefix equality','annual training months strictly prior','same dynamic-policy ledger for training and replay','baseline actual NAV parity','attack parity','weights sum1'],
        caveats=['counterfactual experts have their own prior holdings, actual router switch costs handled by final replay','experts track public counterfactual state even while not selected','no calibrated probability claim','2015 synthetic BITO; previously viewed history'],
        hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [__import__('pathlib').Path(__file__),ROOT/'tools/research_defense_redesign.py',ROOT/'tools/research_defense_whipsaw.py',ROOT/'data/equities.csv',ROOT/'data/btc.csv',AUDIT/'inputs_actual_BITO.npz',AUDIT/'inputs_long_synthetic.npz']})
    (OUT/'manifest.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    q=results[(results.period=='actual_BITO')&(results.window=='full')&(results['mode']=='next_open')&(results.slippage==0)]
    print(q[['model','cagr','mdd','trade_days']].to_string(index=False))
    s='# 동일 거래정책 기반 장·단기 선택 연구\n\n'
    s+='장기수익 우선. EMA5/21 주신호, EMA21/63 비교신호를 고정하고 방어 진입·유지·철회·현금 행동을 같은 장부에서 평가했다. 기존 현금 비중과 공격 전환을 유지한다. 단기 선택을 고정21일 보유하는 이전 학습 점수는 사용하지 않았다. 전량과50% 개입을 비교했다.\n\n'
    s+='## 선택 방법\n\n과거 확정 월별 비용후 로그수익에서 기존 대비 증가분을 계산한다. 매년 최소24개월 이후 전체과거 통합/방향별/최근36개월 방향별/방향별 불확실성차감의 네 방법을 비교했다. 점수가 양수일 때만 단기를 선택하고 아니면 기존을 유지한다. 보수적 방법은3개월 블록 점수의 표준오차1.28배를 차감하는 휴리스틱이며 통계적 신뢰수준을 보장하지 않는다. 당시 이후 자료는 선택에 쓰지 않는다. 최종 혼합 정책은 별도 장부로 다시 실행해 정책 변경 매매비용을 반영했다.\n\n'
    s+='## 기본 실제구간 결과\n\n2021-10-20~2026-10-20, 달러, 다음시가, 편도0.1%.\n\n|정책|연복리|최대낙폭|매매일|\n|---|---:|---:|---:|\n'
    for r in q.itertuples():s+=f'|{r.model}|{r.cagr:.2%}|{r.mdd:.2%}|{r.trade_days}|\n'
    s+='\n## 장기와 비용\n\n|자료|정책|체결|추가비용|지연|연복리|최대낙폭|\n|---|---|---|---:|---:|---:|---:|\n'
    for r in results[(results.window=='full')&(results.model.str.startswith('router_')|results.model.eq('baseline'))].itertuples():s+=f'|{r.period}|{r.model}|{r.mode}|{r.slippage:.2%}|{r.delay}|{r.cagr:.2%}|{r.mdd:.2%}|\n'
    s+='\n## 判定\n\n금보유 방향만 개입하는 EMA5/21 전량 후보는 기본 실제구간 연복리48.91%로 기존47.63%보다 높았다. 그러나 다음종가52.73% 대 기존53.12%, 3일지연+추가0.3%에서는27.87% 대31.71%, 장기합성72.58% 대74.18%로 열세였다. 사후 개선 후보이며 강건하게 우월한 규칙으로 확정하지 않는다.\n\n실제자료에서는 네 선택기가 모두 기존을 유지했다. 이는 개선 성공이나 선택기 완성의 증거가 아니라 과거24개월 이상 성과로 단기를 승인할 근거가 없었다는 결과다. 장기합성에서는 최근36개월 선택기가 일부 개입했으나 연복리가71.41%로 기존74.18%보다 낮았다.\n\n현금조건을 강제로 모든정책에 합치는대신 유무를분리한16후보를 비교했다. 새로강제현금을넣지않은후보도 기존Cross/D25현금은그대로유지한다. 고정신호2개,방향2개,비중2개,현금유무2개의작은구성으로제한했다.\n'
    s+='\n## 한계\n\n既存 자료를 이미 검토한 뒤 설계한 후속 실험이다. 과거만 쓰는 연도별 선택도 완전한 미사용 검증은 아니다. 2015 장기 BITO는 합성 자료이고 실제 구간과 독립 표본이 아니다. 세금·환전·시장충격·장중낙폭 제외. 모듈 진입/철회 판정은 종가 기준이며 실제 실행에는 다음거래일·밴드·대기주문이 적용된다. 전문가의 가상 상태는 선택되지 않을 때도 공개 과거 신호로 추적한다. 정책을 고를 때 그 정책을 지금 새로 시작하는 별도 경로까지 모두 재최적화한 것은 아니다.\n\n운영모델 변경 없음. metrics.csv에2024이후와전조건, selection_log.csv에선택한정책과마지막학습일, manifest.json에코드·입력해시 기록.\n'
    (OUT/'report.md').write_text(s.replace('既存','기존').replace('判定','판정'),encoding='utf-8')

if __name__=='__main__':main()
