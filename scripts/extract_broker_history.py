#!/usr/bin/env python3
"""Accumulate weekly per-broker net positions (futures + options) into a
persistent history, so the "大口動向" card can show multi-week trends.

Reads whatever weekly files are present in the data dir this run
(YYYYMMDD_indexfut_oi_by_tp.xlsx and YYYYMMDD_nk225op_oi_by_tp.xlsx),
computes each broker's net, and merges into broker_history.json keyed by the
weekly as-of date. Idempotent: re-running a week overwrites that week only.

Futures net comes from extract_weekly_trend's section parser (n225 large).
Option net (put/call, buy +, sell -) comes from extract_opt_weekly.
"""
import argparse
import glob
import json
import os
import re


def _norm(n):
    s = str(n or '')
    for j in ['證券', '証券', 'クリアリン', '（', '）', ' ', '　']:
        s = s.replace(j, '')
    return s.replace('ＭＵＦＪ', 'ＭＵＦＧ')


def _load(path):
    if os.path.exists(path):
        try:
            return json.load(open(path, encoding='utf-8'))
        except Exception:
            return {}
    return {}


def _futures_nets(path):
    """broker -> n225 large net for one weekly indexfut file."""
    import openpyxl
    import extract_weekly_trend as wt
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    bounds = wt.find_sections(ws)          # {section_key: (start, end)}
    # prefer the n225 large section
    key = None
    for k in bounds:
        kl = str(k).lower()
        if 'large' in kl or 'ラージ' in str(k) or 'n225_large' in kl:
            key = k
            break
    if key is None and bounds:
        key = list(bounds.keys())[0]
    out = {}
    if key:
        start, end = bounds[key]
        for b, v in wt.extract_section_nets(ws, start, end).items():
            out[_norm(b)] = round(v or 0)
    return out


def _option_nets(path):
    """broker -> {'put':net,'call':net,'cat':cat} for one weekly nk225op file."""
    import extract_opt_weekly as ow
    part = ow.parse_opt_weekly(path).get('participants', {})
    out = {}
    for b, v in part.items():
        out[_norm(b)] = {'put': round(v.get('put', 0)),
                         'call': round(v.get('call', 0)),
                         'cat': v.get('cat', '')}
    return out


def build_broker_history(data_dir, out_path):
    hist = _load(out_path)              # { date: { broker: {...} } }

    fut_files = glob.glob(os.path.join(data_dir, '*indexfut_oi_by_tp*.xlsx'))
    opt_files = glob.glob(os.path.join(data_dir, '*nk225op_oi_by_tp*.xlsx'))
    dates = set()
    fut_by_date, opt_by_date = {}, {}
    for f in fut_files:
        m = re.search(r'(\d{8})', os.path.basename(f))
        if m:
            fut_by_date[m.group(1)] = f
            dates.add(m.group(1))
    for f in opt_files:
        m = re.search(r'(\d{8})', os.path.basename(f))
        if m:
            opt_by_date[m.group(1)] = f
            dates.add(m.group(1))

    for d in sorted(dates):
        wk = hist.get(d, {})
        if d in fut_by_date:
            try:
                for b, net in _futures_nets(fut_by_date[d]).items():
                    wk.setdefault(b, {})['fut'] = net
            except Exception as e:
                print('[broker_history] futures parse failed %s: %s' % (d, e))
        if d in opt_by_date:
            try:
                for b, o in _option_nets(opt_by_date[d]).items():
                    e = wk.setdefault(b, {})
                    e['put'] = o['put']
                    e['call'] = o['call']
                    if o['cat']:
                        e['cat'] = o['cat']
            except Exception as e:
                print('[broker_history] option parse failed %s: %s' % (d, e))
        if wk:
            hist[d] = wk

    # keep last 16 weeks to bound size
    if len(hist) > 16:
        for d in sorted(hist.keys())[:-16]:
            del hist[d]

    json.dump(hist, open(out_path, 'w', encoding='utf-8'),
              ensure_ascii=False, separators=(',', ':'))
    print('[broker_history] %d weeks -> %s (%s)'
          % (len(hist), out_path, ','.join(sorted(hist.keys()))))
    return hist


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', default='data')
    ap.add_argument('--out', default='data/broker_history.json')
    a = ap.parse_args()
    build_broker_history(a.data_dir, a.out)
