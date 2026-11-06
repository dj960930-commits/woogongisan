"""Adapted from local elliott_lab/elliott_rules.py for bounded, multi-symbol candidates.
Price geometry and subdivision evidence remain separate.
"""
import numpy as np
FAMILIES = ('impulse', 'truncated_impulse', 'leading_diagonal', 'ending_diagonal', 'zigzag', 'regular_flat', 'expanded_flat', 'running_flat', 'contracting_triangle', 'barrier_triangle', 'expanding_triangle', 'double_zigzag', 'triple_zigzag', 'double_three', 'triple_three')

def geometry(prices):
    """Outer-shape candidates. Flat 90/110% bounds are operational near-equality choices."""
    p = np.asarray(prices, dtype=float)
    if len(p) < 2 or np.any(np.diff(p) == 0):
        return []
    sign = np.sign(p[1] - p[0])
    z = (p - p[0]) * sign
    if not np.all(np.sign(np.diff(z)) == np.where(np.arange(len(p) - 1) % 2 == 0, 1, -1)):
        return []
    n = len(z) - 1
    out = []
    if n == 3:
        b = (z[1] - z[2]) / z[1]
        if 0 < z[2] < z[1] and z[3] > z[1]:
            out.append('zigzag')
        if 0.9 <= b <= 1.1 and z[3] > z[1]:
            out.append('regular_flat')
        if b > 1 and z[3] > z[1]:
            out.append('expanded_flat')
        if b > 1 and z[2] < z[3] < z[1]:
            out.append('running_flat')
    if n == 5:
        lengths = np.abs(np.diff(z))
        notshortest = lengths[2] >= min(lengths[0], lengths[4]) - 1e-10
        base = z[2] > 0 and z[3] > z[1] and (z[4] > z[2]) and (z[5] > z[4]) and notshortest
        if base and z[4] > z[1]:
            if z[5] >= z[3]:
                out.append('impulse')
            else:
                out.append('truncated_impulse')
        if base and z[4] < z[1] and (z[5] > z[3]):
            contraction = lengths[2] < lengths[0] and lengths[4] < lengths[2] and (lengths[3] < lengths[1])
            expansion = lengths[2] > lengths[0] and lengths[4] > lengths[2] and (lengths[3] > lengths[1])
            if contraction or expansion:
                out.extend(['leading_diagonal', 'ending_diagonal'])
        if z[2] < z[1] and z[3] < z[1] and (z[4] > z[2]) and (z[5] < z[3]) and (z[4] < z[3]):
            out.append('contracting_triangle')
        tol = abs(z[1]) * 0.1
        if abs(z[4] - z[2]) <= tol and z[3] < z[1] and (z[4] < z[5] < z[3]):
            out.append('barrier_triangle')
        if z[3] > z[1] and z[4] < z[2] and (z[5] > z[3]):
            out.append('expanding_triangle')
    return out
MOTIVE = {'impulse', 'truncated_impulse', 'leading_diagonal', 'ending_diagonal'}
CORRECTIVE = set(FAMILIES) - MOTIVE
TRIANGLES = {x for x in FAMILIES if 'triangle' in x}

def children_allowed(family, groups):
    """Require child-family membership and legal triangle/diagonal positions."""
    if family in ('impulse', 'truncated_impulse'):
        allowed = [{'impulse', 'leading_diagonal'}, CORRECTIVE - TRIANGLES, {'impulse'}, CORRECTIVE, {'impulse', 'ending_diagonal'}]
    elif family == 'leading_diagonal':
        return children_allowed('impulse', groups) or all((bool(g & {'zigzag'}) for g in groups))
    elif family == 'ending_diagonal':
        allowed = [{'zigzag', 'double_zigzag', 'triple_zigzag'}] * 5
    elif family == 'zigzag':
        allowed = [{'impulse', 'leading_diagonal'}, CORRECTIVE, {'impulse', 'ending_diagonal'}]
    elif family.endswith('_flat'):
        allowed = [CORRECTIVE - TRIANGLES, CORRECTIVE, {'impulse', 'ending_diagonal'}]
    elif 'triangle' in family:
        allowed = [CORRECTIVE - TRIANGLES] * 4 + [CORRECTIVE]
    else:
        return False
    return len(groups) == len(allowed) and all((bool(g & a) for g, a in zip(groups, allowed)))

