"""Fixed dual-sleeve experiments; never changes active profiles or publications."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from models.registry import load_model
from models.allocation_v21 import attack_weights
from models.performance import replay as canonical_replay
from tools.portable_replay import factor

ASSETS = ["TQQQ", "BRK.B", "GLD", "CASH", "SOXL", "BITO", "QQQ"]
RISK = ["TQQQ", "SOXL", "BITO", "QQQ", "GLD", "BRK.B"]
OUT = ROOT / "release/model-research/studies/dual-sleeve-study"


def scores(prices, btc, horizons=(63, 126), adjusted=False):
    x = prices[["TQQQ", "SOXL", "QQQ", "GLD", "BRK.B"]].copy()
    x["BITO"] = btc.shift(1).reindex(x.index)
    x = x.reindex(columns=RISK)
    logs = np.log(x.where(x > 0))
    cash = np.log1p(prices.cash_return.fillna(0))
    values = []
    for n in horizons:
        excess = logs - logs.shift(n)
        excess = excess.sub(cash.rolling(n, min_periods=n).sum(), axis=0)
        if adjusted:
            denominator = logs.diff().rolling(n, min_periods=n).std(ddof=1) * np.sqrt(n)
            excess = excess / denominator.where(denominator > 1e-12)
        values.append(excess)
    return sum(values) / len(values)


def sleeves(signal, index, relative_gate=True):
    values = signal.reindex(index)[RISK].to_numpy()
    finite = np.isfinite(values)
    eligible = finite & (values > 0)
    counts = eligible.sum(axis=1)
    weights = eligible / np.maximum(counts[:,None],1)
    absolute = pd.DataFrame(0.,index=index,columns=ASSETS)
    absolute.loc[:,RISK] = weights
    absolute.loc[counts==0,"CASH"] = 1.
    allowed = eligible if relative_gate else finite
    ranked_values = np.where(allowed,values,-np.inf)
    order = np.argsort(-ranked_values,axis=1,kind="stable")[:,:2]
    chosen = np.zeros_like(allowed)
    rows = np.arange(len(index))[:,None]
    chosen[rows,order] = allowed[rows,order]
    count = chosen.sum(axis=1)
    relative = pd.DataFrame(0.,index=index,columns=ASSETS)
    relative.loc[:,RISK] = chosen / np.maximum(count[:,None],1)
    relative.loc[count==0,"CASH"] = 1.
    return absolute, relative


def limit(raw):
    result = raw.copy()
    result.SOXL = np.minimum(result.SOXL, .4)
    lever = result.TQQQ + result.SOXL
    shrink = np.minimum(1., .7 / np.maximum(lever, 1e-16))
    result.TQQQ *= shrink
    result.SOXL *= shrink
    released = (raw.TQQQ + raw.SOXL - result.TQQQ - result.SOXL).clip(lower=0)
    result.CASH += released
    return result, released


def destination(prices, btc, index):
    # Same 63-day BTC/QQQ/GLD ranking as prior residual research, not tuned here.
    x = prices[["QQQ", "GLD"]].copy()
    x["BITO"] = btc.shift(1).reindex(x.index)
    s = np.log(x / x.shift(63)).reindex(index)[["BITO", "QQQ", "GLD"]]
    return s.fillna(-np.inf).idxmax(axis=1).where(s.max(axis=1) > 0, "CASH")


def add_residual(target, released, winner):
    result = target.copy()
    result.CASH -= released
    for asset in ["BITO", "QQQ", "GLD", "CASH"]:
        result[asset] += released.where(winner.eq(asset), 0.)
    return result


def build_targets(prices, btc):
    base, ind = load_model("woogong-v2.1").evaluate(prices, btc)
    base["QQQ"] = 0.
    base = base.reindex(columns=ASSETS)
    attack = ind.state.eq(0)
    winner = destination(prices, btc, base.index)
    # Only the leverage-induced cash is reallocated; other cash is preserved.
    unbounded = attack_weights(prices, btc, base.index, 1., .4)
    release = ((unbounded.TQQQ + unbounded.SOXL) - (base.TQQQ + base.SOXL)).clip(lower=0).where(attack, 0)
    variants = {"v21": base, "v21_residual63": add_residual(base, release, winner)}
    diagnostics = []
    for suffix, horizons, adjusted, gate in [
        ("raw", (63, 126), False, True),
        ("vol", (63, 126), True, True),
        ("short", (21, 63), False, True),
        ("no_relative_gate", (63, 126), False, False),
    ]:
        absolute, relative = sleeves(scores(prices, btc, horizons, adjusted), base.index, gate)
        mixture = (absolute + relative) / 2
        capped, freed = limit(mixture)
        t = base.copy()
        t.loc[attack] = capped.loc[attack]
        variants["hybrid_" + suffix] = t
        if suffix != "no_relative_gate":
            variants["hybrid_" + suffix + "_residual63"] = add_residual(
                t, freed.where(attack, 0), winner)
        if suffix == "raw":
            for label, raw in [("absolute_only", absolute), ("relative_only", relative)]:
                capped_single, _ = limit(raw)
                single = base.copy()
                single.loc[attack] = capped_single.loc[attack]
                variants[label] = single
            overlap = np.minimum(absolute[RISK], relative[RISK]).sum(axis=1)
            diagnostics = dict(attack_days=int(attack.sum()),
                               average_sleeve_overlap=float(overlap[attack].mean()),
                               same_sleeve_days=int(((absolute-relative).abs().max(axis=1)<1e-12)[attack].sum()))
    for t in variants.values():
        assert np.isfinite(t).all().all() and t.min().min() > -1e-10
        np.testing.assert_allclose(t.sum(axis=1), 1., atol=1e-12)
        assert (t.TQQQ+t.SOXL <= .7+1e-12).all() and (t.SOXL <= .4+1e-12).all()
        np.testing.assert_array_equal(t.loc[~attack], base.loc[~attack])
    return variants, diagnostics


def replay(target, close, opening, cash, distribution, mode, extra):
    """Seven-asset replay with the original six-asset ledger's exact ordering."""
    held = np.zeros(7); held[3] = 1.
    value = 1.; nav = []; trades = []
    rate = np.full(7, .001+extra); rate[3] = 0.
    goal = target[0].copy()
    pending = np.max(abs(goal-held)) >= .125
    for i in range(len(target)):
        traded = 0
        if i:
            gross = opening[i]/close[i-1]; gross[3] = 1+cash[i]
            gross -= distribution[i]*.001
            mark = held*gross; value *= mark.sum(); held = mark/mark.sum()
            gross = close[i]/opening[i]; gross[3] = 1.
            mark = held*gross; value *= mark.sum(); held = mark/mark.sum()
        use = (np.max(abs(target[i]-held)) >= .125) if mode == "same_close_reference" else (i > 0 and pending)
        if use:
            wanted = target[i] if mode == "same_close_reference" else goal
            k = factor(wanted[None, :], held[None, :], rate)[0]
            value *= k; held = wanted.copy(); traded = 1
        goal = target[i].copy(); pending = np.max(abs(goal-held)) >= .125
        nav.append(value); trades.append(traded)
    return np.array(nav), np.array(trades)


