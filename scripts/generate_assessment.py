#!/usr/bin/env python3
"""
JPX Market Analysis - Assessment Generator (generate_assessment.py)
====================================================================
Reads data.json and generates ⑧ 総合評価 using Google Gemini API.

Usage:
    python generate_assessment.py --data data.json [--key YOUR_API_KEY]
"""

import argparse
import json
import os
import sys
import time
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


# Model: gemini-2.5-flash (stable, free tier)
GEMINI_MODEL = 'gemini-2.5-flash'
FALLBACK_MODELS = ['gemini-2.0-flash']

SYSTEM_PROMPT = """あなたはJPXデリバティブ市場を専門とするトレーディングアドバイザーです。
以下のデータを統合し、日本語で実践的なトレード判断材料を生成してください。
読者は日経225先物・オプションを実際に売買する個人トレーダーです。

【出力フォーマット】
以下の4項目を記述してください。各項目3-5文。HTMLタグは使わないでください。
具体的な価格水準を必ず数字で示すこと。曖昧な表現は避ける。

【IVの扱い（重要）】
・ATM IVの水準と期間構造（期近が高い/低い）から相場の警戒度を読む。
・プットスキュー（下方IV−上方IV）が厚い＝下方ヘッジ需要・暴落警戒。薄い/フラット＝楽観。
・建玉が大きく増えた行使価格は、そのストライクのIVの動きも併せて売買方向を推定する：OI増＋IV上昇＝買い需要（上抜け加速やヘッジ買い）、OI増＋IV低下/横ばい＝売り（コール売り/プット売り＝抵抗・壁）。
・ただしJ-NET手口に売買区分は無いため、IVとprice actionで補強しつつ断定は避ける。

■ 先物の方向性（ロング or ショート）
・建玉増減、海外勢のポジション、PCR、先物ベーシスから総合判断し、「ロング寄り」「ショート寄り」「様子見」のいずれかを明示。
・判断根拠を2-3個の具体的データで裏付ける（例: 「ラージ+XX枚の買い増し」「PCR 1.97は弱気過剰」）。

■ 押し目買い・戻り売りの水準
・大口手口（J-NET）、建玉壁（P壁/C壁）、Max Pain、ピボットポイントから、押し目買いゾーンと戻り売りゾーンを特定。
・「XX,000円付近まで押したら買い」「XX,000円付近は上値が重い」のように具体的な価格帯で示す。
・壁が補強されているか崩壊しつつあるかにも言及。

■ オプション売りの安全圏
・OTM確率、建玉壁の厚さ、参加者のポジション（ABN/BNPなどのHF代理がどこに売り建てているか）から、プット売り・コール売りの推奨ゾーンを提示。
・「P XX,000以下は建玉壁XX枚＋OTM確率XX%で売りエッジあり」のように根拠付き。
・IVも必ず考慮: IVが高い行使価格ほど売りプレミアムが厚く妙味がある（例「C72,000はIV XX%で割高＝売り候補」）。下方プットスキューが厚いほどプット売りの受取は大きいが暴落リスクも比例して高い点に留意。
・危険な行使価格帯（売ってはいけないゾーン）も明示。

■ リスクシナリオ
・現在のポジションが崩れるトリガー（IV/スキューの急変＝特に下方IVの跳ね上がり、壁の崩壊、海外勢の反転など）。
・その場合の損切り水準やヘッジアクション（mini先物でデルタヘッジなど）を具体的に提案。
"""


