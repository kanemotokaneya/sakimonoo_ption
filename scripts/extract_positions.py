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

    # today's J-NET flow (futures volume + option cross involvement)
    day_fut = {}   # norm -> futures volume today
    day_opt = {}   # norm -> {'lots': total option-cross lots, 'top': 'P66000×2194'}
    day_date = ''
    jn_path = os.path.join(data_dir, 'jnet.json')
    if os.path.exists(jn_path):
        jn = json.load(open(jn_path, encoding='utf-8'))
        day_date = jn.get('date', '')
        for r in jn.get('brokers', []):
            day_fut[_norm(r.get('broker'))] = r.get('large', 0) or 0
        for c in jn.get('option_crosses', []):
            side, strike, sz = c.get('side'), c.get('strike'), c.get('size', 0)
            for leg in c.get('legs', []):
                n = _norm(leg.get('broker'))
                e = day_opt.setdefault(n, {'lots': 0, 'top': '', 'top_v': 0})
                e['lots'] += leg.get('vol', 0) or 0
                if (leg.get('vol', 0) or 0) > e['top_v']:
                    e['top_v'] = leg.get('vol', 0) or 0
                    e['top'] = '%s%s×%d' % (side, format(int(strike), ','), int(leg.get('vol', 0)))

    keys = set(fut) | set(opt) | set(day_opt)
    # include big daily-futures players too
    for k, v in day_fut.items():
        if abs(v) >= 1000:
            keys.add(k)
    rows = []
    for k in keys:
        f = fut.get(k, {})
        o = opt.get(k, {})
        do = day_opt.get(k, {})
        broker = f.get('broker') or o.get('broker') or k
        rows.append({
            'broker': broker,
            'cat': f.get('cat') or o.get('cat') or '',
            'fut': round(f.get('fut', 0)),
            'put': round(o.get('put', 0)),
            'call': round(o.get('call', 0)),
            'day_fut': round(day_fut.get(k, 0)),
            'day_opt_lots': round(do.get('lots', 0)),
            'day_opt_top': do.get('top', ''),
        })
    # footprint: weekly futures + 20*(weekly options) + daily flow
    rows.sort(key=lambda r: -(abs(r['fut']) + 20 * (abs(r['put']) + abs(r['call']))
                              + abs(r['day_fut']) + 20 * abs(r['day_opt_lots'])))
    return {'fut_limgetsu': fut_lim, 'opt_as_of': opt_as_of, 'day_date': day_date,
            'rows': rows[:16]}


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
