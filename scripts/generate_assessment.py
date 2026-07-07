#!/usr/bin/env python3
"""Deterministic daily assessment (定型8) builder.

Replaces the old Gemini generator. Reads the already-computed pipeline outputs
(data.json / greeks.json / iv.json) and composes a factual market assessment
purely from real numbers -- no API key, no hallucination. Writes s08_assessment
+ s08_source='auto' into data.json.

Priority in run_pipeline: manual_assessment_<date>.md (manual) > this (auto).
"""
import argparse
import json
import os


def _load(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _fmt(n):
    try:
        return format(int(round(n)), ',')
    except Exception:
        return str(n)


def _skew(iv, expiry='202607'):
    ee = next((x for x in (iv or {}).get('expiries', []) if x['expiry'] == expiry), None)
    if not ee:
        return None
    atm = ee.get('atm_iv'); spot = ee.get('underlying')
    sm = [p for p in ee.get('smile', []) if p.get('iv')]
    if not (atm and spot and sm):
        return None
    pk = min(sm, key=lambda p: abs(p['strike'] - spot * 0.90))
    return (pk['iv'] - atm) * 100


def build_assessment(data_dir, data_json_path):
    data = _load(data_json_path) or {}
    greeks = _load(os.path.join(data_dir, 'greeks.json')) or {}
    iv = _load(os.path.join(data_dir, 'iv.json')) or {}
    ghist = _load(os.path.join(data_dir, 'greeks_history.json')) or {}
    ind = data.get('indicators', {})

    exps = greeks.get('expiries', [])
    e = exps[0] if exps else {}
    spot = e.get('spot')
    atm_chg = (e.get('atm_iv_chg') or 0) * 100
    front_atm = None; term = []
    for ex in ['202607', '202608', '202609']:
        q = next((x for x in iv.get('expiries', []) if x['expiry'] == ex), None)
        if q:
            term.append((ex[4:6], q['atm_iv'] * 100))
            if ex == '202607':
                front_atm = q['atm_iv'] * 100
    skew = _skew(iv)

    prev_spot = None
    if ghist:
        ds = sorted(ghist.keys())
        if len(ds) >= 2:
            prev_spot = ghist[ds[-2]].get('spot')
    chg = pct = None
    if spot and prev_spot:
        chg = spot - prev_spot; pct = chg / prev_spot * 100

    zB, zB2 = e.get('zero_gamma_B', {}), e.get('zero_gamma_B2', {})
    nA = (e.get('net_A') or {}).get('gamma')
    nB = (e.get('net_B') or {}).get('gamma')
    nB2 = (e.get('net_B2') or {}).get('gamma')
    lens = 'B2' if abs(atm_chg) >= 2.0 else 'B'
    z_use = zB2 if lens == 'B2' else zB
    sign = z_use.get('sign_at_spot')
    regime = '安定(ピン優勢)' if sign == 'positive' else '不安定(加速方向)'
    regime_mk = '\U0001F7E9' if sign == 'positive' else '\U0001F7E5'

    walls_r = ind.get('walls_reinforced', [])[:4]
    top_g = e.get('top_gamma', [])[:3]

    P = []
    if spot is not None and chg is not None:
        arrow = '上昇' if chg > 0 else ('下落' if chg < 0 else '横ばい')
        P.append('本日終値は%s(前日比%+d、%+.2f%%)で%s。*本欄はデータから自動生成した定型サマリー(手動分析が無い日)。'
                 % (_fmt(spot), round(chg), pct, arrow))
    elif spot is not None:
        P.append('本日終値は%s。*データから自動生成した定型サマリー。' % _fmt(spot))

    ivbits = []
    if front_atm is not None:
        ivbits.append('7月限ATM IVは%.1f%%(前日比%+.1fpt)' % (front_atm, atm_chg))
    if len(term) >= 2:
        ivbits.append('期間構造は' + '＞'.join('%s月%.1f' % (m, v) for m, v in term))
    if skew is not None:
        ivbits.append('プットスキュー(下方10%%−ATM)は%+.1fpt' % skew)
    if ivbits:
        P.append('IV・スキュー：' + '、'.join(ivbits) + '。スキューが厚いほど下方ヘッジ需要が強い。')

    wbits = []
    if walls_r:
        wbits.append('前日比で建玉が増えた主な行使価格は '
                     + '・'.join('%s%s(+%d)' % (w['type'], _fmt(w['strike']), w['change']) for w in walls_r))
    if ind.get('max_pain') is not None:
        wbits.append('MaxPainは%s' % _fmt(ind['max_pain']))
    if ind.get('pcr') is not None:
        wbits.append('PCRは%.2f' % ind['pcr'])
    if wbits:
        P.append('OI・壁：' + '。'.join(wbits) + '。OI増加は新規/手仕舞い両方を含むため出来高と併せて解釈する。')

    gbits = []
    if None not in (nA, nB, nB2):
        gbits.append('netΓは A%+.1f・B%+.1f・B2%+.1f' % (nA, nB, nB2))
    if z_use.get('flip') is not None:
        rel = '上' if (spot and z_use['flip'] and z_use['flip'] >= spot) else '下'
        gbits.append('本日はIV変動%+.1fptにつき%s基準が妥当で、ゼロガンマ転換点は%s(現値の%s)'
                     % (atm_chg, lens, _fmt(z_use['flip']), rel))
    gbits.append('現値の地合いは%s%s' % (regime_mk, regime))
    if top_g:
        gbits.append('高ガンマ(ピン候補)は ' + '・'.join(_fmt(r['strike']) for r in top_g))
    P.append('GEX・ガンマ：' + '。'.join(gbits) + '。正ガンマ＝ピン/安定、負ガンマ＝ブレイク時に加速。')

    sbits = []
    if z_use.get('flip') is not None and spot is not None:
        if sign == 'positive':
            sbits.append('現値はゼロガンマの上でピンが効きやすく、転換点(%s)割れで負ガンマ側は荒れやすい' % _fmt(z_use['flip']))
        else:
            sbits.append('現値はゼロガンマの下＝加速ゾーンで、転換点(%s)回復でピン/安定側に戻りやすい' % _fmt(z_use['flip']))
    if walls_r:
        strikes = sorted(set(w['strike'] for w in walls_r))
        sbits.append('上下の厚い壁(%s)が目先の攻防ライン' % '・'.join(_fmt(s) for s in strikes))
    P.append('構造まとめ(方向は断定しない)：' + '。'.join(sbits)
             + '。J-NET手口は売買区分が無いため方向は断定せず翌日の値動きで事後確認する。')

    return '\n\n'.join(P)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--key', default='')
    a = ap.parse_args()
    data_dir = os.path.dirname(os.path.abspath(a.data))
    text = build_assessment(data_dir, a.data)
    data = _load(a.data) or {}
    data['s08_assessment'] = text
    data['s08_source'] = 'auto'
    with open(a.data, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print('[assessment] deterministic teikei-8 written (%d chars) -> auto' % len(text))


if __name__ == '__main__':
    main()