def metrics(nav, index, trades):
    dd = nav / np.maximum.accumulate(np.r_[1., nav])[1:] - 1
    daily = nav / np.r_[1., nav[:-1]] - 1
    cagr = nav[-1]**(365.25/(index[-1]-index[0]).days)-1
    count = longest = 0
    for value in dd:
        count = count+1 if value < -1e-10 else 0
        longest = max(longest, count)
    return dict(final=float(nav[-1]), total_return=float(nav[-1]-1), cagr=float(cagr),
                mdd=float(dd.min()), calmar=float(cagr/-dd.min()) if dd.min() < 0 else None,
                trade_days=int(trades.sum()), underwater_sessions=longest,
                cvar95=float(np.sort(daily)[:max(1,int(np.ceil(.05*len(daily))))].mean()))


def main():
    OUT.mkdir(exist_ok=True)
    prices = pd.read_csv(ROOT/"data/equities.csv", index_col=0, parse_dates=True)
    btc = pd.read_csv(ROOT/"data/btc.csv", parse_dates=["date_utc"]).set_index("date_utc").close
    variants, diagnostics = build_targets(prices, btc)
    print("Built",len(variants),"candidate targets",flush=True)
    # Prefix and future-perturbation invariance for all newly defined policies.
    cutoff = "2024-12-31"
    prefix, _ = build_targets(prices.loc[:cutoff], btc.loc[:cutoff])
    altered = prices.copy(); altered.loc[altered.index > cutoff] *= 2
    changed_btc = btc.copy(); changed_btc.loc[changed_btc.index > cutoff] *= 3
    future, _ = build_targets(altered, changed_btc)
    for key in variants:
        np.testing.assert_allclose(prefix[key], variants[key].loc[prefix[key].index], atol=1e-12, rtol=0)
        np.testing.assert_allclose(future[key].loc[:cutoff], variants[key].loc[:cutoff], atol=1e-12, rtol=0)
    print("Causal checks passed",flush=True)
    records = []; annual = []; segment_rows = []
    fixtures = []
    for name in ["actual_BITO", "long_synthetic"]:
        a = np.load(ROOT/f"data/validation/v2/inputs_{name}.npz")
        index = pd.DatetimeIndex(a["dates"])
        close = np.column_stack([a["cl"], prices.QQQ.reindex(index)])
        opening = np.column_stack([a["op"], prices.QQQ.reindex(index)])
        div = np.column_stack([a["div"], np.zeros(len(index))])
        fixtures.append((name, index, close, opening, a["rf"], div, variants))
    longprices = pd.read_csv(ROOT/"data/validation/long2010/reconstructed_inputs.csv.gz", index_col=0, parse_dates=True).loc[:prices.index[-1]]
    longtargets, _ = build_targets(longprices, btc)
    for drag in [0., -.05338828097800662, -.10]:
        index = longtargets["v21"].index
        close = longprices.reindex(index)[["TQQQ","BRK.B","GLD","cash_return","SOXL","BITO","QQQ"]].copy()
        close.columns = ASSETS; close.CASH = 1.
        proxy = btc.shift(1).reindex(index); valid = proxy.notna(); close.BITO = proxy
        close.loc[valid, "BITO"] *= np.exp(drag*(index[valid]-index[valid][0]).days.to_numpy()/365.25)
        for t in longtargets.values():
            assert not (t.to_numpy()*close.isna().to_numpy()).any(), "Exposure to missing price"
        close = close.ffill().fillna(1.).to_numpy()
        fixtures.append((f"long2010_drag{drag:.6f}", index, close, close.copy(),
                         longprices.cash_return.reindex(index).fillna(0).to_numpy(),
                         np.zeros_like(close), longtargets))
    for period, index, close, opening, cash, div, target_set in fixtures:
        print("Replaying",period,flush=True)
        full = {}
        for mode in ["same_close_reference", "next_close"]:
            for extra in [0., .003]:
                for name, t in target_set.items():
                    target = t.reindex(index).to_numpy()
                    nav, tr = replay(target, close, opening, cash, div, mode, extra)
                    if name == "v21" and period in ("actual_BITO", "long_synthetic"):
                        check = canonical_replay(target[:,:6], close[:,:6], cash, div[:,:6],
                                                 mode, opening[:,:6], extra, .125)[0]
                        np.testing.assert_allclose(nav, check, rtol=1e-10)
                    records.append(dict(period=period, name=name, mode=mode, extra=extra,
                                        start=str(index[0].date()), end=str(index[-1].date()), **metrics(nav,index,tr)))
                    if mode == "same_close_reference" and extra == 0:
                        full[name] = nav
                        for year in sorted(set(index.year)):
                            ids = np.flatnonzero(index.year==year)
                            prior = nav[ids[0]-1] if ids[0] else 1.
                            annual.append(dict(period=period,name=name,year=int(year),
                                               return_=float(nav[ids[-1]]/prior-1)))
        pd.DataFrame(full,index=index).to_csv(OUT/f"nav_{period}.csv.gz",compression="gzip")
        if period not in ("actual_BITO", "long2010_drag-0.053388"):
            continue
        segments = [("2010-02-11","2014-12-31"),("2015-01-01","2019-12-31"),
                    ("2020-01-01","2023-12-31"),("2024-01-01","2026-10-20")] if period.startswith("long2010") else [
                    ("2021-10-20","2023-12-31"),("2024-01-01","2026-10-20")]
        for start, end in segments:
            ids = np.flatnonzero((index>=start)&(index<=end))
            for name,t in target_set.items():
                nav,tr = replay(t.reindex(index).to_numpy()[ids],close[ids],opening[ids],
                                cash[ids],div[ids],"same_close_reference",0.)
                segment_rows.append(dict(period=period,name=name,start=str(index[ids[0]].date()),
                                         end=str(index[ids[-1]].date()),**metrics(nav,index[ids],tr)))
    pd.DataFrame(records).to_csv(OUT/"metrics.csv",index=False)
    pd.DataFrame(annual).to_csv(OUT/"annual.csv",index=False)
    pd.DataFrame(segment_rows).to_csv(OUT/"segments.csv",index=False)
    source_paths=[Path(__file__), ROOT/"data/equities.csv",ROOT/"data/btc.csv",
                  ROOT/"data/validation/long2010/reconstructed_inputs.csv.gz",
                  ROOT/"data/validation/v2/inputs_actual_BITO.npz",
                  ROOT/"data/validation/v2/inputs_long_synthetic.npz"]
    protocol=dict(horizons=[63,126],relative_top=2,absolute="Equal eligible assets; mean cash-excess log momentum>0",
                  relative="Top2 raw momentum among absolute-eligible assets; 21/63 and volatility adjusted are separate sensitivities",
                  residual="63-session raw log momentum BTC/QQQ/GLD, all negative -> cash",
                  constraints="Apply SOXL40% then TQQQ+SOXL70% after sleeves combined; constraint spill to cash or residual selector",
                  scope="Attack state only; V2.1 defense identical. Existing live profile is not changed.",
                  baseline_model_fingerprint=load_model("woogong-v2.1").fingerprint,
                  missing="Missing pre-inception prices cannot be held; BTC signal is shifted previous UTC close",
                  execution="same_close_reference / next_close; 0.1% each side plus0/.3% extra; 12.5pp rebalance band",
                  segment_basis="Each segment starts in cash; annual results continue holdings from full-period replay",
                  limitations="Retrospective research; no unseen OOS; QQQ signal close basis, no verified adjusted total return or opening prices. No next-open result fabricated. Long2010 is BTC proxy, not ETF record.",
                  diagnostics=diagnostics,
                  source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths},
                  checks=["all allocations sum to1", "global caps", "defense parity", "prefix invariance",
                          "future price perturbation", "canonical V2.1 book parity"])
    (OUT/"protocol.json").write_text(json.dumps(protocol,ensure_ascii=False,indent=2),encoding="utf-8")
    frame=pd.DataFrame(records)
    primary=["v21","v21_residual63","hybrid_raw","hybrid_raw_residual63","hybrid_vol","hybrid_short"]
    print(frame[frame.name.isin(primary)&frame.extra.eq(0)&frame["mode"].eq("same_close_reference")][
        ["period","name","final","cagr","mdd","calmar","trade_days"]].to_string(index=False))
    print("CHECKS PASSED",diagnostics)


if __name__ == "__main__":
    main()
