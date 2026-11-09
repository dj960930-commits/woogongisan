"""Retrospective, non-overlapping forward-origin comparison; no parameter fitting."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from price_outlook import distribution

HORIZONS = (5, 21, 63)
SYMBOLS = ("TQQQ", "BRK.B", "GLD")
START = pd.Timestamp("2025-01-01")


def evaluate(series, horizon, start=START):
    series = series.astype(float).dropna()
    start_index = max(400, int(series.index.searchsorted(start)))
    rows = []
    for i in range(start_index, len(series) - horizon, horizon):
        past = series.iloc[:i + 1]
        try:
            q = distribution(past, horizon)
        except ValueError:
            continue
        actual = float(series.iloc[i + horizon] / series.iloc[i] - 1)
        estimated = np.expm1(q)
        sigma = float(np.log(past / past.shift(1)).dropna().tail(1261).std(ddof=1))
        bound = 1.2815515655446004 * sigma * np.sqrt(horizon)
        rows.append(dict(issued=str(series.index[i].date()), resolved=str(series.index[i+horizon].date()),
                         actual=actual, median=float(estimated[1]),
                         covered=bool(estimated[0] <= actual <= estimated[2]),
                         volatility_covered=bool(np.expm1(-bound) <= actual <= np.expm1(bound))))
    if not rows:
        return dict(origins=0)
    return dict(origins=len(rows), first=rows[0]["issued"], last=rows[-1]["resolved"],
                scenario_mae=float(np.mean([abs(x["median"]-x["actual"]) for x in rows])),
                unchanged_mae=float(np.mean([abs(x["actual"]) for x in rows])),
                scenario_coverage=float(np.mean([x["covered"] for x in rows])),
                volatility_coverage=float(np.mean([x["volatility_covered"] for x in rows])),
                windows=rows)


def main():
    source = ROOT / "data/equities.csv"
    prices = pd.read_csv(source, index_col=0, parse_dates=True)
    result = dict(protocol="frozen retrospective 2025+ origins; non-overlapping within each horizon",
                  caveat="Exploratory: history has been inspected during development; not independent future validation.",
                  source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  data_end=str(prices.index[-1].date()),
                  results={s:{str(h):evaluate(prices[s],h) for h in HORIZONS} for s in SYMBOLS})
    destination=ROOT/"data/validation/outlook_forward_20261109.json"
    destination.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    for symbol, horizons in result["results"].items():
        for horizon, metrics in horizons.items():
            print(symbol, horizon, {k:round(v,4) if isinstance(v,float) else v
                                    for k,v in metrics.items() if k!="windows"})


if __name__ == "__main__":
    main()
