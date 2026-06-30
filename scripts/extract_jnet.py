#!/usr/bin/env python3
"""
extract_jnet.py — per-broker J-NET (off-auction / cross) futures volume.

Parses `<date>_volume_by_participant_whole_day_J-NET.xlsx` and aggregates the
day-session J-NET volume by broker and product class (large / mini futures,
topix, options). Accumulates a daily history in `jnet_history.json` so broker
cross activity (e.g. UBS) can be tracked over time and eyeballed against price.

IMPORTANT: J-NET data has NO buy/sell split. This is VOLUME only, not
direction. Use it as a hypothesis ("did a broker's cross spike coincide with a
price stall?") to confirm against subsequent price action — never as a direct
buy/sell signal.
"""
import argparse
import glob
import json
import os
import re

import openpyxl

PRODUCTS = {'NK225F': 'large', 'NK225MF': 'mini',
            'TOPIXF': 'topix', 'NK225E': 'option'}


def _digits(s):
    return re.sub(r'\D', '', str(s or ''))


def parse_jnet(path):
    """Return (date_str, {broker: {large,mini,topix,option}})."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb['手口上位一覧'] if '手口上位一覧' in wb.sheetnames else wb.worksheets[0]
    date = None
    brokers = {}
    for r in ws.iter_rows(values_only=True):
        if not r:
            continue
        # trading date line
        if len(r) > 2 and r[1] and '取引日' in str(r[1]) and r[2]:
            d = _digits(r[2])
            if len(d) >= 8:
                date = d[:8]
        pc = str(r[0]).strip() if r[0] else ''
        if pc in PRODUCTS:
            broker = str(r[5]).strip() if len(r) > 5 and r[5] else None
            vol = r[7] if len(r) > 7 and isinstance(r[7], (int, float)) else None
            if broker and vol is not None:
                d = brokers.setdefault(broker, {'large': 0.0, 'mini': 0.0,
                                                'topix': 0.0, 'option': 0.0})
                d[PRODUCTS[pc]] += float(vol)
    if not date:
        m = re.search(r'(\d{8})', os.path.basename(path))
        date = m.group(1) if m else None
    return date, brokers


def _load(path):
    try:
        with open(path, encoding='utf-8') as f:
            h = json.load(f)
        return h if isinstance(h, dict) else {}
    except Exception:
        return {}


def _save(path, history, keep=40):
    for d in sorted(history.keys())[:-keep]:
        history.pop(d, None)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, separators=(',', ':'))


def _spot_from_dir(data_dir):
    """Best-effort: read spot from greeks.json or data.json in the dir."""
    for name in ('greeks.json', 'data.json'):
        p = os.path.join(data_dir, name)
        try:
            d = json.load(open(p, encoding='utf-8'))
            if d.get('spot'):
                return d['spot']
            sp = (d.get('meta') or d.get('metadata') or {}).get('nikkei')
            if sp:
                return sp
        except Exception:
            pass
    return None


def build_jnet(data_dir, spot=None):
    files = sorted(glob.glob(os.path.join(
        data_dir, '*volume_by_participant_whole_day_J-NET*.xlsx')))
    if not files:
        return {'error': 'no J-NET file found'}
    date, brokers = parse_jnet(files[-1])
    if spot is None:
        spot = _spot_from_dir(data_dir)

    rows = []
    for b, d in brokers.items():
        fut = d['large'] + d['mini']
        rows.append({'broker': b, 'large': d['large'], 'mini': d['mini'],
                     'topix': d['topix'], 'option': d['option'], 'fut': fut})
    rows.sort(key=lambda x: -x['fut'])

    out = {'date': date, 'spot': spot, 'brokers': rows}

    # accumulate history (compact: broker -> fut/large/mini/option)
    hist_path = os.path.join(data_dir, 'jnet_history.json')
    history = _load(hist_path)
    history[date] = {
        'spot': spot,
        'brokers': {r['broker']: {'fut': r['fut'], 'large': r['large'],
                                  'mini': r['mini'], 'opt': r['option']}
                    for r in rows},
    }
    _save(hist_path, history)
    out['history_dates'] = sorted(history.keys())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', default='data')
    ap.add_argument('--out', default='data/jnet.json')
    ap.add_argument('--spot', type=float, default=None)
    a = ap.parse_args()
    res = build_jnet(a.data_dir, spot=a.spot)
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    if res.get('error'):
        print('[extract_jnet] %s' % res['error'])
        return
    ubs = next((r for r in res['brokers']
                if 'ＵＢＳ' in r['broker'] or 'UBS' in r['broker']), None)
    print('[extract_jnet] wrote %s | date=%s | %d brokers | spot=%s'
          % (a.out, res['date'], len(res['brokers']), res['spot']))
    if ubs:
        print('[extract_jnet]   UBS futures J-NET: large=%.0f mini=%.0f total=%.0f'
              % (ubs['large'], ubs['mini'], ubs['fut']))
    print('[extract_jnet]   history dates: %s' % res['history_dates'])


if __name__ == '__main__':
    main()
