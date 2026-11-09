"""Replay the proposed router from October through cached latest Nov4 close.

Public fresh fetch did not supply expected date; cached live snapshots supply
anchored close fields. Missing risk data is never invented or used for P&L.
"""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from research_bounded_intervention import ROOT,combine
from research_defense_redesign import AUDIT
from research_defense_whipsaw import replay
from models.registry import load_model

OUT=ROOT/'release/model-research/studies/october-replay'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    frozen=pd.read_csv(ROOT/'data/equities.csv',index_col=0,parse_dates=True)
    p=pd.read_csv(ROOT/'runtime/outlook-input.csv',index_col=0,parse_dates=True)
    pd.testing.assert_frame_equal(p.loc[frozen.index],frozen,check_freq=False)
    snapshots={};paths=[]
    for path in sorted((ROOT/'site/history').glob('*.json')):
        d=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(d,dict) or 'market_date' not in d:continue
        day=pd.Timestamp(d['market_date'])
        if day<pd.Timestamp('2026-10-30') or not d.get('raw_close') or d.get('mode')!='live':continue
        if day not in snapshots or d['generated_at']>snapshots[day]['generated_at']:snapshots[day]=d
        paths.append(path)
    anchor=pd.Timestamp('2026-10-30');assert anchor in snapshots
    fields=['QQQ','TQQQ','BRK.B','GLD']
    factors={s:float(p.loc[anchor,s]/snapshots[anchor]['raw_close'][s]) for s in fields}
    for day,s in sorted(snapshots.items()):
        if day<=p.index[-1]:continue
        p.loc[day]=np.nan
        for symbol in fields:p.loc[day,symbol]=s['raw_close'][symbol]*factors[symbol]
    p=p.sort_index();p.index.name=frozen.index.name
    assert p.index[-1]==pd.Timestamp('2026-11-04')
    btc=pd.read_csv(ROOT/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
    targets,ind=combine(p,btc);base=targets['baseline'];new=targets['entry_only']
    # Missing late BTC/adjusted risk fields cannot alter the decisions here:
    # all sessions are defensive, and a NECESSARY Cross condition is false.
    after=p.index>frozen.index[-1];di=p.index[after]
    assert ind.state.reindex(di).ne(0).all()
    r=p[['BRK.B','GLD']].pct_change(5,fill_method=None).reindex(di)
    chosen=np.where(ind.defense_fast.reindex(di)>ind.defense_slow.reindex(di),r.GLD,r['BRK.B'])
    necessary=(r['BRK.B']<0)&(r.GLD<0)&(chosen<=-.05)
    assert not necessary.any(), 'Need complete risk feed to decide Cross; do not infer'
    differences=[]
    for day,s in snapshots.items():
        if day not in base.index:continue
        np.testing.assert_allclose(base.loc[day].to_numpy(),[s['target'][a] for a in base.columns],atol=1e-10,rtol=0)
        for k in ['gap','qqq_drawdown','defense_fast','defense_slow']:
            differences.append(dict(day=str(day.date()),indicator=k,reconstructed=float(ind.loc[day,k]),cached=float(s['indicators'][k]),difference=float(ind.loc[day,k]-s['indicators'][k])))
    # Small cached-history revisions are retained in audit, never called exact.
    assert max(abs(x['difference']) for x in differences)<4e-6
    # The October approval is frozen at intervention entry. The conservative
    # three-closed-event mode was not approved and follows baseline throughout.
    approval=pd.read_csv(ROOT/'release/model-research/studies/past-selection/selection_log.csv')
    log=approval[(approval.period=='actual_BITO')&(approval.selector=='monthly_pair')&(approval.decision=='2026-10-01')].iloc[0]
    assert log.pick=='bounded::entry_only' and log.last_training_month=='2026-09-30'
    cache=pd.read_csv(ROOT/'release/model-research/studies/past-selection/nav_actual_BITO_next_open.csv',index_col=0,parse_dates=True)
    nv=cache[['baseline','monthly_pair_entrygate']].rename(columns={'monthly_pair_entrygate':'proposed'}).copy()
    canonical_end=nv.index[-1];assert canonical_end==frozen.index[-1]
    # At the anchor both books are purely defensive and no later trade is due
    # before Nov4 close. Thus close/close returns extend next-open NAV exactly,
    # without inventing unavailable future opening prices or risk asset marks.
    assert base.loc[canonical_end,'GLD']==1 and new.loc[canonical_end,'BRK.B']==1
    for day in p.index[p.index>canonical_end]:
        prev=p.index[p.index.get_loc(day)-1]
        assert base.loc[prev,'GLD']==1 and new.loc[prev,'BRK.B']==1, 'Unknown open fill would be needed'
        nv.loc[day,'baseline']=nv.loc[prev,'baseline']*(p.loc[day,'GLD']/p.loc[prev,'GLD'])
        nv.loc[day,'proposed']=nv.loc[prev,'proposed']*(p.loc[day,'BRK.B']/p.loc[prev,'BRK.B'])
    baseline_held=np.where(base.GLD.shift(1)>0,'GLD',np.where(base['BRK.B'].shift(1)>0,'BRK.B','공격자산/현금'))
    new_held=np.where(new.GLD.shift(1)>0,'GLD',np.where(new['BRK.B'].shift(1)>0,'BRK.B','공격자산/현금'))
    trace=pd.DataFrame(dict(state=ind.state,baseline_target=base[['BRK.B','GLD','CASH']].idxmax(axis=1),
        proposed_target=new[['BRK.B','GLD','CASH']].idxmax(axis=1),baseline_held=baseline_held,proposed_held=new_held,
        baseline_gold=base.GLD,baseline_brk=base['BRK.B'],proposed_gold=new.GLD,proposed_brk=new['BRK.B'],proposed_cash=new.CASH),index=base.index)
    attack=ind.state.eq(0);trace.loc[attack,['baseline_target','proposed_target']]='공격자산 배분'
    trace=trace.loc['2026-10-01':];trace.to_csv(OUT/'daily_trace.csv')
    end=nv.index[-1];start=pd.Timestamp('2026-09-30');returns=nv.loc[end]/nv.loc[start]-1
    before_entry=pd.Timestamp('2026-10-12');defense=nv.loc[end]/nv.loc[before_entry]-1
    a=np.load(AUDIT/'inputs_actual_BITO.npz');ax=pd.DatetimeIndex(a['dates']);entry=pd.Timestamp('2026-10-13');j=ax.get_loc(entry)
    # Invested defense sleeve from that actual next-open price to Nov4 close.
    brk_end=float(a['cl'][-1,1]*p.loc[end,'BRK.B']/p.loc[canonical_end,'BRK.B'])
    gold_end=float(a['cl'][-1,2]*p.loc[end,'GLD']/p.loc[canonical_end,'GLD'])
    sleeve_brk=(brk_end/a['op'][j,1])/(1+.001)-1
    sleeve_gold=(gold_end/a['op'][j,2])/(1+.001)-1
    # Separately replay the user's literal five-condition V1 from October.
    # Its one-way override persists; the supplied rule has no reverse exit.
    q=p['BRK.B']/p.GLD
    v1signal=(q.pct_change(5)>.02)&(q.pct_change(20)>.05)&(q>q.rolling(10).mean()*1.01)&(p.GLD<p.GLD.rolling(10).mean()*.99)&(p['BRK.B']>p['BRK.B'].rolling(5).mean())
    v1=base.copy();active=False;entry_signals=[]
    for day in v1.index[v1.index>=pd.Timestamp('2026-10-01')]:
        if ind.loc[day,'state'] not in [2,3,4] or base.loc[day,'GLD']==0:active=False
        elif not active and v1signal.loc[day]:active=True;entry_signals.append(str(day.date()))
        if active:
            v1.loc[day,'BRK.B']+=v1.loc[day,'GLD'];v1.loc[day,'GLD']=0
    v1nav=replay(v1.reindex(ax).to_numpy()[None,:,:],a['op'],a['cl'],a['rf'],a['div'])[0][0]
    vv=pd.Series(v1nav,index=ax)
    for day in p.index[p.index>canonical_end]:
        prev=p.index[p.index.get_loc(day)-1]
        assert v1.loc[prev,'BRK.B']==1
        vv.loc[day]=vv.loc[prev]*p.loc[day,'BRK.B']/p.loc[prev,'BRK.B']
    v1results=dict(raw_signal_dates=[str(d.date()) for d in v1signal.loc['2026-10-01':].index[v1signal.loc['2026-10-01':]]],
        applicable_defense_entry_signals=entry_signals,return_from_sep30=float(vv.loc[end]/vv.loc[start]-1),
        assumptions='Literal one-way GLD-to-BRK override applied from October only; hold until attack/forced state or long selector BRK; reverse rule not supplied')
    v1signal.loc['2026-10-01':].to_csv(OUT/'literal_v1_signals.csv')
    vv.loc[start:].to_csv(OUT/'literal_v1_nav.csv')
    result=dict(as_of=str(end.date()),month_start_basis='2026-09-30 close through Nov4 close',
        approval=dict(decision=log.decision,training_end=log.last_training_month,closed_opportunities=int(log.closed_events),
                      score=float(log.score),min_months=24,history_months=int(log.months)),
        october_to_latest={k:float(v) for k,v in returns.items()},difference_pp=float((returns.proposed-returns.baseline)*100),
        defense_after_signal_close={k:float(v) for k,v in defense.items()},
        invested_defense_from_oct13_open=dict(brk_entry_open=float(a['op'][j,1]),gold_entry_open=float(a['op'][j,2]),brk_return=float(sleeve_brk),gold_return=float(sleeve_gold),cost='entry buy0.1%; no exit liquidation assumed'),
        last_signal=dict(baseline=base.loc[end].to_dict(),proposed=new.loc[end].to_dict()),
        held_at_nov4_close=dict(baseline='GLD',proposed='BRK.B'),
        conservative_closed3='baseline path; only1 completed simulated opportunity before October',
        literal_user_v1=v1results,
        limitations=['hypothetical next-open research model, not actual account performance',
            'cached live snapshots; fresh public fetch did not supply Nov4 close',
            'risk data after frozen range incomplete, unused in this purely defensive segment; Cross necessary condition explicitly false',
            'appended closes anchored to Oct30 cached input; all cached targets agree; small defense EMA source discrepancy up to0.00000372 recorded in audit; cause not independently established',
            'no new open execution assumed after Oct20; Nov4 baseline BRK target executes next US session, not Nov4 close',
            'rules designed after seeing October, not independent prediction proof'])
    (OUT/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    p.to_csv(OUT/'reconstructed_inputs.csv');nv.loc[start:].to_csv(OUT/'october_nav.csv')
    files=[Path(__file__),ROOT/'runtime/outlook-input.csv',ROOT/'data/btc.csv',ROOT/'release/model-research/studies/past-selection/selection_log.csv',*paths]
    (OUT/'audit.json').write_text(json.dumps(dict(checks=['immutable frozen prefix','cached live targets agree exactly; indicator differences recorded','no new risk exposure','Cross precondition false regardless missing risk data','no post-anchor opening fill required','October approval trained through September only'],
        indicator_differences=differences,factors=factors,source_hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}),indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
