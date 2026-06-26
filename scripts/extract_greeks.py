#!/usr/bin/env python3
"""
extract_greeks.py — Per-strike Black-Scholes greeks + OI-weighted Gamma
Exposure (GEX) for the JPX Nikkei 225 options board.

Inputs (from --data-dir):
  ose{YYYYMMDD}tp.csv          today's OSE theoretical-price file (IV + spot)
  {YYYYMMDD}open_interest.xlsx today's OI (sheet '別紙1')
  (optional) prior-day tp.csv + open_interest for the OI x IV sign (Convention B)

Output: greeks.json with, per expiry:
  - per_strike greeks (delta/gamma/vega/theta) at each strike's own IV
  - gex_A : GEX under the STANDARD dealer convention
            (dealers long calls / short puts)
  - gex_B : GEX under the OI x IV-INFERRED convention
            (per strike/side: OI up + IV up = customer BUY -> dealer SHORT;
             OI up + IV down/flat = customer SELL -> dealer LONG;
             ambiguous -> fall back to the standard sign, so B == A when
             no directional flow is detectable)
  - zero_gamma_A / zero_gamma_B : dealer gamma flip level, found by
            re-evaluating total dealer GEX across a spot grid
  - net_A / net_B : net dealer gamma / delta / vega / theta
  - top_gamma     : strikes with the largest |gamma x OI| (pin candidates)

Greeks use r = 0 (JPY approx), dividends folded into spot for short tenors.
Absolute yen GEX depends on the contract multiplier (default 1000 = large
N225 options); the PROFILE / sign / flip level are robust, exact yen is a
reference figure. Reuses parse_tp_csv()+build() from extract_iv.py.
"""
import argparse
import json
import math
import os
import re
from datetime import date

from extract_iv import parse_tp_csv, build

MULT = 1000          # N225 option multiplier (large). Mini = 100.
OI_EPS = 50          # min net OI change to call a directional flow
IV_EPS = 0.002       # min IV change (decimal, = 0.2 vol pts) for a flow read


# ----------------------------------------------------------------------------
# Black-Scholes greeks (r = 0)
# ----------------------------------------------------------------------------
def _np(x):
    return math.exp(-x * x / 2.0) / math.sqrt(2.0 * math.pi)


