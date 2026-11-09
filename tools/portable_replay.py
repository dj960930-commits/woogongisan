"""Self-financing transaction-cost factor used by the archived research ledgers."""
import numpy as np


def factor(goal, held, rate):
    sign = np.sign(goal - held)
    for _ in range(8):
        k = (1 + (rate * sign * held).sum(axis=1)) / (1 + (rate * sign * goal).sum(axis=1))
        new = np.sign(k[:, None] * goal - held)
        if np.array_equal(sign, new):
            break
        sign = new
    assert np.max(abs(k + (rate * abs(k[:, None] * goal - held)).sum(axis=1) - 1)) < 1e-12
    return k
