"""Prospective close-signal journal. Existing observations are never rewritten."""
import math
from datetime import datetime, timezone

ASSETS = ("TQQQ", "BRK.B", "GLD", "CASH", "SOXL", "BITO")
CONTRACT = "audited-mixed-close-v1"


def append(journal, snapshot, prices, candidates, recorded_at=None):
    if not journal:
        journal = dict(schema_version=1, contract=CONTRACT, observations=[])
    if journal.get("schema_version") != 1 or journal.get("contract") != CONTRACT:
        raise ValueError("Unsupported shadow journal")
    date = snapshot["market_date"]
    rows = journal["observations"]
    if rows and date <= rows[-1]["market_date"]:
        return journal
    close = {asset: (1.0 if asset == "CASH" else float(prices[asset])) for asset in ASSETS}
    if not all(math.isfinite(x) and x > 0 for x in close.values()):
        raise ValueError("Missing shadow close prices")
    policies = []
    for model, weights in candidates:
        target = {asset: float(weights[asset]) for asset in ASSETS}
        if not all(math.isfinite(x) and x >= -1e-10 for x in target.values()) or abs(sum(target.values()) - 1) > 1e-8:
            raise ValueError("Invalid shadow allocation")
        policies.append(dict(model_id=model.id, model_fingerprint=model.fingerprint, target=target))
    if len(policies) != 2 or policies[0]["model_id"] == policies[1]["model_id"]:
        raise ValueError("Invalid shadow policies")
    rows.append(dict(market_date=date, recorded_at=recorded_at or datetime.now(timezone.utc).isoformat(),
                     data_fingerprint=snapshot["data_fingerprint"], close=close, policies=policies,
                     state=snapshot["state"], source="public model input; not an account record"))
    return journal
