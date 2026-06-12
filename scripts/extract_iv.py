#!/usr/bin/env python3
"""Extract per-strike implied volatility from the OSE theoretical-price file
(oseYYYYMMDDtp.csv). Produces iv.json with, per expiry: the underlying close,
the OSE base (reference) volatility, and a list of strikes carrying both the
put IV and the call IV. Also builds an OTM smile (put IV below spot, call IV
above spot), an interpolated ATM IV, and a simple skew metric.

CSV layout (comma-separated, fixed-width-ish, multiple underlyings):
  [0] underlying name (filter == 'NK225E')   [1] type ('OOP' = options)
  [2] expiry YYYYMM (or YYYYMMDD for weeklies)
  [3] strike (e.g. 000000066000.000000)
  [5] put code   [6] put premium close   [8] put theoretical   [9] put IV
  [10] call code [11] call premium close [13] call theoretical [14] call IV
  [15] underlying close                  [16] base (reference) volatility
IV values are decimals (0.3404 = 34.04%).
"""
import csv
import glob
import json
import os
import argparse


def _f(v):
    try:
        return float(str(v).strip())
    except Exception:
        return None


def parse_tp_csv(path):
    by_expiry = {}
    with open(path, encoding='utf-8') as fh:
        for row in csv.reader(fh):
            if len(row) < 17:
                continue
            if row[0].strip() != 'NK225E' or row[1].strip() != 'OOP':
                continue
            expiry = row[2].strip()
            strike = _f(row[3])
            if strike is None:
                continue
            strike = int(round(strike))
            put_iv = _f(row[9])
            call_iv = _f(row[14])
            put_prem = _f(row[6])
            call_prem = _f(row[11])
            under = _f(row[15])
            base_vol = _f(row[16])
            e = by_expiry.setdefault(expiry, {
                'expiry': expiry, 'underlying': under, 'base_vol': base_vol,
                'strikes': {}})
            if under:
                e['underlying'] = under
            if base_vol:
                e['base_vol'] = base_vol
            e['strikes'][strike] = {
                'strike': strike,
                'put_iv': put_iv, 'call_iv': call_iv,
                'put_premium': put_prem, 'call_premium': call_prem,
            }
    return by_expiry


def _interp_atm_iv(smile, spot):
    """Linear-interpolate the OTM IV curve at the spot to get ATM IV."""
    pts = [(s, iv) for s, iv in smile if iv is not None and iv > 0]
    if not pts or not spot:
        return None
    pts.sort()
    if spot <= pts[0][0]:
        return pts[0][1]
    if spot >= pts[-1][0]:
        return pts[-1][1]
    for i in range(1, len(pts)):
        if pts[i][0] >= spot:
            x0, y0 = pts[i - 1]
            x1, y1 = pts[i]
            if x1 == x0:
                return y1
            return y0 + (y1 - y0) * (spot - x0) / (x1 - x0)
    return pts[-1][1]


def build(by_expiry, min_strikes=8):
    out_expiries = []
    for expiry, e in by_expiry.items():
        spot = e.get('underlying')
        strikes = sorted(e['strikes'].values(), key=lambda x: x['strike'])
        if len(strikes) < min_strikes:
            continue
        # OTM smile: put IV below spot, call IV above spot
        smile = []
        for s in strikes:
            k = s['strike']
            if spot and k < spot:
                iv = s['put_iv']
            elif spot and k > spot:
                iv = s['call_iv']
            else:  # at the money: average the two sides if available
                ivs = [x for x in (s['put_iv'], s['call_iv']) if x]
                iv = sum(ivs) / len(ivs) if ivs else None
            smile.append({'strike': k, 'iv': iv,
                          'put_iv': s['put_iv'], 'call_iv': s['call_iv']})
        smile_pts = [(p['strike'], p['iv']) for p in smile]
        atm_iv = _interp_atm_iv(smile_pts, spot) or e.get('base_vol')
        # Simple skew: OTM put IV (~10% below) minus OTM call IV (~10% above)
        skew = None
        if spot and atm_iv:
            def iv_at(target):
                best = None
                bestd = 1e18
                for p in smile:
                    if p['iv'] and p['iv'] > 0:
                        d = abs(p['strike'] - target)
                        if d < bestd:
                            bestd = d
                            best = p['iv']
                return best
            lo = iv_at(spot * 0.90)
            hi = iv_at(spot * 1.10)
            if lo and hi:
                skew = round((lo - hi) * 100, 2)  # in vol points
        out_expiries.append({
            'expiry': expiry,
            'underlying': spot,
            'base_vol': e.get('base_vol'),
            'atm_iv': round(atm_iv, 4) if atm_iv else None,
            'skew_10pct': skew,
            'smile': smile,
        })
    # Sort by expiry (monthly YYYYMM first in chrono order; weeklies YYYYMMDD too)
    out_expiries.sort(key=lambda x: x['expiry'])
    return out_expiries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', default='data')
    ap.add_argument('--out', default='data/iv.json')
    ap.add_argument('--file', default=None, help='explicit tp.csv path')
    args = ap.parse_args()

    path = args.file
    if not path:
        cands = sorted(glob.glob(os.path.join(args.data_dir, 'ose*tp.csv')))
        if not cands:
            print('[extract_iv.py] no ose*tp.csv found in %s' % args.data_dir)
            json.dump({'error': 'no tp.csv'}, open(args.out, 'w'))
            return
        path = cands[-1]
    print('[extract_iv.py] parsing %s' % path)
    by_expiry = parse_tp_csv(path)
    expiries = build(by_expiry)
    result = {'source': os.path.basename(path), 'expiries': expiries}
    with open(args.out, 'w', encoding='utf-8') as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    print('[extract_iv.py] wrote %s (%d expiries)' % (args.out, len(expiries)))


if __name__ == '__main__':
    main()
