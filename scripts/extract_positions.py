#!/usr/bin/env python3
"""Merge weekly futures positioning (weekly_trend.json) with weekly option
positioning (opt_weekly.json) into a single per-participant view, so each big
player's full stance (futures direction + option put/call) is in one place.

Output: positions.json
"""
import argparse
import json
import os


def _norm(name):
    """Normalise a broker name for matching across the two files."""
    s = str(name or '')
    for junk in ['證券', '証券', 'クリアリン', '（', '）', ' ', '　']:
        s = s.replace(junk, '')
    # unify a few common variants
    s = s.replace('ＭＵＦＪ', 'ＭＵＦＧ')
    return s


def build(data_dir):
    wt_path = os.path.join(data_dir, 'weekly_trend.json')
    ow_path = os.path.join(data_dir, 'opt_weekly.json')
    if not os.path.exists(wt_path) and not os.path.exists(ow_path):
        return None
    fut = {}      # norm -> {'broker','cat','fut'}
    fut_lim = ''
    if os.path.exists(wt_path):
        wt = json.load(open(wt_path, encoding='utf-8'))
        fut_lim = (wt.get('limgetsu') or {}).get('n225_large', '')
        for r in wt.get('sections', {}).get('n225_large', []):
            n = _norm(r.get('broker'))
            fut[n] = {'broker': r.get('broker'), 'cat': r.get('category', ''),
                      'fut': r.get('oi_current') or 0}
    opt = {}      # norm -> {'put','call','cat'}
    opt_as_of = ''
    if os.path.exists(ow_path):
        ow = json.load(open(ow_path, encoding='utf-8'))
        opt_as_of = ow.get('as_of', '')
        for b, d in (ow.get('participants') or {}).items():
            opt[_norm(b)] = {'broker': b, 'put': d.get('put', 0),
                             'call': d.get('call', 0), 'cat': d.get('cat', '')}

    keys = set(fut) | set(opt)
    rows = []
    for k in keys:
        f = fut.get(k, {})
        o = opt.get(k, {})
        broker = f.get('broker') or o.get('broker') or k
        rows.append({
            'broker': broker,
            'cat': f.get('cat') or o.get('cat') or '',
            'fut': round(f.get('fut', 0)),
            'put': round(o.get('put', 0)),
            'call': round(o.get('call', 0)),
        })
    # footprint = |futures| + 20*(|put|+|call|)  (options are smaller-scale)
    rows.sort(key=lambda r: -(abs(r['fut']) + 20 * (abs(r['put']) + abs(r['call']))))
    return {'fut_limgetsu': fut_lim, 'opt_as_of': opt_as_of, 'rows': rows[:14]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', default='data')
    ap.add_argument('--out', default='data/positions.json')
    a = ap.parse_args()
    out = build(a.data_dir)
    if not out:
        print('[positions] no weekly files found')
        return
    json.dump(out, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('[positions] wrote %s | %d participants (先物%s / OP%s)'
          % (a.out, len(out['rows']), out['fut_limgetsu'], out['opt_as_of']))
    for r in out['rows'][:6]:
        print('  %-14s 先物%+d P%+d C%+d' % (r['broker'].replace('証券', ''), r['fut'], r['put'], r['call']))


if __name__ == '__main__':
    main()
