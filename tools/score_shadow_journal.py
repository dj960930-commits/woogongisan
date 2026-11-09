"""Score only observations recorded after the shadow journal was activated."""
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd
import pandas_market_calendars as calendars

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from models.performance import replay
from shadow_journal import ASSETS


def summarize(journal):
    rows = journal.get("observations", [])
    total = len(rows)
    if not rows:
        return dict(available=False, reason="Collecting new observations", observations=0)
    identities = [(x["model_id"], x["model_fingerprint"]) for x in rows[-1]["policies"]]
    first = len(rows) - 1
    while first > 0 and [(x["model_id"], x["model_fingerprint"]) for x in rows[first-1]["policies"]] == identities:
        first -= 1
    rows = rows[first:]
    if len(rows) < 2:
        return dict(available=False, reason="Collecting new model segment", observations=len(rows),
                    total_observations=total)
    ix = pd.DatetimeIndex([x["market_date"] for x in rows])
    expected = calendars.get_calendar("NYSE").schedule(ix[0].date(), ix[-1].date()).index
    if not ix.equals(expected):
        return dict(available=False, reason="Trading sessions missing or out of order", observations=len(rows))
    close = np.array([[row["close"][asset] for asset in ASSETS] for row in rows])
    targets = [np.array([[row["policies"][i]["target"][asset] for asset in ASSETS] for row in rows])
               for i in range(2)]
    results = []
    for identity, target in zip(identities, targets):
        nav, trades, _, _ = replay(target, close, np.zeros(len(rows)))
        dd = nav / np.maximum.accumulate(np.r_[1., nav])[1:] - 1
        results.append(dict(model_id=identity[0], fingerprint=identity[1],
                            final_multiple=float(nav[-1]), max_drawdown=float(dd.min()),
                            trade_days=int(trades.sum())))
    differs = np.max(abs(targets[0] - targets[1]), axis=1) > 1e-10
    starts = np.flatnonzero(differs & ~np.r_[False, differs[:-1]])
    return dict(available=True, first=rows[0]["market_date"], last=rows[-1]["market_date"],
                observations=len(rows), total_observations=total, differing_days=int(differs.sum()), events_started=len(starts),
                execution="Hypothetical same official close after the signal, 0.1% each side, 12.5% band",
                limitations="Mixed source price basis; USD before tax; cash return zero; no actual fills or FX.",
                results=results)


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site/shadow-journal.json"
    print(json.dumps(summarize(json.loads(path.read_text(encoding="utf-8"))), ensure_ascii=False, indent=2))