def subdivision_groups(indices, close, fine_pivots):
    groups = []
    details = []
    for a, b in zip(indices[:-1], indices[1:]):
        middle = [p[0] for p in fine_pivots if a < p[0] < b]
        ids = [a] + middle + [b]
        types = set(geometry(close[ids]))
        groups.append(types)
        details.append(dict(start=int(a), end=int(b), legs=len(ids) - 1, types=sorted(types)))
    return (groups, details)

def envelope_ok(family, indices, d):
    if family not in {'impulse', 'truncated_impulse'}:
        return True
    s = np.sign(d.close.iloc[indices[1]] - d.close.iloc[indices[0]])
    i, j = (indices[3], indices[4])
    if j <= i:
        return False
    if s > 0:
        return bool(d.low.iloc[i + 1:j + 1].min() > d.high.iloc[indices[0]:indices[1] + 1].max())
    return bool(d.high.iloc[i + 1:j + 1].max() < d.low.iloc[indices[0]:indices[1] + 1].min())

def complete_catalog(d, all_pivots, degrees):
    c = d.close.to_numpy()
    records = []
    for degree, th in enumerate(degrees):
        pivots = all_pivots[th]
        for end in range(max(3, len(pivots) - 16), len(pivots)):
            for count in [3, 5]:
                if end < count:
                    continue
                chunk = pivots[end - count:end + 1]
                ids = [p[0] for p in chunk]
                families = geometry(c[ids])
                if not families:
                    continue
                for family in families:
                    if not envelope_ok(family, ids, d):
                        continue
                    verified = False
                    best = []
                    child_degree = None
                    for smaller in reversed(degrees[:degree]):
                        fine = [p for p in all_pivots[smaller] if p[1] <= chunk[-1][1]]
                        groups, details = subdivision_groups(ids, c, fine)
                        if children_allowed(family, groups):
                            verified = True
                            best = details
                            child_degree = smaller
                            break
                        if not best:
                            best = details
                    records.append(dict(family=family, degree=th, start=ids[0], end=ids[-1], confirmed=chunk[-1][1], indices=ids, direction=int(np.sign(c[ids[1]] - c[ids[0]])), subdivision_verified=verified, subdivision_degree=child_degree, children=best, verification_depth=2 if verified else 1))
    simple = [r for r in records if r['family'] in CORRECTIVE]
    by_start = {}
    for r in simple:
        by_start.setdefault((r['degree'], r['start']), []).append(r)
    combos = []
    for w in simple:
        if w['family'] in TRIANGLES:
            continue
        for x in by_start.get((w['degree'], w['end']), [])[:12]:
            for y in by_start.get((w['degree'], x['end']), [])[:12]:
                if y['direction'] != w['direction'] or x['direction'] == w['direction']:
                    continue
                iszz = w['family'] == 'zigzag' and y['family'] == 'zigzag'
                net = abs(c[y['end']] - c[w['start']])
                span = max(c[w['indices']].max(), c[y['indices']].max()) - min(c[w['indices']].min(), c[y['indices']].min())
                family = 'double_zigzag' if iszz and net > span * 0.5 else 'double_three'
                node = dict(family=family, degree=w['degree'], start=w['start'], end=y['end'], confirmed=max(w['confirmed'], x['confirmed'], y['confirmed']), indices=w['indices'] + x['indices'][1:] + y['indices'][1:], direction=w['direction'], subdivision_verified=all((a['subdivision_verified'] for a in [w, x, y])), subdivision_degree=None, children=[{k: r[k] for k in ['family', 'start', 'end', 'subdivision_verified']} for r in [w, x, y]], verification_depth=min((a['verification_depth'] for a in [w, x, y])) + 1)
                combos.append(node)
                if y['family'] in TRIANGLES:
                    continue
                for x2 in by_start.get((w['degree'], y['end']), [])[:6]:
                    for z in by_start.get((w['degree'], x2['end']), [])[:6]:
                        if z['direction'] != w['direction'] or x2['direction'] == w['direction']:
                            continue
                        trip = dict(node)
                        trip.update(family='triple_zigzag' if iszz and z['family'] == 'zigzag' else 'triple_three', end=z['end'], confirmed=max(node['confirmed'], x2['confirmed'], z['confirmed']), indices=node['indices'] + x2['indices'][1:] + z['indices'][1:], subdivision_verified=node['subdivision_verified'] and x2['subdivision_verified'] and z['subdivision_verified'], children=node['children'] + [{k: r[k] for k in ['family', 'start', 'end', 'subdivision_verified']} for r in [x2, z]])
                        combos.append(trip)
    return records + combos