def _nc(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def greeks(S, K, T, sig, cp):
    """Return dict of delta/gamma/vega(per 1 vol pt)/theta(per day)."""
    if not (S > 0 and K > 0 and T > 0 and sig and sig > 0):
        return {'delta': 0.0, 'gamma': 0.0, 'vega': 0.0, 'theta': 0.0}
    srt = sig * math.sqrt(T)
    d1 = (math.log(S / K) + 0.5 * sig * sig * T) / srt
    delta = _nc(d1) if cp == 'C' else _nc(d1) - 1.0
    gamma = _np(d1) / (S * srt)
    vega = S * _np(d1) * math.sqrt(T) / 100.0
    theta = (-S * _np(d1) * sig / (2.0 * math.sqrt(T))) / 365.0
    return {'delta': delta, 'gamma': gamma, 'vega': vega, 'theta': theta}


def _gamma_at(S, K, T, sig):
    if not (S > 0 and K > 0 and T > 0 and sig and sig > 0):
        return 0.0
    srt = sig * math.sqrt(T)
    d1 = (math.log(S / K) + 0.5 * sig * sig * T) / srt
    return _np(d1) / (S * srt)


# ----------------------------------------------------------------------------
# Expiry / time helpers
# ----------------------------------------------------------------------------
def _sq_date(expiry_code):
    """expiry_code like '202607' -> 2nd-Friday SQ date."""
    y = int(expiry_code[:4]); m = int(expiry_code[4:6])
    d = date(y, m, 1)
    # weekday(): Mon=0..Sun=6 ; Friday=4
    first_fri = 1 + ((4 - d.weekday()) % 7)
    return date(y, m, first_fri + 7)


def _today_from_dir(data_dir):
    best = None
    for fn in os.listdir(data_dir):
        mo = re.search(r'(\d{8})', fn)
        if mo:
            d = mo.group(1)
            if best is None or d > best:
                best = d
    return best


# ----------------------------------------------------------------------------
# OI parsing (sheet 別紙1) -> {expiry: {strike: {'call_oi','put_oi'}}}
# ----------------------------------------------------------------------------
def parse_oi(path):
    from openpyxl import load_workbook
    out = {}
    try:
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb['別紙1']
    except Exception:
        return out
    pat_p = re.compile(r'NIKKEI\s*225\s*P\s*(\d{4})-(\d+)')
    pat_c = re.compile(r'NIKKEI\s*225\s*C\s*(\d{4})-(\d+)')

    def _num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0
    for row in ws.iter_rows(values_only=True):
        a = str(row[0]).strip() if row and row[0] else ''
        g = str(row[6]).strip() if len(row) > 6 and row[6] else ''
        mp = pat_p.match(a)
        if mp and int(mp.group(2)) % 500 == 0:
            e = mp.group(1); k = int(mp.group(2))
            out.setdefault(e, {}).setdefault(k, {'call_oi': 0.0, 'put_oi': 0.0})
            out[e][k]['put_oi'] += _num(row[2] if len(row) > 2 else 0)
        mc = pat_c.match(g)
        if mc and int(mc.group(2)) % 500 == 0:
            e = mc.group(1); k = int(mc.group(2))
            out.setdefault(e, {}).setdefault(k, {'call_oi': 0.0, 'put_oi': 0.0})
            out[e][k]['call_oi'] += _num(row[8] if len(row) > 8 else 0)
    return out


def _find(data_dir, pattern, exclude=None):
    hits = []
    for fn in os.listdir(data_dir):
        if re.search(pattern, fn) and (not exclude or exclude not in fn):
            mo = re.search(r'(\d{8})', fn)
            if mo:
                hits.append((mo.group(1), os.path.join(data_dir, fn)))
    return sorted(hits)


# ----------------------------------------------------------------------------
# Convention B: dealer sign per strike/side from OI x IV flow
# ----------------------------------------------------------------------------
def _dealer_sign(oi_chg, iv_chg, side):
    """Return dealer position sign (+1 long / -1 short) for this option.
    Fallback (ambiguous) = standard convention: long call (+1), short put (-1).
    """
    fallback = +1 if side == 'C' else -1
    if oi_chg is None or iv_chg is None or oi_chg <= OI_EPS:
        return fallback, 'fallback'
    if iv_chg >= IV_EPS:          # customer BUYING -> dealer SHORT
        return -1, 'buy'
    if iv_chg <= -IV_EPS:         # customer SELLING -> dealer LONG
        return +1, 'sell'
    return fallback, 'fallback'   # OI up but IV flat -> ambiguous


# ----------------------------------------------------------------------------
# Core build
# ----------------------------------------------------------------------------
def build_greeks(data_dir, max_expiries=3):
    today = _today_from_dir(data_dir)
    tps = _find(data_dir, r'ose\d{8}tp\.csv')
    ois = _find(data_dir, r'\d{8}open_interest\.xlsx')
    if not tps or not ois:
        return {'error': 'need today ose tp.csv and open_interest.xlsx',
                'have_tp': [d for d, _ in tps], 'have_oi': [d for d, _ in ois]}

    tp_today = tps[-1][1]
    oi_today = ois[-1][1]
    tp_prior = tps[-2][1] if len(tps) >= 2 else None
    oi_prior = ois[-2][1] if len(ois) >= 2 else None

    iv_expiries = build(parse_tp_csv(tp_today))
    spot = None
    for e in iv_expiries:
        if e.get('underlying'):
            spot = e['underlying']; break
    oi_now = parse_oi(oi_today)
    oi_was = parse_oi(oi_prior) if oi_prior else {}

    iv_prior_map = {}
    if tp_prior:
        for e in build(parse_tp_csv(tp_prior)):
            iv_prior_map[e['expiry']] = {int(p['strike']): p['iv']
                                         for p in e['smile'] if p.get('iv')}

    out = {'as_of': today, 'spot': spot, 'r': 0.0, 'mult': MULT,
           'conventions': {
               'A': 'standard: dealer long calls / short puts',
               'B': 'OI x IV inferred sign (fallback to A when ambiguous)'},
           'expiries': []}

    liquid = [e for e in iv_expiries if len(e['expiry']) == 6][:max_expiries]
    for e in liquid:
        ecode = e['expiry']
        sq = _sq_date(ecode)
        T_days = max((sq - date(int(today[:4]), int(today[4:6]), int(today[6:8]))).days, 0)
        T = max(T_days, 0.5) / 365.0
        smile = {int(p['strike']): p['iv'] for p in e['smile'] if p.get('iv')}
        oi_e = oi_now.get(ecode, {})
        oi_e_was = oi_was.get(ecode, {})
        iv_was_e = iv_prior_map.get(ecode, {})

        per = []
        net_A = {'gamma': 0.0, 'delta': 0.0, 'vega': 0.0, 'theta': 0.0}
        net_B = {'gamma': 0.0, 'delta': 0.0, 'vega': 0.0, 'theta': 0.0}
        gex_A = []; gex_B = []
        sign_meta = []
        # union of strikes that have either IV or OI
        strikes = sorted(set(smile) | set(oi_e))
        for K in strikes:
            sig = smile.get(K) or (smile[min(smile, key=lambda x: abs(x - K))]
                                   if smile else None)
            if not sig:
                continue
            coi = (oi_e.get(K, {}) or {}).get('call_oi', 0.0)
            poi = (oi_e.get(K, {}) or {}).get('put_oi', 0.0)
            coi_w = (oi_e_was.get(K, {}) or {}).get('call_oi', 0.0)
            poi_w = (oi_e_was.get(K, {}) or {}).get('put_oi', 0.0)
            coi_chg = coi - coi_w if oi_e_was else None
            poi_chg = poi - poi_w if oi_e_was else None
            iv_chg = (sig - iv_was_e[K]) if (K in iv_was_e) else None

            gc = greeks(spot, K, T, sig, 'C')
            gp = greeks(spot, K, T, sig, 'P')
            g = gc['gamma']  # same magnitude for C/P at K

            # dollar-gamma per 1% move
            unit = g * MULT * spot * spot * 0.01
            # Convention A
            a = (coi - poi) * unit
            # Convention B
            sc, rc = _dealer_sign(coi_chg, iv_chg, 'C')
            sp_, rp = _dealer_sign(poi_chg, iv_chg, 'P')
            b = (sc * coi + sp_ * poi) * unit

            gex_A.append({'strike': K, 'gex': a / 1e8})   # 億円/1%
            gex_B.append({'strike': K, 'gex': b / 1e8})
            sign_meta.append({'strike': K, 'call': rc, 'put': rp})

            net_A['gamma'] += (coi - poi) * g
            net_B['gamma'] += (sc * coi + sp_ * poi) * g
            for kk, src in (('delta', None),):
                pass
            net_A['delta'] += coi * gc['delta'] + poi * gp['delta']
            net_B['delta'] += (sc * coi) * gc['delta'] + (sp_ * poi) * gp['delta']
            for kk in ('vega', 'theta'):
                net_A[kk] += (coi + poi) * gc[kk]
                net_B[kk] += (abs(sc) * coi + abs(sp_) * poi) * gc[kk]

            per.append({
                'strike': K, 'iv': round(sig, 5),
                'call_oi': int(coi), 'put_oi': int(poi),
                'call_oi_chg': (int(coi_chg) if coi_chg is not None else None),
                'put_oi_chg': (int(poi_chg) if poi_chg is not None else None),
                'iv_chg': (round(iv_chg, 5) if iv_chg is not None else None),
                'call': {k: round(v, 6) for k, v in gc.items()},
                'put': {k: round(v, 6) for k, v in gp.items()},
            })

        zga = _zero_gamma(spot, T, smile, oi_e, oi_e_was, iv_was_e, 'A')
        zgb = _zero_gamma(spot, T, smile, oi_e, oi_e_was, iv_was_e, 'B')
        top_gamma = sorted(
            [{'strike': p['strike'],
              'gamma_oi': round(p['call']['gamma'] * p['call_oi']
                                + p['put']['gamma'] * p['put_oi'], 4),
              'call_oi': p['call_oi'], 'put_oi': p['put_oi']} for p in per],
            key=lambda r: -r['gamma_oi'])[:6]

        out['expiries'].append({
            'expiry': ecode, 'label': '%d月限' % int(ecode[4:6]),
            'T_days': T_days, 'T': round(T, 5), 'spot': spot,
            'per_strike': per,
            'gex_A': gex_A, 'gex_B': gex_B,
            'zero_gamma_A': zga, 'zero_gamma_B': zgb,
            'net_A': {k: round(v, 4) for k, v in net_A.items()},
            'net_B': {k: round(v, 4) for k, v in net_B.items()},
            'top_gamma': top_gamma,
            'sign_meta': sign_meta,
            'has_oi_change': bool(oi_e_was),
            'has_iv_change': bool(iv_was_e),
        })
    return out


def _zero_gamma(spot, T, smile, oi_e, oi_e_was, iv_was_e, conv):
    """Find dealer gamma flip level by re-evaluating total GEX on a spot grid."""
    if not smile or not oi_e:
        return None
    lo, hi = spot * 0.90, spot * 1.10
    n = 81
    grid = [lo + (hi - lo) * i / (n - 1) for i in range(n)]

    def total_gex(Sx):
        tot = 0.0
        for K, sig in smile.items():
            coi = (oi_e.get(K, {}) or {}).get('call_oi', 0.0)
            poi = (oi_e.get(K, {}) or {}).get('put_oi', 0.0)
            g = _gamma_at(Sx, K, T, sig)
            if conv == 'A':
                tot += (coi - poi) * g
            else:
                coi_w = (oi_e_was.get(K, {}) or {}).get('call_oi', 0.0)
                poi_w = (oi_e_was.get(K, {}) or {}).get('put_oi', 0.0)
                ivc = (sig - iv_was_e[K]) if (K in iv_was_e) else None
                sc, _ = _dealer_sign(coi - coi_w if oi_e_was else None, ivc, 'C')
                sp_, _ = _dealer_sign(poi - poi_w if oi_e_was else None, ivc, 'P')
                tot += (sc * coi + sp_ * poi) * g
        return tot

    prev_S, prev_v = grid[0], total_gex(grid[0])
    crossings = []
    for Sx in grid[1:]:
        v = total_gex(Sx)
        if prev_v == 0 or (prev_v < 0) != (v < 0):
            if v != prev_v:
                cross = prev_S + (Sx - prev_S) * (0 - prev_v) / (v - prev_v)
            else:
                cross = Sx
            crossings.append(round(cross))
        prev_S, prev_v = Sx, v
    return {'flip': crossings[0] if crossings else None,
            'all_flips': crossings,
            'sign_at_spot': ('positive' if total_gex(spot) >= 0 else 'negative')}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', default='data')
    ap.add_argument('--out', default='data/greeks.json')
    ap.add_argument('--max-expiries', type=int, default=3)
    a = ap.parse_args()
    res = build_greeks(a.data_dir, a.max_expiries)
    with open(a.out, 'w') as f:
        json.dump(res, f, ensure_ascii=False, separators=(',', ':'))
    if res.get('error'):
        print('[extract_greeks] ERROR:', res['error'], res)
    else:
        print('[extract_greeks] wrote %s | spot=%.0f | %d expiries'
              % (a.out, res['spot'] or 0, len(res['expiries'])))
        for e in res['expiries']:
            za = (e['zero_gamma_A'] or {}).get('flip')
            zb = (e['zero_gamma_B'] or {}).get('flip')
            print('  %s T=%dd  zeroGamma A=%s B=%s  netGammaA=%.1f netGammaB=%.1f'
                  % (e['label'], e['T_days'], za, zb,
                     e['net_A']['gamma'], e['net_B']['gamma']))


if __name__ == '__main__':
    main()
