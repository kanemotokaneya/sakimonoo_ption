#!/usr/bin/env python3
"""Parse the weekly OSE "日経平均オプション取引参加者別建玉残高"
(nk225op_oi_by_tp.xlsx): net long / short option OI by participant, per strike,
for puts and calls. This is the definitive "who holds which strike" view.

Layout per data row (0-indexed cols):
  0 rank | 1 strike(rank1 only)
  2 code 3 put-seller name 4 put-seller qty      (売超=net short puts)
  5 code 6 put-buyer  name 7 put-buyer  qty      (買超=net long  puts)
  8,9 spacer
  10 rank | 11 strike
  12 code 13 call-seller name 14 call-seller qty  (売超=net short calls)
  15 code 16 call-buyer  name 17 call-buyer  qty  (買超=net long  calls)
"""
import argparse
import json
import os
import openpyxl

# broker classification (mirrors extract_jnet)
_RULES = [
    ('us', ['ゴールドマン', 'ＪＰモルガン', 'シティ', 'ビーオブエー', 'モルガンＭＵＦＧ', 'メリル']),
    ('eu', ['ＵＢＳ', 'ソシエテ', 'バークレイズ', 'ＨＳＢＣ', 'ドイツ', 'ナティクシス', 'ＢＮＰ']),
    ('hf', ['ＡＢＮ', 'サスケハナ', 'インタラクティブ', 'フィリップ', 'Ｊトラスト']),
    ('domestic', ['野村', '大和', 'みずほ', '三菱', 'ＳＭＢＣ', 'ＳＢＩ', '楽天', '松井',
                  '岩井', '立花', 'むさし', '岡三', '東海東京', 'マネックス', 'ｅスマート']),
]
_LABEL = {'us': '米系', 'eu': '欧系', 'hf': 'HF代理', 'domestic': '国内', 'other': 'その他'}


def _cat(name):
    s = str(name or '')
    for cat, kws in _RULES:
        for kw in kws:
            if kw in s:
                return cat
    return 'other'


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_opt_weekly(path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    as_of = None
    for r in rows[:4]:
        for c in r:
            if c and '現在' in str(c):
                as_of = str(c).strip('（） ').replace('現在', '').strip()
    strikes = {}
    cur_p = cur_c = None
    for r in rows:
        if not r or len(r) < 8:
            continue
        # put side strike
        sp = _num(r[1]) if len(r) > 1 else None
        if sp:
            cur_p = int(sp)
            strikes.setdefault(cur_p, {'put': {'sellers': [], 'buyers': []},
                                       'call': {'sellers': [], 'buyers': []}})
        sc = _num(r[11]) if len(r) > 11 else None
        if sc:
            cur_c = int(sc)
            strikes.setdefault(cur_c, {'put': {'sellers': [], 'buyers': []},
                                       'call': {'sellers': [], 'buyers': []}})
        # put seller / buyer
        if cur_p is not None:
            pn, pq = (r[3] if len(r) > 3 else None), (_num(r[4]) if len(r) > 4 else None)
            if pn and pq:
                strikes[cur_p]['put']['sellers'].append([str(pn).strip(), pq, _cat(pn)])
            bn, bq = (r[6] if len(r) > 6 else None), (_num(r[7]) if len(r) > 7 else None)
            if bn and bq:
                strikes[cur_p]['put']['buyers'].append([str(bn).strip(), bq, _cat(bn)])
        # call seller / buyer
        if cur_c is not None:
            cn, cq = (r[13] if len(r) > 13 else None), (_num(r[14]) if len(r) > 14 else None)
            if cn and cq:
                strikes[cur_c]['call']['sellers'].append([str(cn).strip(), cq, _cat(cn)])
            bn2, bq2 = (r[16] if len(r) > 16 else None), (_num(r[17]) if len(r) > 17 else None)
            if bn2 and bq2:
                strikes[cur_c]['call']['buyers'].append([str(bn2).strip(), bq2, _cat(bn2)])

    # per-participant aggregate: net = long(buyer) - short(seller)
    part = {}
    for k, sd in strikes.items():
        for side in ('put', 'call'):
            for b, q, cat in sd[side]['buyers']:
                part.setdefault(b, {'put': 0.0, 'call': 0.0, 'cat': cat})[side] += q
            for b, q, cat in sd[side]['sellers']:
                part.setdefault(b, {'put': 0.0, 'call': 0.0, 'cat': cat})[side] -= q

    # notable single holdings (largest net long/short at any strike)
    notable = []
    for k, sd in strikes.items():
        for side in ('put', 'call'):
            for b, q, cat in sd[side]['buyers']:
                notable.append({'strike': k, 'side': side, 'dir': 'long',
                                'broker': b, 'qty': q, 'cat': cat, 'cat_label': _LABEL[cat]})
            for b, q, cat in sd[side]['sellers']:
                notable.append({'strike': k, 'side': side, 'dir': 'short',
                                'broker': b, 'qty': q, 'cat': cat, 'cat_label': _LABEL[cat]})
    notable.sort(key=lambda x: -x['qty'])

    return {'as_of': as_of, 'strikes': strikes,
            'participants': part, 'notable': notable[:20]}


def build(data_dir):
    import glob
    import re
    files = glob.glob(os.path.join(data_dir, '*nk225op_oi_by_tp*.xlsx'))
    if not files:
        return None
    files.sort()
    path = files[-1]
    m = re.search(r'(\d{8})', os.path.basename(path))
    out = parse_opt_weekly(path)
    out['date'] = m.group(1) if m else None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', default='data')
    ap.add_argument('--out', default='data/opt_weekly.json')
    a = ap.parse_args()
    out = build(a.data_dir)
    if not out:
        print('[opt_weekly] no nk225op_oi_by_tp file found')
        return
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    n = len(out['strikes'])
    print('[opt_weekly] wrote %s | %d strikes | as_of %s' % (a.out, n, out.get('as_of')))
    # quick peek
    for k in [69000, 69500, 70000, 72000]:
        sd = out['strikes'].get(k)
        if sd:
            pb = sd['put']['buyers'][:1]
            cb = sd['call']['buyers'][:1]
            print('  %d: P買超%s C買超%s' % (
                k, (pb[0][:2] if pb else '-'), (cb[0][:2] if cb else '-')))


if __name__ == '__main__':
    main()
