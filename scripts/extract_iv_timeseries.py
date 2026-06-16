#!/usr/bin/env python3
"""Accumulate a daily IV / skew time-series for the IV推移 card.

Mirrors extract_oi_timeseries.py: the history is persisted inside the output
JSON under '_snapshots' (keyed by date), so it survives even after the daily
ose<date>tp.csv files are deleted from data/. Each run:
  1. loads prior snapshots from the existing iv_timeseries.json,
  2. computes a snapshot for every ose*tp.csv currently in data/ (upsert),
  3. rebuilds the display arrays (dates + per-expiry ATM IV + front skew).

Per-date snapshot: {expiries: {YYYYMM: {atm_iv, skew_10pct}}, front: YYYYMM}.
ATM IV / skew are stored as percentages / points (e.g. 31.8, +9.7).
"""
import argparse
import glob
import json
import os
import re

import extract_iv  # reuse parse_tp_csv() + build()

DATE_RE = re.compile(r'ose(\d{8})tp\.csv$')


def snapshot_from_tp(path):
    """Return {'expiries': {YYYYMM: {atm_iv, skew_10pct}}, 'front': YYYYMM} or None."""
    try:
        expiries = extract_iv.build(extract_iv.parse_tp_csv(path))
    except Exception as e:
        print('[iv_timeseries] parse error %s: %s' % (path, e))
        return None
    monthly = [e for e in expiries if len(e.get('expiry', '')) == 6]
    if not monthly:
        return None
    exp_map = {}
    for e in monthly:
        atm = e.get('atm_iv')
        sk = e.get('skew_10pct')
        exp_map[e['expiry']] = {
            'atm_iv': round(atm * 100, 2) if atm is not None else None,
            'skew_10pct': round(sk, 2) if sk is not None else None,
        }
    return {'expiries': exp_map, 'front': monthly[0]['expiry']}


def build_timeseries(data_dir='data', out_path='data/iv_timeseries.json', max_days=20):
    # 1. prior snapshots
    snaps = {}
    if os.path.exists(out_path):
        try:
            with open(out_path, encoding='utf-8') as f:
                prev = json.load(f)
            snaps = prev.get('_snapshots', {}) or {}
            print('[iv_timeseries] loaded %d prior snapshots' % len(snaps))
        except Exception as e:
            print('[iv_timeseries] could not read prior %s: %s' % (out_path, e))

    # 2. upsert snapshots from any ose*tp.csv present
    new_dates = []
    for fp in sorted(glob.glob(os.path.join(data_dir, 'ose*tp.csv'))):
        m = DATE_RE.search(os.path.basename(fp))
        if not m:
            continue
        date_str = m.group(1)
        snap = snapshot_from_tp(fp)
        if snap:
            snaps[date_str] = snap
            new_dates.append(date_str)
    if new_dates:
        print('[iv_timeseries] upserted %d snapshot(s): %s' % (len(new_dates), ', '.join(new_dates)))

    if not snaps:
        result = {'error': 'No snapshots: neither prior history nor ose*tp.csv in %s' % data_dir}
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return result

    # 3. rebuild display arrays (keep most recent max_days)
    dates = sorted(snaps.keys())[-max_days:]
    # choose the expiries to chart: the 3 nearest monthlies of the LATEST date
    latest = snaps[dates[-1]]
    front_order = sorted(latest['expiries'].keys())
    chart_expiries = front_order[:3]

    atm_iv = {}
    skew = {}
    for exp in chart_expiries:
        atm_iv[exp] = [snaps[d]['expiries'].get(exp, {}).get('atm_iv') for d in dates]
    # front-month skew over time (front per its own date, falls back to latest front)
    front_exp = latest['front']
    skew[front_exp] = [snaps[d]['expiries'].get(front_exp, {}).get('skew_10pct') for d in dates]

    result = {
        'dates': dates,
        'n_dates': len(dates),
        'chart_expiries': chart_expiries,
        'front': front_exp,
        'atm_iv': atm_iv,
        'skew': skew,
        '_snapshots': snaps,
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print('[iv_timeseries] wrote %s | %d dates | expiries %s'
          % (out_path, len(dates), chart_expiries))
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', default='data')
    ap.add_argument('--out', default='data/iv_timeseries.json')
    ap.add_argument('--max-days', type=int, default=20)
    args = ap.parse_args()
    build_timeseries(args.data_dir, args.out, args.max_days)


if __name__ == '__main__':
    main()