def build_data_summary(data, iv=None):
    """Extract key data points for the LLM prompt."""
    lines = []
    meta = data.get('metadata', {})
    s01 = data.get('s01', {})
    lines.append('日付: %s' % meta.get('date_formatted', ''))
    lines.append('ATM: %s' % meta.get('atm', ''))
    lines.append('日経平均終値: %s' % s01.get('nikkei_close', ''))
    lines.append('VI: %s' % s01.get('vi', 'N/A'))
    lines.append('SQ: %s (残り%d営業日)' % (meta.get('sq_label', ''), meta.get('days_to_sq', 0)))

    # Futures OI
    s02 = data.get('s02', {})
    if 'error' not in s02:
        lines.append('')
        lines.append('--- 先物建玉 ---')
        for key, label in [('nk225_large', 'ラージ'), ('nk225_mini', 'mini'), ('topix', 'TOPIX')]:
            sec = s02.get(key, {})
            lines.append('%s: 前日比 %+d' % (label, sec.get('total_change', 0)))

    # Options OI changes
    s04 = data.get('s04', {})
    if 'error' not in s04:
        lg = s04.get('large', {})
        lines.append('')
        lines.append('--- OP建玉増減 ---')
        lines.append('P合計: %+d / C合計: %+d' % (lg.get('put_total_change', 0), lg.get('call_total_change', 0)))

    # Important OI changes
    s05 = data.get('s05', [])
    if s05:
        lines.append('')
        lines.append('--- 重要建玉変化(±300) ---')
        for c in s05[:10]:
            lines.append('%s %s: %+d (OI: %d)' % (c['type'], c['strike'], c['change'], c.get('oi', 0)))

    # OI distribution
    s06 = data.get('s06', {})
    dist = s06.get('distribution', [])
    if dist:
        lines.append('')
        lines.append('--- 建玉分布 ---')
        max_p = max(dist, key=lambda d: d['put_oi'])
        max_c = max(dist, key=lambda d: d['call_oi'])
        lines.append('P壁: %d (%d枚)' % (max_p['strike'], max_p['put_oi']))
        lines.append('C壁: %d (%d枚)' % (max_c['strike'], max_c['call_oi']))

    # J-NET
    s07 = data.get('s07', [])
    if s07:
        lines.append('')
        lines.append('--- J-NET大口 ---')
        for t in s07[:8]:
            pair = ' [対当]' if t.get('is_pair') else ''
            lines.append('%s: %s %d枚%s' % (t['product'][:30], t['participant'], t['volume'], pair))

    # Indicators
    ind = data.get('indicators', {})
    if ind:
        lines.append('')
        lines.append('--- 指標 ---')
        if ind.get('pcr_volume') is not None:
            lines.append('PCR(取引高): %.2f (%s)' % (ind['pcr_volume'], ind.get('pcr_signal', '')))
        if ind.get('max_pain'):
            lines.append('Max Pain: %s (ATM差: %+d)' % (ind['max_pain'], ind.get('max_pain_diff', 0)))
        if ind.get('basis') is not None:
            lines.append('先物ベーシス: %+d (%s)' % (ind['basis'], ind.get('basis_signal', '')))

    # Participant analysis
    s09 = data.get('s09', {})
    if 'error' not in s09:
        profiles = s09.get('profiles', [])
        if profiles:
            lines.append('')
            lines.append('--- 参加者ポジション ---')
            for p in profiles[:8]:
                lines.append('%s [%s]: N225=%+d mini=%+d TOPIX=%+d P=%+d C=%+d → %s' % (
                    p['name'], p['category_label'],
                    p['nk225_large'], p['nk225_mini'], p['topix'],
                    p['put_net'], p['call_net'], p['strategy']))

    # Implied volatility / skew (from iv.json, nearest monthly expiry)
    if iv and not iv.get('error') and iv.get('expiries'):
        monthly = [e for e in iv['expiries'] if len(e['expiry']) == 6]
        if monthly:
            e0 = monthly[0]
            lines.append('')
            lines.append('--- IV/スキュー (%s月限) ---' % e0['expiry'][4:6].lstrip('0'))
            if e0.get('atm_iv'):
                lines.append('ATM IV: %.1f%%' % (e0['atm_iv'] * 100))
            if e0.get('skew_10pct') is not None:
                lines.append('プットスキュー(10%%下IV-10%%上IV): %+.1fpt（プラス=下方IVが高い=下方ヘッジ需要/暴落警戒）' % e0['skew_10pct'])
            ts = []
            for m in monthly[:4]:
                if m.get('atm_iv'):
                    ts.append('%s月 %.1f%%' % (m['expiry'][4:6].lstrip('0'), m['atm_iv'] * 100))
            if ts:
                lines.append('ATM IV期間構造: ' + ' / '.join(ts))
            spot = e0.get('underlying') or 0
            picks = []
            for pt in e0.get('smile', []):
                k = pt.get('strike')
                ivv = pt.get('iv')
                if ivv and spot and 0.85 * spot <= k <= 1.15 * spot and k % 1000 == 0:
                    side = 'P' if k < spot else ('C' if k > spot else 'ATM')
                    picks.append('%s%d=%.1f%%' % (side, k, ivv * 100))
            if picks:
                step = max(1, len(picks) // 7)
                lines.append('主要ストライクIV: ' + '  '.join(picks[::step]))

    return '\n'.join(lines)


def call_gemini(api_key, prompt, data_summary, model=None):
    """Call Google Gemini API with retry on 429/503."""
    model = model or GEMINI_MODEL
    url = 'https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s' % (model, api_key)

    payload = {
        'contents': [{
            'parts': [{'text': prompt + '\n\n--- データ ---\n' + data_summary}]
        }],
        'generationConfig': {
            'temperature': 0.3,
            'maxOutputTokens': 3000,
        }
    }

    body = json.dumps(payload).encode('utf-8')

    for attempt in range(3):
        try:
            req = Request(url, data=body, headers={
                'Content-Type': 'application/json',
            })
            resp = urlopen(req, timeout=60)
            result = json.loads(resp.read().decode('utf-8'))
            candidates = result.get('candidates', [])
            if candidates:
                parts = candidates[0].get('content', {}).get('parts', [])
                if parts:
                    return parts[0].get('text', '')
            print('[assess] Gemini returned no text', file=sys.stderr)
            print('[assess] Response: %s' % json.dumps(result, ensure_ascii=False)[:500], file=sys.stderr)
            return None
        except HTTPError as e:
            code = e.code
            body_text = ''
            try:
                body_text = e.read().decode('utf-8')[:300]
            except:
                pass
            if code in (429, 503):
                wait = (attempt + 1) * 15
                label = 'Rate limited' if code == 429 else 'Service unavailable'
                print('[assess] %s (%d). Retrying in %ds... (%d/3)' % (label, code, wait, attempt + 1), file=sys.stderr)
                time.sleep(wait)
            elif code == 400:
                print('[assess] Bad request (400): %s' % body_text, file=sys.stderr)
                return None
            elif code == 403:
                print('[assess] Forbidden (403) - check API key: %s' % body_text, file=sys.stderr)
                return None
            else:
                print('[assess] HTTP %d: %s' % (code, body_text), file=sys.stderr)
                return None
        except URLError as e:
            print('[assess] Network error: %s' % e, file=sys.stderr)
            return None
        except Exception as e:
            print('[assess] Unexpected error: %s' % e, file=sys.stderr)
            return None

    print('[assess] All retries failed for %s' % model, file=sys.stderr)
    return None


def run(args):
    api_key = args.key or os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        print('[assess] No API key. Skipping.', file=sys.stderr)
        return

    with open(args.data, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Load iv.json (optional) from the same directory as data.json
    iv = None
    _ivpath = os.path.join(os.path.dirname(args.data) or '.', 'iv.json')
    if os.path.exists(_ivpath):
        try:
            with open(_ivpath, 'r', encoding='utf-8') as f:
                iv = json.load(f)
        except Exception as _e:
            print('[assess] iv.json load error: %s' % _e, file=sys.stderr)

    data_summary = build_data_summary(data, iv=iv)
    print('[assess] Data summary: %d chars' % len(data_summary), file=sys.stderr)

    # Try primary model, then fallbacks
    models_to_try = [GEMINI_MODEL] + FALLBACK_MODELS
    assessment = None

    for model in models_to_try:
        print('[assess] Trying model: %s' % model, file=sys.stderr)
        assessment = call_gemini(api_key, SYSTEM_PROMPT, data_summary, model=model)
        if assessment:
            print('[assess] Success with %s (%d chars)' % (model, len(assessment)), file=sys.stderr)
            break
        print('[assess] %s failed, trying next...' % model, file=sys.stderr)

    if assessment:
        data['s08_assessment'] = assessment
        with open(args.data, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print('[assess] Saved to %s' % args.data, file=sys.stderr)
    else:
        print('[assess] All models failed. Assessment not generated.', file=sys.stderr)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate market assessment via Gemini API')
    parser.add_argument('--data', default='data.json', help='Path to data.json')
    parser.add_argument('--key', default=None, help='Gemini API key (or set GEMINI_API_KEY env)')
    args = parser.parse_args()
    run(args)
