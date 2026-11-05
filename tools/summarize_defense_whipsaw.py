"""Diagnostics for the frozen offline comparison; no live-model writes."""
from pathlib import Path
import sys, json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT)]
from research_defense_whipsaw import targets, CANDIDATES


def main():
    out = ROOT / 'release/whipsaw-research'
    nav = pd.read_csv(out / 'nav_actual_BITO_next_open.csv', index_col=0, parse_dates=True)
    p = pd.read_csv(ROOT / 'data/equities.csv', index_col=0, parse_dates=True)
    btc = pd.read_csv(ROOT / 'data/btc.csv', parse_dates=['date_utc']).set_index('date_utc').close
    rows, annual, episodes, changes = [], [], [], []
    for config in CANDIDATES:
        name = config['name']
        t, ind, gold = targets(p, btc, config)
        t = t.reindex(nav.index)
        ind = ind.reindex(nav.index)
        label = np.where(t.GLD > 0, np.where(t['BRK.B'] > 0, 'MIX', 'GLD'),
                         np.where(t['BRK.B'] > 0, 'BRK', np.where(t.CASH > .999, 'CASH', 'RISK')))
        transitions = []
        for i in range(1, len(label)):
            if label[i] != label[i - 1]:
                transitions.append((i, label[i - 1], label[i]))
        trip = []
        for a, b in zip(transitions, transitions[1:]):
            i, prior, selected = a
            j, previous, back = b
            if {prior, selected} == {'GLD', 'BRK'} and prior == back and selected == previous:
                trip.append((i, j))
        relative = nav[name] / nav.baseline
        # Relative daily returns isolate dates on which performance diverges.
        changed = relative.pct_change(fill_method=None).abs() > 1e-10
        for d in nav.index[changed]:
            changes.append(dict(model=name, date=str(d.date()), relative_return=float(relative.pct_change(fill_method=None).loc[d])))
        rows.append(dict(model=name, direct_defense_roundtrips_5=sum(j-i<=5 for i,j in trip),
                         direct_defense_roundtrips_10=sum(j-i<=10 for i,j in trip),
                         divergent_return_days=int(changed.sum()),
                         terminal_nav_vs_baseline=float(relative.iloc[-1]-1)))
        for i,j in trip:
            if j-i<=10:
                episodes.append(dict(model=name,signal_entry=str(nav.index[i].date()),signal_exit=str(nav.index[j].date()),
                                     sessions=j-i,entry_state=int(ind.state.iloc[i]),exit_state=int(ind.state.iloc[j]),
                                     type='direct_target_roundtrip'))
        for year in sorted(nav.index.year.unique()):
            pos=np.flatnonzero(nav.index.year==year); lo=max(0,pos[0]-1); hi=pos[-1]+1
            v=nav[name].iloc[lo:hi]
            annual.append(dict(model=name,year=int(year),return_=float(v.iloc[-1]/v.iloc[0]-1),
                               mdd=float((v/v.cummax()-1).min()),partial=year in (nav.index[0].year,nav.index[-1].year)))
    pd.DataFrame(rows).to_csv(out/'diagnostics.csv',index=False)
    pd.DataFrame(episodes).to_csv(out/'rapid_roundtrips.csv',index=False)
    pd.DataFrame(annual).to_csv(out/'annual_returns.csv',index=False)
    pd.DataFrame(changes).to_csv(out/'relative_return_changes.csv',index=False)
    print(pd.DataFrame(rows).to_string(index=False))
    print(pd.DataFrame(episodes).to_string(index=False))


if __name__ == '__main__':
    main()
