#!/usr/bin/env python3
"""
JPX Market Analysis - Renderer (render.py)
============================================
Reads data.json from extract.py and generates:
  1. JPX_market_analysis_YYYYMMDD.md  (Markdown report)
  2. index.html                       (Dashboard)
  3. pnl_simulator.html               (P&L Simulator)
  4. JPX_portal_YYYYMMDD.html         (Archive copy)
  5. Archive snippet (stdout)

Usage:
    python render.py [--data data.json] [--outdir ./output]

Dependencies: None (pure Python, no external libraries)
"""

import argparse
import json
import os
import sys
import copy

# ============================================================
# Formatting Helpers
# ============================================================

def fnum(n, plus=False):
    if n is None:
        return '-'
    if isinstance(n, float):
        if n == int(n):
            n = int(n)
        else:
            s = '{:,.1f}'.format(n)
            if plus and n > 0:
                s = '+' + s
            return s
    s = '{:,}'.format(int(n))
    if plus and n > 0:
        s = '+' + s
    return s

def fnum_short(n, plus=False):
    """Format number abbreviated: 28781932911 -> '287.8億', 44194 -> '44.2K'."""
    if n is None:
        return '-'
    v = float(n)
    sign = '+' if plus and v > 0 else ''
    av = abs(v)
    if av >= 1e8:  # 1億 = 100,000,000
        return '%s%.1f億' % (sign, v / 1e8)
    if av >= 1e4:  # 1万
        return '%s%.1f万' % (sign, v / 1e4)
    if av >= 1000:
        return '%s%.1fK' % (sign, v / 1000)
    return '%s%s' % (sign, fnum(int(v)))

def fpct(n):
    if n is None:
        return '-'
    return '{:.1f}%'.format(n)

def sign_class(n):
    if n is None:
        return ''
    return 'positive' if n > 0 else 'negative' if n < 0 else ''

def esc(s):
    if s is None:
        return ''
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

def _js_str(s):
    return str(s).replace('\\', '\\\\').replace("'", "\\'").replace('\n', '').replace('\r', '')


# ============================================================
# Markdown Report Builder
# ============================================================

def build_markdown(data):
    meta = data['metadata']
    md = []
    md.append('# JPX Market Analysis %s' % meta['date_formatted'])
    md.append('')
    md.append('> ATM: %s / VI: %s / %s / SQまで%d営業日' % (
        fnum(meta.get('atm')), meta.get('vi', '-'),
        meta.get('sq_label', ''), meta.get('days_to_sq', 0)))
    md.append('')

    s01 = data.get('s01', {})
    md.append('## ① 日経平均・VI分析')
    md.append('')
    if s01.get('nikkei_close'):
        md.append('- 日経平均終値: **%s**' % fnum(s01['nikkei_close']))
    if s01.get('vi'):
        md.append('- 日経平均VI: **%s**' % s01['vi'])
    r1d = s01.get('range_1d', {})
    r1w = s01.get('range_1w', {})
    if r1d:
        md.append('- 1日予測値幅: %s (%s 〜 %s)' % (fnum(r1d.get('width')), fnum(r1d.get('low')), fnum(r1d.get('high'))))
    if r1w:
        md.append('- 1週予測値幅: %s (%s 〜 %s)' % (fnum(r1w.get('width')), fnum(r1w.get('low')), fnum(r1w.get('high'))))
    md.append('')

    s02 = data.get('s02', {})
    md.append('## ② 先物建玉残高')
    md.append('')
    if 'error' not in s02:
        md.append('| 銘柄 | 建玉残高 | 前日比 |')
        md.append('|------|---------|--------|')
        for key, label in [('nk225_large', '日経225ラージ'), ('nk225_mini', '日経225mini'), ('topix', 'TOPIX')]:
            sec = s02.get(key, {})
            md.append('| %s | %s | %s |' % (label, fnum(sec.get('total_oi')), fnum(sec.get('total_change'), plus=True)))
        for key, label in [('nk225_large', 'ラージ'), ('nk225_mini', 'mini'), ('topix', 'TOPIX')]:
            sec = s02.get(key, {})
            months = sec.get('months', [])
            if months:
                md.append('')
                md.append('**%s 限月別**:' % label)
                for m in months:
                    md.append('- %s: OI %s (前日比 %s)' % (m['label'], fnum(m.get('oi')), fnum(m.get('change'), plus=True)))
    else:
        md.append('データなし')
    md.append('')

    s03 = data.get('s03', {})
    md.append('## ③ オプション総取引代金')
    md.append('')
    if 'error' not in s03:
        for block_key, block_label in [('large', 'ラージ'), ('mini', 'ミニ')]:
            b = s03.get(block_key, {})
            if b:
                md.append('**%s**:' % block_label)
                md.append('- プット: %s枚 / %s百万円' % (fnum(b.get('put_volume')), fnum(b.get('put_value'))))
                md.append('- コール: %s枚 / %s百万円' % (fnum(b.get('call_volume')), fnum(b.get('call_value'))))
                md.append('- 合計: %s枚 / %s百万円' % (fnum(b.get('total_volume')), fnum(b.get('total_value'))))
                md.append('- J-NET比率: %s' % fpct(b.get('jnet_ratio')))
                md.append('')
    else:
        md.append('データなし')
    md.append('')

    s04 = data.get('s04', {})
    md.append('## ④ オプション建玉増減')
    md.append('')
    if 'error' not in s04:
        for block_key, block_label in [('large', 'ラージ'), ('mini', 'ミニ')]:
            b = s04.get(block_key, {})
            if b:
                md.append('**%s**:' % block_label)
                md.append('- プット合計: OI %s / 前日比 %s' % (fnum(b.get('put_total_oi')), fnum(b.get('put_total_change'), plus=True)))
                md.append('- コール合計: OI %s / 前日比 %s' % (fnum(b.get('call_total_oi')), fnum(b.get('call_total_change'), plus=True)))
                md.append('')
    md.append('')

    s05 = data.get('s05', [])
    md.append('## ⑤ 重要建玉変化（±300枚以上）')
    md.append('')
    if s05:
        md.append('| 銘柄 | 建玉残高 | 前日比 |')
        md.append('|------|---------|--------|')
        for c in s05:
            md.append('| %s | %s | %s |' % (c['name'], fnum(c.get('oi')), fnum(c['change'], plus=True)))
    else:
        md.append('該当なし')
    md.append('')

    s06 = data.get('s06', {})
    md.append('## ⑥ 建玉分布（ATM±5,000円）')
    md.append('')
    if 'distribution' in s06:
        md.append('ATM = %s' % fnum(s06.get('atm')))
        md.append('')
        md.append('| 行使価格 | P建玉 | P前日比 | C建玉 | C前日比 |')
        md.append('|---------|-------|---------|-------|---------|')
        for d in s06['distribution']:
            atm_mark = ' **←ATM**' if d.get('is_atm') else ''
            md.append('| %s%s | %s | %s | %s | %s |' % (fnum(d['strike']), atm_mark, fnum(d['put_oi']), fnum(d['put_change'], plus=True), fnum(d['call_oi']), fnum(d['call_change'], plus=True)))
    md.append('')

    s07 = data.get('s07', [])
    md.append('## ⑦ 大口手口（J-NET）')
    md.append('')
    if s07:
        md.append('| 銘柄 | 参加者 | 取引高 | 分類 |')
        md.append('|------|-------|--------|------|')
        for t in s07:
            pair = ' 🔄' if t.get('is_pair') else ''
            cat_label = {'us': '米系', 'eu': '欧系', 'hf': 'HF代理', 'domestic': '国内'}.get(t['category'], 'その他')
            md.append('| %s | %s%s | %s | %s |' % (t['product'], t['participant'], pair, fnum(t['volume']), cat_label))
    else:
        md.append('該当なし')
    md.append('')

    md.append('## ⑧ 総合評価')
    md.append('')
    md.append('> ※ このセクションはLLM（Claude）による定性分析が必要です。')
    md.append('')

    s09 = data.get('s09', {})
    md.append('## ⑨ 参加者別建玉分析')
    md.append('')
    if 'error' not in s09:
        if s09.get('source') == 'cache':
            md.append('> ※ %s時点のキャッシュデータ（参考値）' % s09.get('data_date', '?'))
            md.append('')
        fut = s09.get('futures', {})
        if fut:
            for sec_key, sec_label in [('nk225_large', 'N225ラージ'), ('nk225_mini', 'N225mini'), ('topix', 'TOPIX')]:
                sec = fut.get(sec_key, {})
                if sec:
                    md.append('**%s**: 海外Net %s / 国内Net %s' % (sec_label, fnum(sec.get('overseas_net'), plus=True), fnum(sec.get('domestic_net'), plus=True)))
            md.append('')
            for sec_key, sec_label in [('nk225_large', 'N225ラージ'), ('nk225_mini', 'N225mini'), ('topix', 'TOPIX')]:
                sec = fut.get(sec_key, {})
                if sec:
                    sellers = sec.get('sellers', [])[:5]
                    buyers = sec.get('buyers', [])[:5]
                    if sellers or buyers:
                        md.append('**%s 上位**:' % sec_label)
                        md.append('- 売超: %s' % ', '.join(['%s -%s' % (s['name'], fnum(s['volume'])) for s in sellers]))
                        md.append('- 買超: %s' % ', '.join(['%s +%s' % (b['name'], fnum(b['volume'])) for b in buyers]))
                        md.append('')
        profiles = s09.get('profiles', [])
        if profiles:
            md.append('### 統合プロファイル')
            md.append('')
            md.append('| 参加者 | 分類 | N225ラージ | mini | TOPIX | P Net | C Net | 推定戦略 |')
            md.append('|-------|------|-----------|------|-------|-------|-------|---------|')
            for p in profiles[:10]:
                md.append('| %s | %s | %s | %s | %s | %s | %s | %s |' % (
                    p['name'], p['category_label'], fnum(p['nk225_large'], plus=True), fnum(p['nk225_mini'], plus=True),
                    fnum(p['topix'], plus=True), fnum(p['put_net'], plus=True), fnum(p['call_net'], plus=True), p['strategy']))
            md.append('')
    else:
        md.append('週次データなし')
    md.append('')

    s10 = data.get('s10', {})
    if not s10.get('skipped'):
        md.append('## ⑩ 投資部門別 現物フロー')
        md.append('')
        labels = {'foreigners': '海外投資家', 'individuals': '個人', 'institutions': '法人', 'investment_trusts': '投資信託', 'proprietary': '自己'}
        for key, label in labels.items():
            v = s10.get(key, {})
            if v:
                md.append('- %s: %s億円' % (label, fnum(v.get('oku_yen'))))
        md.append('')

    s11 = data.get('s11', {})
    md.append('## ⑪ 戦略マップ')
    md.append('')
    otm = s11.get('otm_table', [])
    if otm:
        md.append('### OTM確率テーブル')
        md.append('')
        md.append('| 行使価格 | タイプ | VI-10 | 現在VI | VI+10 | BS価格 |')
        md.append('|---------|--------|-------|--------|-------|--------|')
        for o in otm:
            md.append('| %s | %s | %s | %s | %s | %s |' % (fnum(o['strike']), o['label'], fpct(o['otm_prob']['vi_minus10']), fpct(o['otm_prob']['vi_current']), fpct(o['otm_prob']['vi_plus10']), fnum(o['bs_price'])))
        md.append('')
    edges = s11.get('edge_scores', [])
    if edges:
        md.append('### ゾーン別売りエッジ')
        md.append('')
        md.append('| ゾーン | タイプ | 壁最大OI | スコア | 評価 |')
        md.append('|-------|--------|---------|--------|------|')
        for e in edges:
            stars = '★' * e['stars'] + '☆' * (5 - e['stars'])
            md.append('| %s | %s | %s @%s | %.2f | %s |' % (e['zone'], e['type'], fnum(e['wall_max_oi']), fnum(e['wall_strike']), e['total_score'], stars))
        md.append('')

    return '\n'.join(md)


# ============================================================
# HTML Dashboard Builder
# ============================================================

DASHBOARD_CSS = r"""
:root{
  --bg:#06060f;--panel:#0c0c1d;--card:#111128;--border:#1e1e3a;
  --text:#e2e2f0;--sub:#8888aa;--accent:#818cf8;
  --red:#f87171;--green:#4ade80;--blue:#60a5fa;--yellow:#fbbf24;
  --put:#f87171;--call:#60a5fa;
  --us:#93c5fd;--eu:#c4b5fd;--hf:#fbbf24;--dom:#f87171;--overseas:#60a5fa;
}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:'Noto Sans JP','Outfit',sans-serif;font-size:13px;line-height:1.6}
a{color:var(--accent);text-decoration:none}
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
.topbar{position:sticky;top:0;z-index:100;background:rgba(6,6,15,.92);backdrop-filter:blur(12px);border-bottom:1px solid var(--border);padding:10px 20px;display:flex;align-items:center;justify-content:space-between}
.topbar .logo{font-family:Outfit;font-weight:700;font-size:16px;color:var(--accent)}
.topbar nav a{margin-left:16px;font-size:12px;color:var(--sub);transition:color .2s}
.topbar nav a:hover{color:var(--accent)}
.hero{text-align:center;padding:32px 16px 8px;position:relative;overflow:hidden}
.hero::before{content:'';position:absolute;top:-60%;left:50%;transform:translateX(-50%);width:600px;height:600px;background:radial-gradient(circle,rgba(129,140,248,.12) 0%,transparent 70%);pointer-events:none}
.hero h1{font-family:Outfit;font-size:22px;font-weight:700;color:#fff;position:relative;animation:fadeUp .6s ease-out}
.hero .sub{color:var(--sub);font-size:12px;margin-top:4px;position:relative}
@keyframes fadeUp{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
.kpi-strip{display:flex;justify-content:center;gap:24px;padding:12px 16px 18px;flex-wrap:wrap}
.kpi{text-align:center;padding:8px 16px;background:rgba(17,17,40,.6);border:1px solid var(--border);border-radius:8px;backdrop-filter:blur(4px)}
.kpi .label{font-size:9px;color:var(--sub);text-transform:uppercase;letter-spacing:.8px}
.kpi .value{font-family:'DM Mono',monospace;font-size:18px;font-weight:700;color:#fff}
.kpi .value.up{color:var(--green)}
.kpi .value.down{color:var(--red)}
.mobile-nav{display:none;text-align:center;padding:6px;border-bottom:1px solid var(--border)}
.mobile-nav a{margin:0 8px;font-size:11px;color:var(--sub)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:10px;padding:10px 16px 30px;max-width:1200px;margin:0 auto}
.card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px;cursor:pointer;transition:all .25s ease}
.card:hover{border-color:rgba(129,140,248,.4);box-shadow:0 0 20px rgba(129,140,248,.06)}
.card.open{grid-column:1/-1;border-color:var(--accent);background:var(--panel);cursor:default;box-shadow:0 0 30px rgba(129,140,248,.08)}
.card-hdr{display:flex;align-items:center;gap:8px}
.card-hdr .icon{font-size:18px}
.card-hdr .title{font-family:Outfit;font-weight:600;font-size:14px;color:#fff}
.card-hdr .arrow{margin-left:8px;color:var(--sub);font-size:12px;transition:transform .25s}
.card-hdr .date-badge{margin-left:auto;font-size:9px;font-family:'DM Mono',monospace;color:var(--sub);background:rgba(255,255,255,.05);padding:2px 6px;border-radius:4px;white-space:nowrap}
.card-hdr .date-badge.weekly{color:#fbbf24;background:rgba(251,191,36,.12)}
.section-hdr{grid-column:1/-1;display:flex;align-items:center;gap:10px;margin:16px 2px 2px}
.section-hdr .section-title{font-family:Outfit;font-weight:700;font-size:11px;letter-spacing:.1em;color:var(--accent)}
.section-hdr .section-line{flex:1;height:1px;background:var(--border)}
.section-hdr:first-child{margin-top:4px}
.card.open .card-hdr .arrow{transform:rotate(90deg);color:var(--accent)}
.card-preview{margin-top:10px}
.card-detail{display:none;margin-top:14px;border-top:1px solid var(--border);padding-top:14px;animation:fadeUp .3s ease-out}
.card.open .card-detail{display:block}
.mini-metrics{display:flex;gap:12px;flex-wrap:wrap}
.mini-metric{flex:1;min-width:80px}
.mini-metric .mm-label{font-size:10px;color:var(--sub)}
.mini-metric .mm-value{font-family:'DM Mono',monospace;font-size:15px;font-weight:600}
.tag{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:600;margin:2px}
.tag-put{background:rgba(248,113,113,.15);color:var(--put)}
.tag-call{background:rgba(96,165,250,.15);color:var(--call)}
.tag-up{background:rgba(74,222,128,.15);color:var(--green)}
.tag-down{background:rgba(239,68,68,.15);color:var(--red)}
.tag-us{background:rgba(147,197,253,.15);color:var(--us)}
.tag-eu{background:rgba(196,181,253,.15);color:var(--eu)}
.tag-hf{background:rgba(251,191,36,.15);color:var(--hf)}
.tag-dom{background:rgba(248,113,113,.15);color:var(--dom)}
.summary-box{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0}
.summary-item{flex:1;min-width:140px;background:var(--card);border:1px solid var(--border);border-radius:8px;padding:10px;text-align:center}
.summary-item .si-label{font-size:10px;color:var(--sub)}
.summary-item .si-value{font-family:'DM Mono',monospace;font-size:16px;font-weight:600;margin-top:2px}
table{width:100%;border-collapse:collapse;margin:10px 0;font-size:12px}
th{background:rgba(17,17,40,.8);color:var(--sub);font-weight:600;text-align:left;padding:6px 8px;border-bottom:1px solid var(--border);position:sticky;top:0}
td{padding:5px 8px;border-bottom:1px solid rgba(30,30,58,.4)}
tr:hover td{background:rgba(129,140,248,.03)}
tr.atm-row{background:rgba(251,191,36,.08)}
.bar-row{display:flex;align-items:center;gap:8px;margin:4px 0;font-size:11px}
.bar-label{width:120px;text-align:right;color:var(--sub);flex-shrink:0;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
.bar-track{flex:1;height:16px;background:rgba(17,17,40,.6);border-radius:3px;position:relative;overflow:hidden}
.bar-fill{height:100%;border-radius:3px;min-width:1px;transition:width .4s ease}
.bar-fill.put{background:linear-gradient(90deg,var(--put),rgba(248,113,113,.6))}
.bar-fill.call{background:linear-gradient(90deg,var(--call),rgba(96,165,250,.6))}
.bar-fill.up{background:linear-gradient(90deg,var(--green),rgba(74,222,128,.6))}
.bar-fill.down{background:linear-gradient(90deg,var(--red),rgba(239,68,68,.6))}
.bar-val{width:60px;font-family:'DM Mono',monospace;font-size:11px;flex-shrink:0}
.insight{background:rgba(129,140,248,.06);border:1px solid rgba(129,140,248,.15);border-radius:8px;padding:12px;margin-top:14px;font-size:12px;color:var(--sub);line-height:1.7}
.insight strong{color:var(--text)}
.analysis-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:8px;margin:12px 0}
.analysis-card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:10px}
.analysis-card .ac-title{font-size:11px;font-weight:600;color:var(--accent);margin-bottom:4px}
.analysis-card .ac-body{font-size:11px;color:var(--sub);line-height:1.5}
.zone-card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:12px;margin:8px 0}
.zone-card .zc-header{display:flex;justify-content:space-between;align-items:center}
.zone-card .zc-name{font-weight:600;font-size:13px}
.zone-card .zc-stars{color:var(--yellow);font-size:14px}
.zone-card .zc-detail{font-size:10px;color:var(--sub);margin-top:4px}
.footer{text-align:center;padding:24px;color:var(--sub);font-size:11px;border-top:1px solid var(--border);margin-top:20px}
.footer a{margin:0 8px}
.positive{color:var(--green)}
.negative{color:var(--red)}
@media(max-width:768px){
  .topbar nav{display:none}
  .mobile-nav{display:block}
  .grid{grid-template-columns:1fr}
  .kpi .value{font-size:15px}
  .kpi{padding:6px 10px}
  .analysis-cards{grid-template-columns:1fr}
}
"""

DASHBOARD_JS = r"""
(function(){
  var cards=document.querySelectorAll('.card[data-card]');
  var grid=document.querySelector('.grid');
  if(!grid)return;
  grid.addEventListener('click',function(e){
    var el=e.target;
    while(el&&el!==grid){
      if(el.dataset&&el.dataset.card!==undefined){
        toggleCard(el);
        return;
      }
      el=el.parentElement;
    }
  });
  function toggleCard(card){
    var wasOpen=card.classList.contains('open');
    for(var i=0;i<cards.length;i++){cards[i].classList.remove('open');}
    if(!wasOpen){
      if(!card.dataset.built){
        var fn=window['b_'+card.dataset.card];
        if(fn){
          var detail=card.querySelector('.card-detail');
          if(detail) detail.innerHTML=fn();
          card.dataset.built='1';
        }
        var initFn=window['init_'+card.dataset.card];
        if(initFn){try{initFn(card);}catch(e){console.error(e);}}
      }
      card.classList.add('open');
      setTimeout(function(){card.scrollIntoView({behavior:'smooth',block:'start'});},100);
    }
  }
})();
"""

# ============================================================
# 建玉推移カード用 — Canvasチャート描画ヘルパー (静的JS)
# ============================================================
OI_CHART_CSS = r"""
.oi-tabs{display:flex;gap:0;margin:8px 0;border-bottom:1px solid var(--border)}
.oi-tab{flex:1;padding:8px 4px;background:transparent;color:var(--sub);border:none;border-bottom:2px solid transparent;font-family:'Noto Sans JP',sans-serif;font-size:11px;cursor:pointer}
.oi-tab.oi-tab-active{color:var(--accent);border-bottom-color:var(--accent)}
.oi-chart-wrap{padding:8px 0}
.oi-canvas{width:100%;height:240px;display:block}
.oi-meta{font-size:10px;color:var(--sub);font-family:'DM Mono',monospace;padding:0 4px 4px;opacity:.7}
.oi-legend{display:flex;flex-wrap:wrap;gap:8px 12px;font-size:10px;color:var(--sub);padding:4px 0}
.oi-legend-item{display:flex;align-items:center;gap:4px;cursor:pointer}
.oi-legend-item .oi-swatch{width:10px;height:2px;border-radius:2px}
.oi-legend-item.oi-hidden{opacity:.35;text-decoration:line-through}
.oi-empty{padding:24px 12px;text-align:center;color:var(--sub);font-size:12px;border:1px dashed var(--border);border-radius:8px}
"""

OI_CHART_JS = r"""
(function(){
  if (typeof window.OI_TS_DATA === 'undefined') window.OI_TS_DATA = null;
  window._oi_state = { activeTab: 'futures', hidden: {} };

  function fmtK(n) {
    if (n === null || n === undefined || n === 0) return '0';
    var abs = Math.abs(n);
    if (abs >= 1000000) return (n/1000000).toFixed(1) + 'M';
    if (abs >= 1000) return Math.round(n/1000) + 'K';
    return Math.round(n).toString();
  }
  function fmtSigned(n) {
    if (n === 0) return '0';
    return (n > 0 ? '+' : '') + fmtK(n);
  }
  function fmtDateLabel(yyyymmdd) {
    if (!yyyymmdd || yyyymmdd.length !== 8) return yyyymmdd || '';
    return yyyymmdd.substring(4, 6) + '/' + yyyymmdd.substring(6, 8);
  }

  function drawChart(canvas, series, dates, hidden) {
    hidden = hidden || {};
    var dpr = window.devicePixelRatio || 1;
    var cssW = canvas.clientWidth || 320;
    var cssH = 240;
    canvas.width = cssW * dpr;
    canvas.height = cssH * dpr;
    canvas.style.height = cssH + 'px';
    var ctx = canvas.getContext('2d');
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, cssW, cssH);

    var pad = { l: 46, r: 12, t: 12, b: 32 };
    var plotW = cssW - pad.l - pad.r;
    var plotH = cssH - pad.t - pad.b;

    var visible = [];
    for (var s = 0; s < series.length; s++) {
      if (!hidden[series[s].label]) visible.push(series[s]);
    }
    if (!visible.length || !dates.length) {
      ctx.fillStyle = '#5a6276';
      ctx.font = "11px 'Noto Sans JP', sans-serif";
      ctx.textAlign = 'center';
      ctx.fillText('表示する系列がありません', cssW/2, cssH/2);
      return;
    }

    var allVals = [];
    for (var i = 0; i < visible.length; i++) {
      for (var j = 0; j < visible[i].data.length; j++) {
        if (typeof visible[i].data[j] === 'number') allVals.push(visible[i].data[j]);
      }
    }
    if (!allVals.length) return;
    var yMin = Math.min.apply(null, allVals);
    var yMax = Math.max.apply(null, allVals);
    if (yMin === yMax) { yMin -= 100; yMax += 100; }
    var yRange = yMax - yMin;
    yMin -= yRange * 0.05;
    yMax += yRange * 0.05;

    var nPts = dates.length;
    function xAt(i) { return pad.l + (nPts === 1 ? plotW/2 : (plotW * i / (nPts - 1))); }
    function yAt(v) { return pad.t + plotH * (1 - (v - yMin) / (yMax - yMin)); }

    ctx.strokeStyle = '#232733';
    ctx.lineWidth = 1;
    ctx.fillStyle = '#8b92a6';
    ctx.font = "10px 'DM Mono', monospace";
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (var g = 0; g <= 4; g++) {
      var gy = pad.t + plotH * g / 4;
      var gv = yMax - (yMax - yMin) * g / 4;
      ctx.beginPath();
      ctx.moveTo(pad.l, gy);
      ctx.lineTo(pad.l + plotW, gy);
      ctx.stroke();
      ctx.fillText(fmtK(gv), pad.l - 6, gy);
    }

    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    var labelStep = Math.max(1, Math.ceil(nPts / 6));
    for (var k = 0; k < nPts; k++) {
      if (k % labelStep !== 0 && k !== nPts - 1) continue;
      ctx.fillText(fmtDateLabel(dates[k]), xAt(k), pad.t + plotH + 6);
    }

    for (var p = 0; p < visible.length; p++) {
      var ser = visible[p];
      ctx.strokeStyle = ser.color;
      ctx.lineWidth = 1.8;
      ctx.beginPath();
      var started = false;
      for (var q = 0; q < ser.data.length; q++) {
        var v = ser.data[q];
        if (typeof v !== 'number') continue;
        var px = xAt(q), py = yAt(v);
        if (!started) { ctx.moveTo(px, py); started = true; }
        else ctx.lineTo(px, py);
      }
      ctx.stroke();
      if (ser.data.length) {
        var lastV = ser.data[ser.data.length - 1];
        if (typeof lastV === 'number') {
          ctx.fillStyle = ser.color;
          ctx.beginPath();
          ctx.arc(xAt(ser.data.length - 1), yAt(lastV), 3, 0, Math.PI*2);
          ctx.fill();
        }
      }
    }
  }

  var FUTURES_COLORS = { nk225_large: '#f59e0b', nk225_mini: '#3b82f6', topix: '#ec4899' };
  var FUTURES_LABELS = { nk225_large: '225ラージ', nk225_mini: '225mini', topix: 'TOPIX' };
  var OP_PUT_COLORS = ['#f87171', '#fb923c'];
  var OP_CALL_COLORS = ['#4ade80', '#22d3ee'];
  // Distinct categorical hues — the P/C distinction is carried by the tab,
  // so within a tab we use maximally-separated colors for legibility.
  var STRIKE_COLORS = ['#f59e0b','#3b82f6','#10b981','#ec4899','#a78bfa','#06b6d4','#ef4444','#84cc16'];
  var P_STRIKE_COLORS = STRIKE_COLORS;
  var C_STRIKE_COLORS = STRIKE_COLORS;

  function getSeriesFor(tab) {
    var D = window.OI_TS_DATA;
    if (!D || D.error) return [];
    var out = [];
    if (tab === 'nikkei') {
      if (D.nikkei) {
        out.push({ label: '日経225先物', color: '#fbbf24', data: D.nikkei });
      }
      return out;
    }
    if (tab === 'futures') {
      var keys = ['nk225_large', 'nk225_mini', 'topix'];
      for (var i = 0; i < keys.length; i++) {
        var k = keys[i];
        var fm = (D.futures && D.futures[k]) || {};
        if (fm.total) out.push({ label: FUTURES_LABELS[k], color: FUTURES_COLORS[k], data: fm.total });
      }
      return out;
    }
    if (tab === 'options_agg') {
      var agg = (D.options && D.options.aggregate) || {};
      var keys2 = Object.keys(agg).sort();
      for (var j = 0; j < keys2.length; j++) {
        var ek = keys2[j];
        var grp = agg[ek];
        var lab = grp.label || ek;
        out.push({ label: lab + ' P', color: OP_PUT_COLORS[j % 2], data: grp.put_total });
        out.push({ label: lab + ' C', color: OP_CALL_COLORS[j % 2], data: grp.call_total });
      }
      return out;
    }
    if (tab === 'top_puts') {
      var puts = (D.options && D.options.top_puts) || [];
      for (var m = 0; m < puts.length; m++) {
        out.push({ label: puts[m].short_label || puts[m].label, color: P_STRIKE_COLORS[m % P_STRIKE_COLORS.length], data: puts[m].oi_history });
      }
      return out;
    }
    if (tab === 'top_calls') {
      var calls = (D.options && D.options.top_calls) || [];
      for (var n = 0; n < calls.length; n++) {
        out.push({ label: calls[n].short_label || calls[n].label, color: C_STRIKE_COLORS[n % C_STRIKE_COLORS.length], data: calls[n].oi_history });
      }
      return out;
    }
    return [];
  }

  function getState(card) {
    if (!card._oiState) {
      // Default active tab = the first .oi-tab in this card
      var first = card.querySelector('.oi-tab');
      var def = first ? first.getAttribute('data-oi-tab') : 'futures';
      card._oiState = { activeTab: def, hidden: {} };
    }
    return card._oiState;
  }

  function renderTab(card) {
    var st = getState(card);
    var D = window.OI_TS_DATA;
    if (!D || D.error || !D.dates || !D.dates.length) {
      var canvas = card.querySelector('.oi-canvas');
      if (canvas) {
        var ctx = canvas.getContext('2d');
        ctx.clearRect(0,0,canvas.width,canvas.height);
      }
      return;
    }
    var canvas2 = card.querySelector('.oi-canvas');
    if (!canvas2) return;
    var series = getSeriesFor(st.activeTab);
    drawChart(canvas2, series, D.dates, st.hidden);

    var leg = card.querySelector('.oi-legend');
    if (leg) {
      var lh = '';
      for (var i = 0; i < series.length; i++) {
        var s = series[i];
        var hidden = st.hidden[s.label] ? ' oi-hidden' : '';
        lh += '<span class="oi-legend-item' + hidden + '" data-oi-label="' + s.label + '">';
        lh += '<span class="oi-swatch" style="background:' + s.color + '"></span>';
        lh += s.label;
        if (s.data && s.data.length) {
          var lastV = s.data[s.data.length - 1];
          lh += ' <span style="opacity:.6">(' + fmtK(lastV) + ')</span>';
        }
        lh += '</span>';
      }
      leg.innerHTML = lh;
    }

    var meta = card.querySelector('.oi-meta');
    if (meta) {
      if (D.dates.length >= 2) {
        meta.innerHTML = fmtDateLabel(D.dates[0]) + ' 〜 ' + fmtDateLabel(D.dates[D.dates.length - 1]) + ' (' + D.dates.length + '営業日)';
      } else {
        meta.innerHTML = '蓄積中 (' + D.dates.length + '日)';
      }
    }
  }

  function setActiveTab(card, tab) {
    var st = getState(card);
    st.activeTab = tab;
    st.hidden = {};
    var btns = card.querySelectorAll('.oi-tab');
    for (var i = 0; i < btns.length; i++) {
      if (btns[i].getAttribute('data-oi-tab') === tab) btns[i].classList.add('oi-tab-active');
      else btns[i].classList.remove('oi-tab-active');
    }
    renderTab(card);
  }

  function initChartCard(card) {
    getState(card);  // initialise per-card state
    var tabs = card.querySelector('.oi-tabs');
    if (tabs) {
      tabs.addEventListener('click', function(ev) {
        var t = ev.target;
        if (t && t.classList && t.classList.contains('oi-tab')) {
          ev.stopPropagation();  // don't bubble to grid (would close card)
          var tab = t.getAttribute('data-oi-tab');
          if (tab) setActiveTab(card, tab);
        }
      });
    }
    var leg = card.querySelector('.oi-legend');
    if (leg) {
      leg.addEventListener('click', function(ev) {
        var t = ev.target;
        while (t && !t.classList.contains('oi-legend-item')) t = t.parentElement;
        if (!t) return;
        ev.stopPropagation();
        var label = t.getAttribute('data-oi-label');
        if (!label) return;
        var st = getState(card);
        st.hidden[label] = !st.hidden[label];
        renderTab(card);
      });
    }
    setTimeout(function() { renderTab(card); }, 0);
    window.addEventListener('resize', function() { renderTab(card); });
  }

  // Both the futures 建玉推移 card and the option OP建玉推移 card use the same
  // generic chart logic; register the init hook under both card ids.
  window.init_oi_timeseries = initChartCard;
  window.init_op_oi_timeseries = initChartCard;
})();
"""

# ============================================================
# 週次手口推移カード (weekly participant futures OI trend)
# ============================================================
WEEKLY_TREND_CSS = r"""
.wt-tabs{display:flex;gap:0;margin:8px 0;border-bottom:1px solid var(--border)}
.wt-tab{flex:1;padding:8px 4px;background:transparent;color:var(--sub);border:none;border-bottom:2px solid transparent;font-family:'Noto Sans JP',sans-serif;font-size:11px;cursor:pointer}
.wt-tab.wt-tab-active{color:var(--accent);border-bottom-color:var(--accent)}
.wt-title{font-size:10px;color:var(--sub);margin:6px 2px;opacity:.8}
.wt-scroll{overflow-x:auto;border:1px solid var(--border);border-radius:10px;-webkit-overflow-scrolling:touch}
.wt-table{border-collapse:separate;border-spacing:0;width:100%;font-size:12px;font-family:'Noto Sans JP',sans-serif}
.wt-table thead th{position:sticky;top:0;background:#1d2230;color:var(--sub);font-weight:500;text-align:right;padding:8px 10px;border-bottom:1px solid #2d3344;white-space:nowrap;font-size:11px}
.wt-table thead th:first-child{text-align:left}
.wt-table thead th .wt-sub{display:block;font-size:9px;color:#5a6276;font-weight:400;margin-top:2px}
.wt-table tbody tr.wt-cat td{background:#1d2230;color:#e9ecf1;font-weight:600;font-size:11px;padding:6px 10px;border-top:1px solid #2d3344;border-bottom:1px solid #2d3344}
.wt-table tbody tr.wt-cat td .wt-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;vertical-align:middle}
.wt-table tbody td{padding:6px 10px;border-bottom:1px solid var(--border);text-align:right;font-family:'DM Mono',ui-monospace,monospace;font-size:12px;white-space:nowrap}
.wt-table tbody td.wt-broker{text-align:left;font-family:'Noto Sans JP',sans-serif;color:#e9ecf1;white-space:nowrap;position:sticky;left:0;background:var(--panel);z-index:1;border-right:1px solid var(--border)}
.wt-table tbody td.wt-oi{font-weight:600;background:#1d2230;border-left:1px solid #2d3344}
.wt-table tbody td.wt-dim{color:#5a6276}
.wt-cell-pos{background:rgba(34,197,94,.18);color:#4ade80}
.wt-cell-pos-strong{background:rgba(34,197,94,.55);color:#fff;font-weight:600}
.wt-cell-neg{background:rgba(239,68,68,.18);color:#f87171}
.wt-cell-neg-strong{background:rgba(239,68,68,.55);color:#fff;font-weight:600}
.wt-dot-macro{background:#f59e0b}.wt-dot-longterm{background:#3b82f6}.wt-dot-cta{background:#ec4899}
.wt-dot-arb{background:#14b8a6}.wt-dot-domins{background:#10b981}.wt-dot-domret{background:#84cc16}.wt-dot-other{background:#6b7280}
"""

WEEKLY_TREND_JS = r"""
(function(){
  if (typeof window.WT_DATA === 'undefined') window.WT_DATA = null;
  var CAT_DOTS = {
    'グローバルマクロ':'macro','長期投資志向':'longterm','トレンドフォロー（CTA）':'cta',
    'アービトラージ（裁定取引）':'arb','国内機関投資家':'domins',
    '国内個人投資家（ネットトレーダー）':'domret','-':'other'
  };
  var CAT_LABELS = {
    'グローバルマクロ':'グローバルマクロ','長期投資志向':'長期投資志向',
    'トレンドフォロー（CTA）':'トレンドフォロー（CTA）','アービトラージ（裁定取引）':'アービトラージ（裁定取引）',
    '国内機関投資家':'国内機関投資家','国内個人投資家（ネットトレーダー）':'国内個人投資家','-':'ー（分類外）'
  };
  var CAT_ORDER = ['グローバルマクロ','長期投資志向','トレンドフォロー（CTA）','アービトラージ（裁定取引）','国内機関投資家','国内個人投資家（ネットトレーダー）','-'];
  var SECTION_LABELS = { 'n225_large':'日経225先物', 'n225_mini':'日経225mini', 'topix':'TOPIX先物' };

  function fmt(n, signed) {
    if (n === null || n === undefined) return '';
    if (n === 0) return '0';
    var abs = Math.abs(n);
    var sign = n < 0 ? '-' : (signed ? '+' : '');
    var s;
    if (abs >= 10000) s = (abs / 10000).toFixed(abs >= 100000 ? 0 : 1) + '万';
    else s = Math.round(abs).toString();
    return sign + s;
  }
  function fmtDate(s) {
    if (!s || s.length !== 8) return s || '';
    return s.substring(4,6) + '/' + s.substring(6,8);
  }
  function cellClass(v, maxAbs) {
    if (v === null || v === undefined || v === 0) return 'wt-dim';
    var ratio = Math.min(1, Math.abs(v) / Math.max(maxAbs, 1));
    var strong = ratio >= 0.5;
    if (v > 0) return strong ? 'wt-cell-pos-strong' : 'wt-cell-pos';
    return strong ? 'wt-cell-neg-strong' : 'wt-cell-neg';
  }

  function getState(card) {
    if (!card._wtState) {
      var first = card.querySelector('.wt-tab');
      var def = first ? first.getAttribute('data-wt-tab') : 'n225_large';
      card._wtState = { tab: def };
    }
    return card._wtState;
  }

  function renderTable(card) {
    var st = getState(card);
    var content = card.querySelector('.wt-content');
    if (!content) return;
    var D = window.WT_DATA;
    if (!D || D.error || !D.sections) {
      content.innerHTML = '<div class="oi-empty">週次データなし — data/weekly_trend.json 未生成、または週次ファイル未配置</div>';
      return;
    }
    var rows = D.sections[st.tab] || [];
    var weeks = D.weeks || [];
    var lim = (D.limgetsu || {})[st.tab] || '';

    var maxAbs = 1;
    for (var i = 0; i < rows.length; i++) {
      var w = rows[i].wow || [];
      for (var j = 0; j < w.length; j++) {
        if (w[j] !== null && Math.abs(w[j]) > maxAbs) maxAbs = Math.abs(w[j]);
      }
    }
    var byCat = {};
    for (var k = 0; k < rows.length; k++) {
      var c = rows[k].category || '-';
      if (!byCat[c]) byCat[c] = [];
      byCat[c].push(rows[k]);
    }
    var h = '';
    h += '<div class="wt-title"><b>' + (SECTION_LABELS[st.tab] || '') + '</b> · ' + lim + ' · 前週比増減・売り越しはマイナス</div>';
    h += '<div class="wt-scroll"><table class="wt-table"><thead><tr>';
    h += '<th>証券会社</th>';
    for (var wk = 0; wk < weeks.length; wk++) {
      h += '<th>' + fmtDate(weeks[wk]) + '<span class="wt-sub">' + (wk === 0 ? '基準' : '前週比') + '</span></th>';
    }
    if (weeks.length > 0) {
      h += '<th>' + fmtDate(weeks[weeks.length - 1]) + '<span class="wt-sub">建玉残高</span></th>';
    }
    h += '</tr></thead><tbody>';
    var colspan = 2 + weeks.length;
    for (var ci = 0; ci < CAT_ORDER.length; ci++) {
      var cat = CAT_ORDER[ci];
      var catRows = byCat[cat];
      if (!catRows || !catRows.length) continue;
      var dotClass = CAT_DOTS[cat] || 'other';
      h += '<tr class="wt-cat"><td colspan="' + colspan + '"><span class="wt-dot wt-dot-' + dotClass + '"></span>' + CAT_LABELS[cat] + ' (' + catRows.length + ')</td></tr>';
      for (var ri = 0; ri < catRows.length; ri++) {
        var row = catRows[ri];
        h += '<tr><td class="wt-broker">' + row.broker + '</td>';
        var wow = row.wow || [];
        for (var wi = 0; wi < wow.length; wi++) {
          var v = wow[wi];
          if (v === null || v === undefined) h += '<td class="wt-dim">—</td>';
          else h += '<td class="' + cellClass(v, maxAbs) + '">' + fmt(v, true) + '</td>';
        }
        h += '<td class="wt-oi">' + fmt(row.oi_current) + '</td></tr>';
      }
    }
    h += '</tbody></table></div>';
    content.innerHTML = h;
  }

  function setTab(card, tab) {
    getState(card).tab = tab;
    var btns = card.querySelectorAll('.wt-tab');
    for (var i = 0; i < btns.length; i++) {
      if (btns[i].getAttribute('data-wt-tab') === tab) btns[i].classList.add('wt-tab-active');
      else btns[i].classList.remove('wt-tab-active');
    }
    renderTable(card);
  }

  window.init_weekly_trend = function(card) {
    getState(card);
    var tabs = card.querySelector('.wt-tabs');
    if (tabs) {
      tabs.addEventListener('click', function(ev) {
        var t = ev.target;
        if (t && t.classList && t.classList.contains('wt-tab')) {
          ev.stopPropagation();
          var tab = t.getAttribute('data-wt-tab');
          if (tab) setTab(card, tab);
        }
      });
    }
    setTimeout(function() { renderTable(card); }, 0);
  };
})();
"""


# ============================================================
# build_dashboard_html and preview/detail functions are below.
# For brevity, the unchanged functions (build_dashboard_html,
# all _preview_* functions, and most _detail_* functions) are
# identical to the original render.py. Only the participants
# section has been modified with strike matrix support.
# ============================================================

# The complete set of functions follows. Only _val_cell,
# _strike_matrix_js (new), and _detail_participants_js (modified)
# differ from the original.

# ============================================================
# 建玉推移カード (OI timeseries) — 補助関数
# ============================================================

def _load_oi_timeseries(data_dir='data'):
    """Try to load data/oi_timeseries.json. Returns dict or None."""
    fp = os.path.join(data_dir, 'oi_timeseries.json')
    if not os.path.exists(fp):
        return None
    try:
        with open(fp, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print('[render.py] WARN: failed to load %s: %s' % (fp, e))
        return None


def _preview_oi_timeseries(oi_ts):
    """Futures 建玉推移 card preview — period, latest Nikkei, futures OI deltas."""
    if not oi_ts or oi_ts.get('error'):
        return '<span class="mm-label">データなし</span>'
    n = oi_ts.get('n_dates', 0)
    if n < 1:
        return '<span class="mm-label">蓄積中</span>'

    h = '<div class="mini-metrics">'
    h += '<div class="mini-metric"><div class="mm-label">期間</div><div class="mm-value">%d日</div></div>' % n

    # Latest Nikkei (price line)
    nk = oi_ts.get('nikkei')
    if nk and isinstance(nk, list):
        last_nk = next((v for v in reversed(nk) if v is not None), None)
        if last_nk is not None:
            h += '<div class="mini-metric"><div class="mm-label">日経</div><div class="mm-value">%s</div></div>' % fnum(last_nk)

    # Futures 5-day delta for nk225_large
    fut_large = (oi_ts.get('futures', {}).get('nk225_large') or {}).get('total', [])
    if len(fut_large) >= 6:
        delta = fut_large[-1] - fut_large[-6]
        cls = 'positive' if delta > 0 else 'negative' if delta < 0 else ''
        h += '<div class="mini-metric"><div class="mm-label">ラージ5日</div><div class="mm-value %s">%s</div></div>' % (cls, fnum(delta, plus=True))
    elif len(fut_large) >= 2:
        delta = fut_large[-1] - fut_large[0]
        cls = 'positive' if delta > 0 else 'negative' if delta < 0 else ''
        h += '<div class="mini-metric"><div class="mm-label">ラージ期間</div><div class="mm-value %s">%s</div></div>' % (cls, fnum(delta, plus=True))

    # TOPIX period delta
    topix = (oi_ts.get('futures', {}).get('topix') or {}).get('total', [])
    if len(topix) >= 2:
        delta = topix[-1] - topix[0]
        cls = 'positive' if delta > 0 else 'negative' if delta < 0 else ''
        h += '<div class="mini-metric"><div class="mm-label">TOPIX期間</div><div class="mm-value %s">%s</div></div>' % (cls, fnum(delta, plus=True))

    h += '</div>'
    return h


def _preview_op_oi_timeseries(oi_ts):
    """Option OP建玉推移 card preview — target expiry, PCR, Top P / Top C."""
    if not oi_ts or oi_ts.get('error'):
        return '<span class="mm-label">データなし</span>'
    n = oi_ts.get('n_dates', 0)
    if n < 1:
        return '<span class="mm-label">蓄積中</span>'

    h = '<div class="mini-metrics">'
    h += '<div class="mini-metric"><div class="mm-label">期間</div><div class="mm-value">%d日</div></div>' % n

    top_exp = (oi_ts.get('options') or {}).get('top_expiry')
    if top_exp and len(top_exp) == 4:
        h += '<div class="mini-metric"><div class="mm-label">対象限月</div><div class="mm-value">%s月限</div></div>' % top_exp[2:]

    agg = (oi_ts.get('options') or {}).get('aggregate', {}) or {}
    if top_exp and top_exp in agg:
        grp = agg[top_exp]
        p = (grp.get('put_total') or [0])[-1]
        c = (grp.get('call_total') or [0])[-1]
        if c > 0:
            short_lab = top_exp[2:] + '月' if len(top_exp) == 4 else top_exp
            h += '<div class="mini-metric"><div class="mm-label">%sPCR</div><div class="mm-value">%.2f</div></div>' % (short_lab, p / c)

    top_p = (oi_ts.get('options') or {}).get('top_puts', []) or []
    top_c = (oi_ts.get('options') or {}).get('top_calls', []) or []
    if top_p:
        h += '<div class="mini-metric"><div class="mm-label">Top P</div><div class="mm-value">%s</div></div>' % esc(top_p[0].get('short_label', ''))
    if top_c:
        h += '<div class="mini-metric"><div class="mm-label">Top C</div><div class="mm-value">%s</div></div>' % esc(top_c[0].get('short_label', ''))

    h += '</div>'
    return h


def _detail_oi_timeseries_js(oi_ts):
    """Futures 建玉推移 card — tabs: 日経先物 (default) + 先物OI.
    Chart drawn by init_oi_timeseries() (OI_CHART_JS).
    """
    if not oi_ts or oi_ts.get('error'):
        return "var h='';h+='<div class=\"oi-empty\">建玉推移データなし — pipeline が `data/oi_timeseries.json` を未生成、または `*open_interest.xlsx` の蓄積が不足</div>';return h;"
    js = "var h='';"
    js += "h+='<div class=\"oi-tabs\">';"
    js += "h+='<button class=\"oi-tab oi-tab-active\" data-oi-tab=\"futures\" type=\"button\">先物OI</button>';"
    js += "h+='</div>';"
    js += "h+='<div class=\"oi-chart-wrap\"><canvas class=\"oi-canvas\"></canvas></div>';"
    js += "h+='<div class=\"oi-meta\"></div>';"
    js += "h+='<div class=\"oi-legend\"></div>';"
    js += "return h;"
    return js


def _detail_op_oi_timeseries_js(oi_ts):
    """Option OP建玉推移 card — tabs: OP集計 (default) + Pストライク + Cストライク.
    Chart drawn by init_op_oi_timeseries() (same generic logic, OI_CHART_JS).
    """
    if not oi_ts or oi_ts.get('error'):
        return "var h='';h+='<div class=\"oi-empty\">OP建玉推移データなし — `*open_interest.xlsx` の蓄積が不足</div>';return h;"
    js = "var h='';"
    js += "h+='<div class=\"oi-tabs\">';"
    js += "h+='<button class=\"oi-tab oi-tab-active\" data-oi-tab=\"options_agg\" type=\"button\">OP集計</button>';"
    js += "h+='<button class=\"oi-tab\" data-oi-tab=\"top_puts\" type=\"button\">Pストライク</button>';"
    js += "h+='<button class=\"oi-tab\" data-oi-tab=\"top_calls\" type=\"button\">Cストライク</button>';"
    js += "h+='</div>';"
    js += "h+='<div class=\"oi-chart-wrap\"><canvas class=\"oi-canvas\"></canvas></div>';"
    js += "h+='<div class=\"oi-meta\"></div>';"
    js += "h+='<div class=\"oi-legend\"></div>';"
    js += "return h;"
    return js


def _load_weekly_trend(data_dir='data'):
    """Load data/weekly_trend.json (produced by extract_weekly_trend.py)."""
    fp = os.path.join(data_dir, 'weekly_trend.json')
    if not os.path.exists(fp):
        return None
    try:
        with open(fp, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print('[render.py] WARN: failed to load %s: %s' % (fp, e))
        return None


def _preview_weekly_trend(wt):
    if not wt or wt.get('error'):
        return '<span class="mm-label">データなし</span>'
    weeks = wt.get('weeks', []) or []
    if not weeks:
        return '<span class="mm-label">蓄積中</span>'
    h = '<div class="mini-metrics">'
    h += '<div class="mini-metric"><div class="mm-label">最終データ</div><div class="mm-value">%s</div></div>' % (
        ('%s/%s' % (weeks[-1][4:6], weeks[-1][6:8])) if len(weeks[-1]) == 8 else weeks[-1])
    h += '<div class="mini-metric"><div class="mm-label">週数</div><div class="mm-value">%d</div></div>' % len(weeks)
    # Biggest WoW mover (latest week) in n225_large
    rows = (wt.get('sections', {}) or {}).get('n225_large', []) or []
    best = None
    for r in rows:
        wow = r.get('wow') or []
        last = wow[-1] if wow else None
        if last is not None and (best is None or abs(last) > abs(best[1])):
            best = (r.get('broker', ''), last)
    if best:
        cls = 'positive' if best[1] > 0 else 'negative' if best[1] < 0 else ''
        h += '<div class="mini-metric"><div class="mm-label">最大変化(ラージ)</div><div class="mm-value %s">%s %s</div></div>' % (
            cls, esc(best[0][:8]), fnum(best[1], plus=True))
    h += '</div>'
    return h


def _detail_weekly_trend_js(wt):
    """OP/futures weekly participant trend card — tabs by market.
    Rendered by init_weekly_trend() (WEEKLY_TREND_JS)."""
    if not wt or wt.get('error'):
        return "var h='';h+='<div class=\"oi-empty\">週次手口データなし — `*_indexfut_oi_by_tp.xlsx` を data/ に蓄積し、pipeline で weekly_trend.json を生成してください</div>';return h;"
    js = "var h='';"
    js += "h+='<div class=\"wt-tabs\">';"
    js += "h+='<button class=\"wt-tab wt-tab-active\" data-wt-tab=\"n225_large\" type=\"button\">日経225先物</button>';"
    js += "h+='<button class=\"wt-tab\" data-wt-tab=\"n225_mini\" type=\"button\">日経225mini</button>';"
    js += "h+='<button class=\"wt-tab\" data-wt-tab=\"topix\" type=\"button\">TOPIX先物</button>';"
    js += "h+='</div>';"
    js += "h+='<div class=\"wt-content\"></div>';"
    js += "return h;"
    return js


def build_dashboard_html(data, oi_ts=None, wt=None):
    meta = data['metadata']
    s01 = data.get('s01', {})
    s02 = data.get('s02', {})
    s03 = data.get('s03', {})
    s04 = data.get('s04', {})
    s05 = data.get('s05', [])
    s06 = data.get('s06', {})
    s07 = data.get('s07', [])
    s09 = data.get('s09', {})
    s11 = data.get('s11', {})
    atm = meta.get('atm', 0)
    nikkei = s01.get('nikkei_close', 0)
    vi = s01.get('vi', 0)
    ind = data.get('indicators', {})

    h = '<!DOCTYPE html>\n<html lang="ja">\n<head>\n'
    h += '<meta charset="UTF-8">\n'
    h += '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
    h += '<title>JPX Market Analysis %s</title>\n' % esc(meta.get('date_formatted', ''))
    h += '<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700&family=Noto+Sans+JP:wght@400;500;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">\n'
    h += '<style>\n%s\n%s\n%s\n</style>\n' % (DASHBOARD_CSS, OI_CHART_CSS, WEEKLY_TREND_CSS)
    h += '</head>\n<body>\n'

    h += '<div class="topbar">\n  <span class="logo">JPX Dashboard</span>\n  <nav>\n'
    h += '    <a href="index.html">ダッシュボード</a>\n    <a href="pnl_simulator.html">P&Lシミュレーター</a>\n    <a href="weekly_trend.html">週次推移</a>\n    <a href="archive.html">アーカイブ</a>\n  </nav>\n</div>\n'

    h += '<div class="hero">\n  <h1>%s</h1>\n  <div class="sub">%s / SQまで%d営業日</div>\n</div>\n' % (esc(meta.get('date_formatted', '')), esc(meta.get('sq_label', '')), meta.get('days_to_sq', 0))

    h += '<div class="kpi-strip">\n'
    vi_cls = 'down' if vi and vi > 30 else ''
    h += '  <div class="kpi"><div class="label">VI</div><div class="value %s">%s</div></div>\n' % (vi_cls, vi if vi else '-')
    h += '  <div class="kpi"><div class="label">ATM</div><div class="value">%s</div></div>\n' % (fnum(atm) if atm else '-')
    mp = ind.get('max_pain')
    if mp:
        h += '  <div class="kpi"><div class="label">Max Pain</div><div class="value">%s</div></div>\n' % fnum(mp)
    dist = s06.get('distribution', [])
    if dist:
        max_p = max(dist, key=lambda d: d['put_oi'])
        max_c = max(dist, key=lambda d: d['call_oi'])
        if max_p['put_oi'] > 0:
            h += '  <div class="kpi"><div class="label">P壁</div><div class="value" style="color:var(--put)">%s</div></div>\n' % fnum(max_p['strike'])
        if max_c['call_oi'] > 0:
            h += '  <div class="kpi"><div class="label">C壁</div><div class="value" style="color:var(--call)">%s</div></div>\n' % fnum(max_c['strike'])
    h += '</div>\n'

    h += '<div style="max-width:1200px;margin:0 auto;padding:0 16px 10px;display:flex;gap:10px;flex-wrap:wrap">\n'
    h += '  <div style="flex:1;min-width:300px">\n'
    h += '    <div style="font-size:11px;color:var(--sub);text-align:center;padding:4px 0;font-family:Outfit">日足</div>\n'
    h += '    <div style="background:var(--card);border:1px solid var(--border);border-radius:10px;overflow:hidden;height:310px">\n'
    h += '      <iframe src="https://s.tradingview.com/widgetembed/?symbol=OSE%3ANK2251!&interval=D&theme=dark&style=1&hide_top_toolbar=1&hide_legend=0&save_image=0&hide_volume=0&locale=ja&studies=BB%40tv-basicstudies%1F25" style="width:100%;height:100%;border:none"></iframe>\n'
    h += '    </div>\n  </div>\n'
    h += '  <div style="flex:1;min-width:300px">\n'
    h += '    <div style="font-size:11px;color:var(--sub);text-align:center;padding:4px 0;font-family:Outfit">15分足</div>\n'
    h += '    <div style="background:var(--card);border:1px solid var(--border);border-radius:10px;overflow:hidden;height:310px">\n'
    h += '      <iframe src="https://s.tradingview.com/widgetembed/?symbol=OSE%3ANK2251!&interval=15&theme=dark&style=1&hide_top_toolbar=1&hide_legend=0&save_image=0&hide_volume=0&locale=ja&studies=BB%40tv-basicstudies%1F25" style="width:100%;height:100%;border:none"></iframe>\n'
    h += '    </div>\n  </div>\n</div>\n'

    h += '<div class="mobile-nav">\n  <a href="index.html">ダッシュボード</a>\n  <a href="pnl_simulator.html">P&L</a>\n  <a href="weekly_trend.html">週次</a>\n  <a href="archive.html">アーカイブ</a>\n</div>\n'

    # Resolve data-vintage badges
    def _short_date(yyyymmdd):
        s = str(yyyymmdd or '')
        if len(s) != 8:
            return ''
        return '%d/%d' % (int(s[4:6]), int(s[6:8]))

    daily_badge = _short_date(meta.get('date'))
    # Weekly participant snapshot date is in the weekly filename (files_found)
    ff = meta.get('files_found', {}) or {}
    import re as _re
    weekly_date = ''
    for key in ('fut_participants', 'op_participants'):
        m = _re.search(r'(\d{8})', str(ff.get(key, '')))
        if m:
            weekly_date = _short_date(m.group(1))
            break
    weekly_badge = (weekly_date + ' 週次') if weekly_date else '週次'

    h += '<div class="grid">\n'
    # Cards organized into domain groups. Each tuple now carries a date badge
    # (text, is_weekly) so users can see at a glance which data vintage a card
    # reflects (daily 5/28 vs weekly 5/22).
    DB = (daily_badge, False)
    WB = (weekly_badge, True)
    card_groups = [
        ('先物', [
            ('futures', '📈', '先物建玉増減', _preview_futures(s02), _detail_futures_js(s02), DB),
            ('oi_timeseries', '📈', '建玉推移', _preview_oi_timeseries(oi_ts), _detail_oi_timeseries_js(oi_ts), DB),
        ]),
        ('オプション', [
            ('opval', '💰', 'OP取引代金', _preview_opval(s03), _detail_opval_js(s03), DB),
            ('oichg', '📊', 'OP建玉増減', _preview_oichg(s04), _detail_oichg_js(s04), DB),
            ('op_oi_timeseries', '📉', 'OP建玉推移', _preview_op_oi_timeseries(oi_ts), _detail_op_oi_timeseries_js(oi_ts), DB),
            ('important', '⚡', 'OP重要建玉変化', _preview_important(s05), _detail_important_js(s05), DB),
            ('dist', '🦋', 'OP建玉分布', _preview_dist(s06), _detail_dist_js(s06, ind), DB),
            ('strategy', '🎲', 'OP戦略マップ', _preview_strategy(s11), _detail_strategy_js(s11, atm), DB),
        ]),
        ('参加者・手口', [
            ('participants', '🌏', '参加者別建玉分析', _preview_participants(s09), _detail_participants_js(s09), WB),
            ('weekly_trend', '📅', '週次手口推移', _preview_weekly_trend(wt), _detail_weekly_trend_js(wt), WB),
            ('jnet', '🏛', '大口手口（J-NET）', _preview_jnet(s07), _detail_jnet_js(s07), DB),
        ]),
        ('総合', [
            ('assess', '🎯', '総合評価', _preview_assess(s01, ind), _detail_assess_js(data), DB),
            ('gemini', '🤖', 'AI予想', _preview_gemini(data), _detail_gemini_js(data), DB),
        ]),
    ]
    # Flat list for the JS function registration below
    cards = []
    for _gtitle, _gcards in card_groups:
        cards.extend([(c[0], c[1], c[2], c[3], c[4]) for c in _gcards])

    for gtitle, gcards in card_groups:
        h += '<div class="section-hdr"><span class="section-title">%s</span><span class="section-line"></span></div>\n' % esc(gtitle)
        for card_id, icon, title, preview_html, detail_js, badge in gcards:
            btext, is_weekly = badge
            badge_cls = 'date-badge weekly' if is_weekly else 'date-badge'
            badge_html = ('<span class="%s">%s</span>' % (badge_cls, esc(btext))) if btext else ''
            h += '<div class="card" data-card="%s">\n  <div class="card-hdr">\n    <span class="icon">%s</span>\n    <span class="title">%s</span>\n    %s\n    <span class="arrow">▶</span>\n  </div>\n' % (card_id, icon, esc(title), badge_html)
            h += '  <div class="card-preview">%s</div>\n  <div class="card-detail"></div>\n</div>\n' % preview_html
    h += '</div>\n'

    h += '<div class="footer">\n  <a href="pnl_simulator.html">P&Lシミュレーター</a>\n  <a href="weekly_trend.html">週次推移</a>\n  <a href="archive.html">アーカイブ一覧</a>\n  <span>Generated by JPX Analysis Pipeline</span>\n</div>\n'

    h += '<script>\n'
    # Strip the heavy '_snapshots' raw history before inlining — the dashboard
    # chart only needs the derived display fields (dates/futures/options).
    oi_ts_display = None
    if oi_ts:
        oi_ts_display = {k: v for k, v in oi_ts.items() if k != '_snapshots'}
    h += 'window.OI_TS_DATA = ' + json.dumps(oi_ts_display or {}, ensure_ascii=False) + ';\n'
    h += 'window.WT_DATA = ' + json.dumps(wt or {}, ensure_ascii=False) + ';\n'
    h += OI_CHART_JS
    h += WEEKLY_TREND_JS
    for card_id, _, _, _, detail_js in cards:
        h += 'function b_%s(){' % card_id
        h += detail_js
        h += '}\n'
    h += DASHBOARD_JS
    h += '</script>\n</body>\n</html>'
    return h


# --- Preview builders (unchanged) ---

def _preview_futures(s02):
    if 'error' in s02:
        return '<span class="mm-label">データなし</span>'
    h = '<div class="mini-metrics">'
    for key, label in [('nk225_large', 'ラージ'), ('nk225_mini', 'mini'), ('topix', 'TOPIX')]:
        sec = s02.get(key, {})
        chg = sec.get('total_change', 0)
        cls = 'positive' if chg > 0 else 'negative' if chg < 0 else ''
        h += '<div class="mini-metric"><div class="mm-label">%s</div><div class="mm-value %s">%s</div></div>' % (label, cls, fnum(chg, plus=True))
    h += '</div>'
    return h

def _preview_opval(s03):
    if 'error' in s03:
        return '<span class="mm-label">データなし</span>'
    lg = s03.get('large', {})
    h = '<div class="mini-metrics">'
    h += '<div class="mini-metric"><div class="mm-label">P代金</div><div class="mm-value">%s</div></div>' % fnum_short(lg.get('put_value'))
    h += '<div class="mini-metric"><div class="mm-label">C代金</div><div class="mm-value">%s</div></div>' % fnum_short(lg.get('call_value'))
    h += '<div class="mini-metric"><div class="mm-label">J-NET率</div><div class="mm-value">%s</div></div>' % fpct(lg.get('jnet_ratio'))
    h += '</div>'
    return h

def _preview_oichg(s04):
    if 'error' in s04:
        return '<span class="mm-label">データなし</span>'
    lg = s04.get('large', {})
    pc = lg.get('put_total_change', 0)
    cc = lg.get('call_total_change', 0)
    h = '<div class="mini-metrics">'
    h += '<div class="mini-metric"><div class="mm-label">P合計</div><div class="mm-value %s">%s</div></div>' % (sign_class(pc), fnum(pc, plus=True))
    h += '<div class="mini-metric"><div class="mm-label">C合計</div><div class="mm-value %s">%s</div></div>' % (sign_class(cc), fnum(cc, plus=True))
    h += '</div>'
    return h

def _preview_important(s05):
    if not s05:
        return '<span class="mm-label">該当なし</span>'
    h = ''
    for c in s05[:4]:
        cls = 'tag-put' if c['type'] == 'P' else 'tag-call'
        h += '<span class="tag %s">%s%s %s</span>' % (cls, c['type'], fnum(c['strike']), fnum(c['change'], plus=True))
    if len(s05) > 4:
        expiries = set(c.get('expiry', '') for c in s05)
        h += '<span class="tag">他%d件 (%d限月)</span>' % (len(s05) - 4, len(expiries))
    return h

def _preview_dist(s06):
    if 'distribution' not in s06:
        return '<span class="mm-label">データなし</span>'
    dist = s06['distribution']
    max_p = max(dist, key=lambda d: d['put_oi']) if dist else None
    max_c = max(dist, key=lambda d: d['call_oi']) if dist else None
    h = '<div class="mini-metrics">'
    if max_p:
        h += '<div class="mini-metric"><div class="mm-label">P壁</div><div class="mm-value" style="color:var(--put)">%s (%s)</div></div>' % (fnum(max_p['strike']), fnum(max_p['put_oi']))
    h += '<div class="mini-metric"><div class="mm-label">ATM</div><div class="mm-value" style="color:var(--yellow)">%s</div></div>' % fnum(s06.get('atm'))
    if max_c:
        h += '<div class="mini-metric"><div class="mm-label">C壁</div><div class="mm-value" style="color:var(--call)">%s (%s)</div></div>' % (fnum(max_c['strike']), fnum(max_c['call_oi']))
    h += '</div>'
    return h

def _preview_jnet(s07):
    if not s07:
        return '<span class="mm-label">該当なし</span>'
    h = ''
    seen = set()
    for t in s07[:5]:
        if t['participant'] not in seen:
            cat_cls = {'us': 'tag-us', 'eu': 'tag-eu', 'hf': 'tag-hf', 'domestic': 'tag-dom'}.get(t['category'], '')
            h += '<span class="tag %s">%s %s枚</span>' % (cat_cls, esc(t['participant'][:8]), fnum(t['volume']))
            seen.add(t['participant'])
    return h

def _preview_assess(s01, ind=None):
    ind = ind or {}
    h = '<div class="mini-metrics">'
    r1w = s01.get('range_1w', {})
    if r1w:
        h += '<div class="mini-metric"><div class="mm-label">1週予想</div><div class="mm-value" style="color:var(--yellow)">%s〜%s</div></div>' % (fnum(r1w.get('low')), fnum(r1w.get('high')))
    pcr = ind.get('pcr_volume')
    if pcr is not None:
        pcr_cls = 'negative' if pcr > 1.0 else 'positive' if pcr < 0.7 else ''
        h += '<div class="mini-metric"><div class="mm-label">PCR</div><div class="mm-value %s">%.2f</div></div>' % (pcr_cls, pcr)
    mp = ind.get('max_pain')
    if mp:
        h += '<div class="mini-metric"><div class="mm-label">MaxPain</div><div class="mm-value">%s</div></div>' % fnum(mp)
    h += '</div>'
    return h

def _preview_participants(s09):
    if 'error' in s09:
        return '<span class="mm-label">週次データなし</span>'
    sm = s09.get('strike_matrix', {})
    strikes = sm.get('strikes', [])
    h = '<div class="mini-metrics">'
    if strikes:
        h += '<div class="mini-metric"><div class="mm-label">対象行使価格</div><div class="mm-value">%s〜%s</div></div>' % (fnum(strikes[0]), fnum(strikes[-1]))
    if s09.get('source') == 'cache':
        h += '<div class="mini-metric"><div class="mm-label" style="color:var(--yellow)">%s時点</div></div>' % esc(s09.get('data_date', '?')[:8])
    h += '</div>'
    return h

def _preview_strategy(s11):
    otm = s11.get('otm_table', [])
    edges = s11.get('edge_scores', [])
    if not otm:
        return '<span class="mm-label">データ不足</span>'
    best_p = None
    best_c = None
    for e in edges:
        if e['type'] == 'sell-p' and (best_p is None or e['stars'] > best_p['stars']):
            best_p = e
        if e['type'] == 'sell-c' and (best_c is None or e['stars'] > best_c['stars']):
            best_c = e
    h = '<div class="mini-metrics">'
    if best_p:
        h += '<div class="mini-metric"><div class="mm-label">P売り</div><div class="mm-value" style="color:var(--put)">%s</div></div>' % ('★' * best_p['stars'])
    if best_c:
        h += '<div class="mini-metric"><div class="mm-label">C売り</div><div class="mm-value" style="color:var(--call)">%s</div></div>' % ('★' * best_c['stars'])
    h += '</div>'
    return h


# --- Detail JS builders (unchanged functions first, then modified ones) ---

def _detail_futures_js(s02):
    if 'error' in s02:
        return "var h='<div>データなし</div>';return h;"
    js = "var h='';"
    for key, label in [('nk225_large', '日経225ラージ'), ('nk225_mini', '日経225mini'), ('topix', 'TOPIX')]:
        sec = s02.get(key, {})
        chg = sec.get('total_change', 0)
        cls = 'positive' if chg > 0 else 'negative' if chg < 0 else ''
        js += "h+='<div class=\"bar-row\"><div class=\"bar-label\">%s 合計</div>';" % _js_str(label)
        js += "h+='<div class=\"bar-track\"><div class=\"bar-fill %s\" style=\"width:%dpx\"></div></div>';" % ('up' if chg > 0 else 'down', min(abs(chg) // 50 + 5, 200) if chg else 0)
        js += "h+='<div class=\"bar-val %s\">%s</div></div>';" % (cls, _js_str(fnum(chg, plus=True)))
        months = sec.get('months', [])
        if months:
            m = months[0]
            mc = m.get('change', 0)
            mcls = 'positive' if mc > 0 else 'negative' if mc < 0 else ''
            js += "h+='<div class=\"bar-row\"><div class=\"bar-label\" style=\"font-size:10px;padding-left:16px\">%s (OI: %s)</div>';" % (_js_str(m['label'][:12]), _js_str(fnum(m.get('oi'))))
            js += "h+='<div class=\"bar-track\"><div class=\"bar-fill %s\" style=\"width:%dpx\"></div></div>';" % ('up' if mc > 0 else 'down', min(abs(mc) // 50 + 3, 150) if mc else 0)
            js += "h+='<div class=\"bar-val %s\" style=\"font-size:10px\">%s</div></div>';" % (mcls, _js_str(fnum(mc, plus=True)))
    js += "return h;"
    return js

def _detail_opval_js(s03):
    if 'error' in s03:
        return "var h='<div>データなし</div>';return h;"
    js = "var h='';"
    for bk, bl in [('large', 'ラージ'), ('mini', 'ミニ')]:
        b = s03.get(bk, {})
        if not b:
            continue
        js += "h+='<h3 style=\"color:#fff;font-size:13px;margin:8px 0 4px\">%s</h3>';" % bl
        js += "h+='<table><tr><th></th><th>取引高</th><th>取引代金</th></tr>';"
        js += "h+='<tr><td style=\"color:var(--put)\">プット</td><td>%s</td><td>%s</td></tr>';" % (_js_str(fnum_short(b.get('put_volume'))), _js_str(fnum_short(b.get('put_value'))))
        js += "h+='<tr><td style=\"color:var(--call)\">コール</td><td>%s</td><td>%s</td></tr>';" % (_js_str(fnum_short(b.get('call_volume'))), _js_str(fnum_short(b.get('call_value'))))
        js += "h+='<tr><td>合計</td><td>%s</td><td>%s</td></tr>';" % (_js_str(fnum_short(b.get('total_volume'))), _js_str(fnum_short(b.get('total_value'))))
        js += "h+='<tr><td>J-NET</td><td>%s</td><td>%s (%s)</td></tr>';" % (_js_str(fnum_short(b.get('jnet_volume'))), _js_str(fnum_short(b.get('jnet_value'))), _js_str(fpct(b.get('jnet_ratio'))))
        js += "h+='</table>';"
    js += "return h;"
    return js

def _detail_oichg_js(s04):
    if 'error' in s04:
        return "var h='<div>データなし</div>';return h;"
    js = "var h='';"
    for bk, bl in [('large', 'ラージ'), ('mini', 'ミニ')]:
        b = s04.get(bk, {})
        if not b:
            continue
        pc = b.get('put_total_change', 0)
        cc = b.get('call_total_change', 0)
        js += "h+='<h3 style=\"color:#fff;font-size:13px;margin:8px 0 4px\">%s</h3>';" % bl
        js += "h+='<div class=\"bar-row\"><div class=\"bar-label\" style=\"color:var(--put)\">P合計 %s</div>';" % _js_str(fnum(pc, plus=True))
        js += "h+='<div class=\"bar-track\"><div class=\"bar-fill %s\" style=\"width:%dpx\"></div></div></div>';" % ('up' if pc > 0 else 'down', min(abs(pc) // 30 + 5, 200) if pc else 0)
        js += "h+='<div class=\"bar-row\"><div class=\"bar-label\" style=\"color:var(--call)\">C合計 %s</div>';" % _js_str(fnum(cc, plus=True))
        js += "h+='<div class=\"bar-track\"><div class=\"bar-fill %s\" style=\"width:%dpx\"></div></div></div>';" % ('up' if cc > 0 else 'down', min(abs(cc) // 30 + 5, 200) if cc else 0)
    js += "return h;"
    return js

def _detail_important_js(s05):
    if not s05:
        return "var h='<div>該当なし</div>';return h;"
    from collections import OrderedDict
    groups = OrderedDict()
    for c in s05:
        exp = c.get('expiry', '?')
        if exp not in groups:
            groups[exp] = []
        groups[exp].append(c)
    def expiry_label(exp):
        if len(exp) == 4:
            return '20%s年%s月限' % (exp[:2], exp[2:])
        return exp
    js = "var h='';"
    for exp, items in groups.items():
        label = expiry_label(exp)
        js += "h+='<div style=\"margin-top:10px;margin-bottom:4px;font-size:12px;font-weight:600;color:var(--accent)\">%s</div>';" % _js_str(label)
        js += "h+='<table><tr><th>タイプ</th><th>行使価格</th><th>建玉</th><th>前日比</th></tr>';"
        for c in items:
            chg_cls = 'positive' if c['change'] > 0 else 'negative'
            type_color = 'var(--put)' if c['type'] == 'P' else 'var(--call)'
            js += "h+='<tr><td style=\"color:%s;font-weight:600\">%s</td>';" % (type_color, c['type'])
            js += "h+='<td style=\"font-family:DM Mono\">%s</td>';" % _js_str(fnum(c['strike']))
            js += "h+='<td style=\"font-family:DM Mono\">%s</td>';" % _js_str(fnum(c.get('oi')))
            js += "h+='<td class=\"%s\" style=\"font-family:DM Mono\">%s</td></tr>';" % (chg_cls, _js_str(fnum(c['change'], plus=True)))
        js += "h+='</table>';"
    js += "return h;"
    return js

def _detail_dist_js(s06, ind=None):
    if 'distribution' not in s06:
        return "var h='<div>データなし</div>';return h;"
    ind = ind or {}
    js = "var h='';"
    js += "h+='<div style=\"font-size:11px;color:var(--sub);margin-bottom:8px\">ATM = %s</div>';" % _js_str(fnum(s06.get('atm')))

    # Top OI strikes (全行使価格)
    top_puts = s06.get('top_puts', [])
    top_calls = s06.get('top_calls', [])
    if top_puts or top_calls:
        js += "h+='<div style=\"display:flex;gap:12px;flex-wrap:wrap;margin-bottom:12px\">';"
        if top_puts:
            js += "h+='<div style=\"flex:1;min-width:140px;background:var(--card);border:1px solid rgba(248,113,113,.2);border-radius:8px;padding:8px\">';"
            js += "h+='<div style=\"font-size:10px;font-weight:600;color:var(--put);margin-bottom:4px\">PUT \\u5EFA\\u7389 TOP5</div>';"
            for i, tp in enumerate(top_puts[:5]):
                js += "h+='<div style=\"font-size:11px;font-family:DM Mono;color:var(--text)\">%d. %s <span style=\"color:var(--sub)\">%s\\u679A</span></div>';" % (i + 1, _js_str(fnum(tp['strike'])), _js_str(fnum(tp['oi'])))
            js += "h+='</div>';"
        if top_calls:
            js += "h+='<div style=\"flex:1;min-width:140px;background:var(--card);border:1px solid rgba(96,165,250,.2);border-radius:8px;padding:8px\">';"
            js += "h+='<div style=\"font-size:10px;font-weight:600;color:var(--call);margin-bottom:4px\">CALL \\u5EFA\\u7389 TOP5</div>';"
            for i, tc in enumerate(top_calls[:5]):
                js += "h+='<div style=\"font-size:11px;font-family:DM Mono;color:var(--text)\">%d. %s <span style=\"color:var(--sub)\">%s\\u679A</span></div>';" % (i + 1, _js_str(fnum(tc['strike'])), _js_str(fnum(tc['oi'])))
            js += "h+='</div>';"
        js += "h+='</div>';"

    by_expiry = s06.get('by_expiry', [])
    if by_expiry:
        for ei, exp_data in enumerate(by_expiry):
            dist = exp_data['distribution']
            max_oi = max([max(d['put_oi'], d['call_oi']) for d in dist] or [1])
            if max_oi < 10:
                continue
            js += "h+='<div style=\"margin-top:%dpx;margin-bottom:6px;font-size:12px;font-weight:600;color:var(--accent)\">%s (OI: %s)</div>';" % (14 if ei > 0 else 4, _js_str(exp_data['label']), _js_str(fnum(exp_data['total_oi'])))
            js += "h+='<div style=\"display:flex;align-items:center;gap:4px;padding:2px 0;font-size:10px;color:var(--sub);font-weight:600\">';"
            js += "h+='<div style=\"width:50px;text-align:right\">P増減</div><div style=\"width:50px;text-align:right\">P建玉</div><div style=\"width:150px;text-align:center;color:var(--put)\">← PUT</div><div style=\"width:60px;text-align:center\">行使価格</div><div style=\"width:150px;text-align:center;color:var(--call)\">CALL →</div><div style=\"width:50px\">C建玉</div><div style=\"width:50px\">C増減</div></div>';"
            for d in dist:
                if d['put_oi'] == 0 and d['call_oi'] == 0:
                    continue
                pw = int(d['put_oi'] / max_oi * 150) if max_oi else 0
                cw = int(d['call_oi'] / max_oi * 150) if max_oi else 0
                atm_style = 'background:rgba(251,191,36,.12);' if d.get('is_atm') else ''
                js += "h+='<div style=\"display:flex;align-items:center;gap:4px;padding:2px 0;font-size:11px;%s\">';" % atm_style
                pcls = 'positive' if d['put_change'] > 0 else 'negative' if d['put_change'] < 0 else ''
                js += "h+='<div style=\"width:50px;text-align:right;font-family:DM Mono;font-size:10px\" class=\"%s\">%s</div>';" % (pcls, _js_str(fnum(d['put_change'], plus=True)))
                js += "h+='<div style=\"width:50px;text-align:right;font-family:DM Mono;font-size:10px\">%s</div>';" % _js_str(fnum(d['put_oi']))
                js += "h+='<div style=\"width:150px;direction:rtl\"><div style=\"display:inline-block;height:12px;width:%dpx;background:var(--put);border-radius:2px\"></div></div>';" % pw
                strike_color = 'var(--yellow)' if d.get('is_atm') else '#fff'
                js += "h+='<div style=\"width:60px;text-align:center;font-family:DM Mono;font-weight:600;color:%s\">%s</div>';" % (strike_color, _js_str(fnum(d['strike'])))
                js += "h+='<div style=\"width:150px\"><div style=\"display:inline-block;height:12px;width:%dpx;background:var(--call);border-radius:2px\"></div></div>';" % cw
                js += "h+='<div style=\"width:50px;font-family:DM Mono;font-size:10px\">%s</div>';" % _js_str(fnum(d['call_oi']))
                ccls = 'positive' if d['call_change'] > 0 else 'negative' if d['call_change'] < 0 else ''
                js += "h+='<div style=\"width:50px;font-family:DM Mono;font-size:10px\" class=\"%s\">%s</div>';" % (ccls, _js_str(fnum(d['call_change'], plus=True)))
                js += "h+='</div>';"
    else:
        dist = s06['distribution']
        max_oi = max([max(d['put_oi'], d['call_oi']) for d in dist] or [1])
        js += "h+='<div style=\"display:flex;align-items:center;gap:4px;padding:2px 0;font-size:10px;color:var(--sub);font-weight:600\">';"
        js += "h+='<div style=\"width:50px;text-align:right\">P増減</div><div style=\"width:50px;text-align:right\">P建玉</div><div style=\"width:150px;text-align:center;color:var(--put)\">← PUT</div><div style=\"width:60px;text-align:center\">行使価格</div><div style=\"width:150px;text-align:center;color:var(--call)\">CALL →</div><div style=\"width:50px\">C建玉</div><div style=\"width:50px\">C増減</div></div>';"
        for d in dist:
            pw = int(d['put_oi'] / max_oi * 150) if max_oi else 0
            cw = int(d['call_oi'] / max_oi * 150) if max_oi else 0
            atm_style = 'background:rgba(251,191,36,.12);' if d.get('is_atm') else ''
            js += "h+='<div style=\"display:flex;align-items:center;gap:4px;padding:2px 0;font-size:11px;%s\">';" % atm_style
            pcls = 'positive' if d['put_change'] > 0 else 'negative' if d['put_change'] < 0 else ''
            js += "h+='<div style=\"width:50px;text-align:right;font-family:DM Mono;font-size:10px\" class=\"%s\">%s</div>';" % (pcls, _js_str(fnum(d['put_change'], plus=True)))
            js += "h+='<div style=\"width:50px;text-align:right;font-family:DM Mono;font-size:10px\">%s</div>';" % _js_str(fnum(d['put_oi']))
            js += "h+='<div style=\"width:150px;direction:rtl\"><div style=\"display:inline-block;height:12px;width:%dpx;background:var(--put);border-radius:2px\"></div></div>';" % pw
            strike_color = 'var(--yellow)' if d.get('is_atm') else '#fff'
            js += "h+='<div style=\"width:60px;text-align:center;font-family:DM Mono;font-weight:600;color:%s\">%s</div>';" % (strike_color, _js_str(fnum(d['strike'])))
            js += "h+='<div style=\"width:150px\"><div style=\"display:inline-block;height:12px;width:%dpx;background:var(--call);border-radius:2px\"></div></div>';" % cw
            js += "h+='<div style=\"width:50px;font-family:DM Mono;font-size:10px\">%s</div>';" % _js_str(fnum(d['call_oi']))
            ccls = 'positive' if d['call_change'] > 0 else 'negative' if d['call_change'] < 0 else ''
            js += "h+='<div style=\"width:50px;font-family:DM Mono;font-size:10px\" class=\"%s\">%s</div>';" % (ccls, _js_str(fnum(d['call_change'], plus=True)))
            js += "h+='</div>';"
    mp = ind.get('max_pain')
    if mp:
        js += "h+='<div style=\"margin:10px 0;padding:8px;background:var(--card);border:1px solid var(--border);border-radius:6px;font-size:11px\">';"
        js += "h+='<span style=\"color:var(--yellow);font-weight:600\">Max Pain: %s</span>';" % _js_str(fnum(mp))
        diff = ind.get('max_pain_diff')
        if diff is not None:
            js += "h+=' <span style=\"color:var(--sub)\">(ATM%s)</span>';" % (_js_str(fnum(diff, plus=True)))
        js += "h+='</div>';"
    reinforced = ind.get('walls_reinforced', [])
    weakened = ind.get('walls_weakened', [])
    if reinforced or weakened:
        js += "h+='<div style=\"margin-top:10px\"><div style=\"font-size:11px;font-weight:600;color:var(--accent);margin-bottom:4px\">壁の変化</div>';"
        if reinforced:
            js += "h+='<div style=\"font-size:10px;color:var(--sub);margin:2px 0\">🧱 補強: ';"
            for w in reinforced:
                color = 'var(--put)' if w['type'] == 'P' else 'var(--call)'
                js += "h+='<span style=\"color:%s;margin-right:8px\">%s%s +%s</span>';" % (color, w['type'], _js_str(fnum(w['strike'])), _js_str(fnum(w['change'])))
            js += "h+='</div>';"
        if weakened:
            js += "h+='<div style=\"font-size:10px;color:var(--sub);margin:2px 0\">⚠️ 崩壊: ';"
            for w in weakened:
                color = 'var(--put)' if w['type'] == 'P' else 'var(--call)'
                js += "h+='<span style=\"color:%s;margin-right:8px\">%s%s %s</span>';" % (color, w['type'], _js_str(fnum(w['strike'])), _js_str(fnum(w['change'])))
            js += "h+='</div>';"
        js += "h+='</div>';"
    js += "return h;"
    return js

def _detail_jnet_js(s07):
    if not s07:
        return "var h='<div>該当なし</div>';return h;"
    js = "var h='';"
    js += "h+='<table><tr><th>銘柄</th><th>参加者</th><th>取引高</th><th>分類</th></tr>';"
    for t in s07:
        cat_tag = {'us': 'tag-us', 'eu': 'tag-eu', 'hf': 'tag-hf', 'domestic': 'tag-dom'}.get(t['category'], '')
        cat_label = {'us': '米系', 'eu': '欧系', 'hf': 'HF代理', 'domestic': '国内'}.get(t['category'], 'その他')
        pair = ' <span style="color:var(--yellow)">🔄</span>' if t.get('is_pair') else ''
        js += "h+='<tr><td>%s</td><td>%s%s</td><td>%s</td><td><span class=\"tag %s\">%s</span></td></tr>';" % (
            _js_str(esc(t['product'][:30])), _js_str(esc(t['participant'])), pair, _js_str(fnum(t['volume'])), cat_tag, cat_label)
    js += "h+='</table>';"
    js += "return h;"
    return js

def _detail_assess_js(data):
    s01 = data.get('s01', {})
    s02 = data.get('s02', {})
    s04 = data.get('s04', {})
    s06 = data.get('s06', {})
    s07 = data.get('s07', [])
    ind = data.get('indicators', {})
    r1d = s01.get('range_1d', {})
    r1w = s01.get('range_1w', {})
    js = "var h='';"
    if r1d or r1w:
        js += "h+='<div class=\"summary-box\">';"
        if r1d:
            js += "h+='<div class=\"summary-item\"><div class=\"si-label\">1日予測値幅</div><div class=\"si-value\" style=\"color:var(--yellow)\">%s 〜 %s</div></div>';" % (_js_str(fnum(r1d.get('low'))), _js_str(fnum(r1d.get('high'))))
        if r1w:
            js += "h+='<div class=\"summary-item\"><div class=\"si-label\">1週予測値幅</div><div class=\"si-value\" style=\"color:var(--yellow)\">%s 〜 %s</div></div>';" % (_js_str(fnum(r1w.get('low'))), _js_str(fnum(r1w.get('high'))))
        js += "h+='</div>';"
    pcr = ind.get('pcr_volume')
    mp = ind.get('max_pain')
    if pcr or mp:
        js += "h+='<div class=\"summary-box\">';"
        if pcr is not None:
            pcr_color = 'var(--red)' if pcr > 1.0 else 'var(--green)' if pcr < 0.7 else 'var(--text)'
            js += "h+='<div class=\"summary-item\"><div class=\"si-label\">PCR（取引高）</div><div class=\"si-value\" style=\"color:%s\">%.2f</div><div style=\"font-size:9px;color:var(--sub)\">%s</div></div>';" % (pcr_color, pcr, _js_str(ind.get('pcr_signal', '')))
        if mp:
            js += "h+='<div class=\"summary-item\"><div class=\"si-label\">Max Pain</div><div class=\"si-value\">%s</div><div style=\"font-size:9px;color:var(--sub)\">ATM%s</div></div>';" % (_js_str(fnum(mp)), _js_str(fnum(ind.get('max_pain_diff', 0), plus=True)))
        js += "h+='</div>';"
    ohlc = data.get('metadata', {}).get('ohlc', {})
    if ohlc.get('pivot'):
        js += "h+='<div style=\"background:var(--card);border:1px solid var(--border);border-radius:8px;padding:12px;margin:10px 0\">';"
        js += "h+='<div style=\"font-weight:600;color:var(--accent);margin-bottom:6px;font-size:12px\">前日4本値 + ピボットポイント</div>';"
        js += "h+='<div class=\"summary-box\" style=\"margin-bottom:8px\">';"
        js += "h+='<div class=\"summary-item\"><div class=\"si-label\">始値</div><div class=\"si-value\" style=\"font-size:14px\">%s</div></div>';" % _js_str(fnum(ohlc['open']))
        js += "h+='<div class=\"summary-item\"><div class=\"si-label\">高値</div><div class=\"si-value\" style=\"font-size:14px;color:var(--green)\">%s</div></div>';" % _js_str(fnum(ohlc['high']))
        js += "h+='<div class=\"summary-item\"><div class=\"si-label\">安値</div><div class=\"si-value\" style=\"font-size:14px;color:var(--red)\">%s</div></div>';" % _js_str(fnum(ohlc['low']))
        js += "h+='<div class=\"summary-item\"><div class=\"si-label\">清算値</div><div class=\"si-value\" style=\"font-size:14px\">%s</div></div>';" % _js_str(fnum(ohlc['close']))
        js += "h+='<div class=\"summary-item\"><div class=\"si-label\">値幅</div><div class=\"si-value\" style=\"font-size:14px\">%s</div></div>';" % _js_str(fnum(ohlc['range']))
        js += "h+='</div>';"
        levels = [('R3', ohlc.get('r3', 0), 'var(--call)'), ('R2', ohlc.get('r2', 0), 'var(--call)'), ('R1', ohlc.get('r1', 0), 'var(--call)'), ('PP', ohlc.get('pivot', 0), 'var(--yellow)'), ('S1', ohlc.get('s1', 0), 'var(--put)'), ('S2', ohlc.get('s2', 0), 'var(--put)'), ('S3', ohlc.get('s3', 0), 'var(--put)')]
        for label, val, color in levels:
            is_pp = label == 'PP'
            weight = 'font-weight:700;' if is_pp else ''
            border = 'border-top:1px solid var(--yellow);' if is_pp else ''
            js += "h+='<div style=\"display:flex;justify-content:space-between;padding:3px 8px;font-size:11px;%s%s\"><span style=\"color:%s\">%s</span><span style=\"font-family:DM Mono;color:%s\">%s</span></div>';" % (weight, border, color, label, color, _js_str(fnum(val)))
        js += "h+='</div>';"
    js += "h+='<div class=\"analysis-cards\">';"
    mini_chg = s02.get('nk225_mini', {}).get('total_change', 0)
    large_chg = s02.get('nk225_large', {}).get('total_change', 0)
    js += "h+='<div class=\"analysis-card\"><div class=\"ac-title\">📈 需給構造</div><div class=\"ac-body\">ラージ %s / mini %s" % (_js_str(fnum(large_chg, plus=True)), _js_str(fnum(mini_chg, plus=True)))
    if mini_chg > 0 and large_chg < 0:
        js += "<br>個人買い vs 機関売り"
    elif mini_chg < 0 and large_chg > 0:
        js += "<br>機関買い vs 個人売り"
    js += "</div></div>';"
    js += "h+='<div class=\"analysis-card\"><div class=\"ac-title\">🏛 手口シグナル</div><div class=\"ac-body\">"
    if s07:
        top = s07[0]
        js += "%s %s枚" % (_js_str(esc(top['participant'][:8])), _js_str(fnum(top['volume'])))
        if len(s07) > 1:
            js += "<br>他%d件の大口取引" % (len(s07) - 1)
    else:
        js += "大口取引なし"
    js += "</div></div>';"
    lg = s04.get('large', {})
    pc = lg.get('put_total_change', 0)
    cc = lg.get('call_total_change', 0)
    js += "h+='<div class=\"analysis-card\"><div class=\"ac-title\">📊 建玉変動</div><div class=\"ac-body\">P %s / C %s" % (_js_str(fnum(pc, plus=True)), _js_str(fnum(cc, plus=True)))
    if pc > 0 and cc > 0:
        js += "<br>両建て増加"
    elif pc > cc:
        js += "<br>プット優位"
    elif cc > pc:
        js += "<br>コール優位"
    js += "</div></div>';"
    dist = s06.get('distribution', [])
    if dist:
        max_p = max(dist, key=lambda d: d['put_oi'])
        max_c = max(dist, key=lambda d: d['call_oi'])
        js += "h+='<div class=\"analysis-card\"><div class=\"ac-title\">🎯 S/R水準</div><div class=\"ac-body\"><span style=\"color:var(--put)\">S: %s</span> (%s枚)<br><span style=\"color:var(--call)\">R: %s</span> (%s枚)</div></div>';" % (_js_str(fnum(max_p['strike'])), _js_str(fnum(max_p['put_oi'])), _js_str(fnum(max_c['strike'])), _js_str(fnum(max_c['call_oi'])))
    js += "h+='</div>';"
    # Technical Levels
    tech = data.get('technicals', {})
    pivot = tech.get('pivot', {})
    fib = tech.get('fibonacci', {})
    bb = tech.get('bollinger', {})
    rsi = tech.get('rsi', {})

    if pivot or fib or bb or rsi:
        js += "h+='<div style=\"margin-top:12px;font-size:13px;font-weight:600;color:var(--accent);margin-bottom:8px\">テクニカルレベル</div>';"
        js += "h+='<div style=\"display:flex;gap:10px;flex-wrap:wrap\">';"

        # Pivot Points
        if pivot:
            js += "h+='<div style=\"flex:1;min-width:140px;background:var(--card);border:1px solid var(--border);border-radius:8px;padding:10px\">';"
            js += "h+='<div style=\"font-size:10px;font-weight:600;color:var(--accent);margin-bottom:6px\">ピボットポイント</div>';"
            for lbl, key, color in [('R3', 'r3', 'var(--call)'), ('R2', 'r2', 'var(--call)'), ('R1', 'r1', 'var(--call)'), ('PP', 'pp', 'var(--yellow)'), ('S1', 's1', 'var(--put)'), ('S2', 's2', 'var(--put)'), ('S3', 's3', 'var(--put)')]:
                val = pivot.get(key, 0)
                weight = 'font-weight:700;' if lbl == 'PP' else ''
                js += "h+='<div style=\"display:flex;justify-content:space-between;padding:2px 4px;font-size:10px;%s\"><span style=\"color:%s\">%s</span><span style=\"font-family:DM Mono;color:%s\">%s</span></div>';" % (weight, color, lbl, color, _js_str(fnum(val)))
            js += "h+='</div>';"

        # Fibonacci
        if fib:
            js += "h+='<div style=\"flex:1;min-width:140px;background:var(--card);border:1px solid var(--border);border-radius:8px;padding:10px\">';"
            fib_label = _js_str(esc(fib.get('label', '')))
            js += "h+='<div style=\"font-size:10px;font-weight:600;color:var(--accent);margin-bottom:2px\">フィボナッチ (%d日)</div>';" % fib.get('period', 20)
            js += "h+='<div style=\"font-size:9px;color:var(--sub);margin-bottom:4px\">%s</div>';" % fib_label
            levels = fib.get('levels', {})
            for pct in ['0%', '23.6%', '38.2%', '50%', '61.8%', '78.6%', '100%']:
                val = levels.get(pct, 0)
                is_key = pct in ('38.2%', '50%', '61.8%')
                weight = 'font-weight:600;' if is_key else ''
                color = 'var(--yellow)' if is_key else 'var(--sub)'
                js += "h+='<div style=\"display:flex;justify-content:space-between;padding:2px 4px;font-size:10px;%s\"><span style=\"color:%s\">%s</span><span style=\"font-family:DM Mono;color:var(--text)\">%s</span></div>';" % (weight, color, pct, _js_str(fnum(val)))
            js += "h+='</div>';"

        # BB + RSI combined
        if bb or rsi:
            js += "h+='<div style=\"flex:1;min-width:140px;background:var(--card);border:1px solid var(--border);border-radius:8px;padding:10px\">';"
            if bb:
                js += "h+='<div style=\"font-size:10px;font-weight:600;color:var(--accent);margin-bottom:4px\">ボリンジャーバンド (%d日)</div>';" % bb.get('period', 20)
                for lbl, key, color in [('+3\\u03c3', 'upper3', 'var(--call)'), ('+2\\u03c3', 'upper2', 'var(--call)'), ('+1\\u03c3', 'upper1', 'var(--call)'), ('SMA', 'mean', 'var(--yellow)'), ('-1\\u03c3', 'lower1', 'var(--put)'), ('-2\\u03c3', 'lower2', 'var(--put)'), ('-3\\u03c3', 'lower3', 'var(--put)')]:
                    val = bb.get(key, 0)
                    weight = 'font-weight:600;' if 'mean' in key else ''
                    js += "h+='<div style=\"display:flex;justify-content:space-between;padding:2px 4px;font-size:10px;%s\"><span style=\"color:%s\">%s</span><span style=\"font-family:DM Mono;color:var(--text)\">%s</span></div>';" % (weight, color, lbl, _js_str(fnum(val)))
                sig = bb.get('current_sigma', 0)
                sig_color = 'var(--red)' if abs(sig) > 2 else 'var(--yellow)' if abs(sig) > 1 else 'var(--green)'
                js += "h+='<div style=\"margin-top:4px;font-size:10px;color:var(--sub)\">現在位置: <span style=\"color:%s;font-weight:600\">%+.1f\\u03c3</span></div>';" % (sig_color, sig)
            if rsi:
                rsi_val = rsi.get('value', 50)
                rsi_color = 'var(--red)' if rsi_val >= 70 else 'var(--green)' if rsi_val <= 30 else 'var(--text)'
                js += "h+='<div style=\"margin-top:8px;font-size:10px;font-weight:600;color:var(--accent)\">RSI (%d日)</div>';" % rsi.get('period', 14)
                js += "h+='<div style=\"font-family:DM Mono;font-size:16px;font-weight:700;color:%s\">%s</div>';" % (rsi_color, _js_str(rsi_val))
                js += "h+='<div style=\"font-size:9px;color:var(--sub)\">%s</div>';" % _js_str(esc(rsi.get('signal', '')))
            js += "h+='</div>';"

        js += "h+='</div>';"

    js += "return h;"
    return js


def _preview_gemini(data):
    assessment = data.get('s08_assessment', '')
    source = data.get('s08_source', '')
    if not assessment:
        return '<span class="mm-label">生成待ち</span>'
    badge = '👤 手動' if source == 'manual' else '🤖 AI'
    # Extract first ■ header as preview
    parts = assessment.split('■')
    for part in parts[1:2]:
        lines = part.strip().split('\n', 1)
        header = lines[0].strip()[:20]
        return '<div class="mini-metrics"><div class="mini-metric"><div class="mm-label">%s</div><div class="mm-value" style="font-size:12px;color:var(--accent)">■ %s…</div></div></div>' % (badge, esc(header))
    return '<span class="mm-label">%s 生成済み</span>' % badge


def _detail_gemini_js(data):
    assessment = data.get('s08_assessment', '')
    source = data.get('s08_source', '')
    if not assessment:
        return "var h='<div class=\"insight\">手動分析(data/manual_assessment_YYYYMMDD.md)を置くか、GEMINI_API_KEY を設定すると表示されます。</div>';return h;"
    js = "var h='';"
    # Source badge line
    if source == 'manual':
        js += "h+='<div style=\"font-size:11px;color:var(--sub);margin-bottom:8px\">👤 手動分析(Claude等で作成)</div>';"
    else:
        js += "h+='<div style=\"font-size:11px;color:var(--sub);margin-bottom:8px\">🤖 AI自動生成(Gemini)</div>';"
    js += "h+='<div class=\"insight\" style=\"white-space:pre-wrap;line-height:1.8\">';"
    parts = assessment.split('■')
    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        lines = part.split('\n', 1)
        header = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ''
        js += "h+='<div style=\"margin-top:%dpx\"><strong style=\"color:var(--accent)\">■ %s</strong><br>%s</div>';" % (0 if i <= 1 else 10, _js_str(esc(header)), _js_str(esc(body)))
    js += "h+='</div>';"
    js += "return h;"
    return js


# ============================================================
# === PATCH: Strike Matrix Functions (NEW) ===
# ============================================================

def _val_cell(val, is_atm, delta=None):
    """Return JS string fragment for one value cell in the strike matrix."""
    abdr = 'border-left:2px solid rgba(251,191,36,.4);' if is_atm else ''
    if val != 0:
        bg = 'rgba(248,113,113,.15)' if val < 0 else 'rgba(74,222,128,.15)'
        cl = 'var(--red)' if val < 0 else 'var(--green)'
        # Main value
        s = "h+='<td style=\"%sfont-family:DM Mono;font-size:9px;text-align:right;padding:2px 3px;color:%s;background:%s\">" % (abdr, cl, bg)
        s += "%s" % _js_str(fnum(val, plus=False))
        # Delta (small text below)
        if delta and delta != 0:
            d_cl = 'var(--green)' if delta > 0 else 'var(--red)'
            s += "<br><span style=\"font-size:7px;color:%s\">%s</span>" % (d_cl, _js_str(fnum(delta, plus=True)))
        s += "</td>';"
        return s
    elif delta and delta != 0:
        # No current position but there was a change (position closed)
        d_cl = 'var(--green)' if delta > 0 else 'var(--red)'
        return "h+='<td style=\"%sfont-family:DM Mono;font-size:7px;text-align:right;padding:2px 3px;color:%s\">%s</td>';" % (abdr, d_cl, _js_str(fnum(delta, plus=True)))
    return "h+='<td style=\"%spadding:2px 1px\"></td>';" % abdr


def _strike_matrix_js(s09):
    """Generate JS string for ⑨-D strike x participant matrix table."""
    sm = s09.get('strike_matrix', {})
    if not sm or not sm.get('participants'):
        return ""
    strikes = sm.get('strikes', [])
    parts = sm.get('participants', [])
    atm_r = sm.get('atm_round', 0)
    ns = len(strikes)
    if ns == 0:
        return ""

    js = ""
    js += "h+='<div style=\"margin-top:18px;padding-top:14px;border-top:1px solid var(--border)\">';"
    js += "h+='<div style=\"font-size:13px;font-weight:600;color:var(--text);margin-bottom:4px\">';"
    js += "h+='\\u884C\\u4F7F\\u4FA1\\u683C\\u5225\\u30DD\\u30B8\\u30B7\\u30E7\\u30F3\\u5206\\u5E03';"
    js += "h+='</div>';"
    js += "h+='<div style=\"font-size:10px;color:var(--sub);margin-bottom:10px\">';"
    prev_date = sm.get('prev_date', '')
    if prev_date:
        js += "h+='ATM %s / \\u8CA0=\\u58F2\\u308A\\u8D8A\\u3057 \\u6B63=\\u8CB7\\u3044\\u8D8A\\u3057 / \\u5C0F\\u6587\\u5B57=\\u524D\\u9031\\u6BD4(%s\\u6642\\u70B9)';" % (_js_str(fnum(atm_r)), _js_str(prev_date[:8]))
    else:
        js += "h+='ATM %s / \\u8CA0=\\u58F2\\u308A\\u8D8A\\u3057 \\u6B63=\\u8CB7\\u3044\\u8D8A\\u3057';" % _js_str(fnum(atm_r))
    js += "h+='</div>';"
    # Customer type legend
    js += "h+='<div style=\"display:flex;flex-wrap:wrap;gap:6px 14px;margin-bottom:12px;font-size:10px;color:var(--sub);line-height:1.7\">';"
    js += "h+='<div><b style=\"color:var(--us)\">\\u30b0\\u30ed\\u30fc\\u30d0\\u30eb\\u30de\\u30af\\u30ed</b>: GS/Citi/JPM \\u65b9\\u5411\\u6027\\u30d9\\u30c3\\u30c8</div>';"
    js += "h+='<div><b style=\"color:var(--us)\">\\u9577\\u671f\\u6295\\u8cc7\\u5fd7\\u5411</b>: BofA \\u4e2d\\u9577\\u671f\\u30dd\\u30b8\\u30b7\\u30e7\\u30f3</div>';"
    js += "h+='<div><b style=\"color:var(--us)\">CTA</b>: \\u30e2\\u30eb\\u30ac\\u30f3MUFG \\u30c8\\u30ec\\u30f3\\u30c9\\u8ffd\\u5f93</div>';"
    js += "h+='<div><b style=\"color:var(--hf)\">\\u30a2\\u30fc\\u30d3\\u30c8\\u30e9\\u30fc\\u30b8</b>: ABN/SocGen/BNP \\u88c1\\u5b9a\\u30fbHF\\u4ee3\\u7406</div>';"
    js += "h+='<div><b style=\"color:var(--dom)\">\\u56fd\\u5185\\u6a5f\\u95a2</b>: \\u307f\\u305a\\u307b/\\u91ce\\u6751 \\u30d8\\u30c3\\u30b8\\u4e3b\\u4f53</div>';"
    js += "h+='<div><b style=\"color:var(--dom)\">\\u56fd\\u5185\\u500b\\u4eba</b>: SBI/\\u697d\\u5929/\\u677e\\u4e95 \\u30cd\\u30c3\\u30c8\\u30c8\\u30ec\\u30fc\\u30c0\\u30fc</div>';"
    js += "h+='</div>';"
    js += "h+='<div style=\"overflow-x:auto;-webkit-overflow-scrolling:touch\">';"
    js += "h+='<table style=\"font-size:10px;white-space:nowrap;border-collapse:collapse\">';"
    sty0 = 'min-width:72px;text-align:left;padding:4px 6px;position:sticky;left:0;background:var(--panel);z-index:2'
    sty1 = 'min-width:84px;text-align:left;padding:4px 6px;position:sticky;left:72px;background:var(--panel);z-index:2'
    sty2 = 'min-width:56px;text-align:center;padding:4px 4px;position:sticky;left:156px;background:var(--panel);z-index:2;border-right:1px solid var(--border)'
    js += "h+='<tr style=\"border-bottom:2px solid var(--border)\">';"
    js += "h+='<th rowspan=\"2\" style=\"%s\">\\u9867\\u5BA2\\u30BF\\u30A4\\u30D7</th>';" % sty0
    js += "h+='<th rowspan=\"2\" style=\"%s\">\\u8A3C\\u5238\\u4F1A\\u793E</th>';" % sty1
    js += "h+='<th rowspan=\"2\" style=\"%s\">N225</th>';" % sty2
    js += "h+='<th colspan=\"%d\" style=\"text-align:center;padding:4px;color:var(--put);border-bottom:2px solid var(--put)\">\\u30D7\\u30C3\\u30C8</th>';" % ns
    js += "h+='<th colspan=\"%d\" style=\"text-align:center;padding:4px;color:var(--call);border-bottom:2px solid var(--call)\">\\u30B3\\u30FC\\u30EB</th>';" % ns
    js += "h+='</tr>';"
    js += "h+='<tr style=\"border-bottom:1px solid var(--border)\">';"
    for _side in range(2):
        for strike in strikes:
            is_atm = (strike == atm_r)
            bg = 'background:rgba(251,191,36,.12);' if is_atm else ''
            lbl = '%g' % (strike / 1000.0) + 'k' if strike >= 10000 else str(strike)
            js += "h+='<th style=\"%sfont-family:DM Mono;font-size:9px;padding:3px 2px;text-align:center\">%s</th>';" % (bg, lbl)
    js += "h+='</tr>';"

    type_order = [
        '\u30b0\u30ed\u30fc\u30d0\u30eb\u30de\u30af\u30ed',
        '\u9577\u671f\u6295\u8cc7\u5fd7\u5411',
        '\u30c8\u30ec\u30f3\u30c9\u30d5\u30a9\u30ed\u30fc\uff08CTA\uff09',
        '\u30a2\u30fc\u30d3\u30c8\u30e9\u30fc\u30b8\uff08\u88c1\u5b9a\u53d6\u5f15\uff09',
        '\u56fd\u5185\u6a5f\u95a2\u6295\u8cc7\u5bb6',
        '\u56fd\u5185\u500b\u4eba\u6295\u8cc7\u5bb6\uff08\u30cd\u30c3\u30c8\u30c8\u30ec\u30fc\u30c0\u30fc\uff09',
        '\u30fc',
    ]
    from collections import OrderedDict
    groups = OrderedDict()
    seen = set()
    for t in type_order:
        members = [p for p in parts if p.get('customer_type', '') == t]
        if members:
            groups[t] = members
            seen.add(t)
    for p in parts:
        ct = p.get('customer_type', '\u30fc')
        if ct not in seen:
            if ct not in groups:
                groups[ct] = []
            groups[ct].append(p)

    for ctype, members in groups.items():
        for idx, p in enumerate(members):
            pos = p.get('positions', {})
            deltas = p.get('deltas', {})
            fut = p.get('futures', {})
            d_label = fut.get('direction', '\u30fc')
            d_sum = fut.get('summary', '')
            nk_large = fut.get('nk225_large', 0)
            nk_delta = fut.get('nk225_large_delta', None)
            if '\u30ed\u30f3\u30b0' in d_label:
                d_color = 'var(--green)'
            elif '\u30b7\u30e7\u30fc\u30c8' in d_label:
                d_color = 'var(--red)'
            else:
                d_color = 'var(--sub)'
            r_bdr = 'border-top:1px solid var(--border);' if idx == 0 else ''
            new_tag = ' <span style="font-size:7px;color:var(--accent)">[NEW]</span>' if p.get('is_new') else ''
            js += "h+='<tr style=\"%s\">';" % r_bdr
            if idx == 0:
                js += "h+='<td rowspan=\"%d\" style=\"font-size:9px;color:var(--sub);padding:3px 6px;vertical-align:top;position:sticky;left:0;background:var(--panel);border-right:1px solid var(--border)\">%s</td>';" % (len(members), _js_str(esc(ctype)))
            js += "h+='<td style=\"font-size:10px;padding:3px 6px;position:sticky;left:72px;background:var(--panel)\">%s%s</td>';" % (_js_str(esc(p['name'][:14])), new_tag)
            # Futures column: show position number + delta
            fut_text = _js_str(esc(d_label))
            if nk_large != 0:
                fut_text = _js_str(fnum(nk_large, plus=True))
                if nk_delta and nk_delta != 0:
                    d_cl = 'var(--green)' if nk_delta > 0 else 'var(--red)'
                    fut_text += '<br><span style=\"font-size:7px;color:%s\">%s</span>' % (d_cl, _js_str(fnum(nk_delta, plus=True)))
            ttl = ' title=\"%s\"' % _js_str(esc(d_sum)) if d_sum else ''
            js += "h+='<td style=\"font-size:9px;text-align:center;color:%s;padding:2px 4px;position:sticky;left:156px;background:var(--panel);border-right:1px solid var(--border)\"%s>%s</td>';" % (d_color, ttl, fut_text)
            for strike in strikes:
                sk = str(strike)
                val = pos.get(sk, {}).get('put', 0)
                d = deltas.get(sk, {}).get('put', None)
                js += _val_cell(val, strike == atm_r, delta=d)
            for strike in strikes:
                sk = str(strike)
                val = pos.get(sk, {}).get('call', 0)
                d = deltas.get(sk, {}).get('call', None)
                js += _val_cell(val, strike == atm_r, delta=d)
            js += "h+='</tr>';"

    js += "h+='</table></div></div>';"
    return js


# ============================================================
# === PATCH: Modified _detail_participants_js (strike matrix call added) ===
# ============================================================

def _detail_participants_js(s09):
    if 'error' in s09:
        return "var h='<div>週次データなし</div>';return h;"
    js = "var h='';"
    if s09.get('source') == 'cache':
        js += "h+='<div style=\"background:rgba(251,191,36,.1);border:1px solid rgba(251,191,36,.2);border-radius:6px;padding:8px;margin-bottom:10px;font-size:11px;color:var(--yellow)\">%s時点のキャッシュデータ（参考値）</div>';" % _js_str(s09.get('data_date', '?'))

    # === Strike matrix table ===
    js += _strike_matrix_js(s09)

    js += "return h;"
    return js


def _detail_strategy_js(s11, atm):
    otm = s11.get('otm_table', [])
    edges = s11.get('edge_scores', [])
    if not otm:
        return "var h='<div>データ不足（ATMまたはVI未設定）</div>';return h;"
    js = "var h='';"
    js += "h+='<h3 style=\"color:#fff;font-size:13px;margin:8px 0 4px\">OTM確率テーブル</h3>';"
    js += "h+='<table><tr><th>行使価格</th><th>タイプ</th><th>VI-10</th><th>現在</th><th>VI+10</th><th>BS価格</th></tr>';"
    for o in otm:
        js += "h+='<tr><td style=\"font-family:DM Mono\">%s</td><td>%s</td><td>%s</td><td style=\"font-weight:600\">%s</td><td>%s</td><td>%s</td></tr>';" % (
            _js_str(fnum(o['strike'])), _js_str(o['label']), _js_str(fpct(o['otm_prob']['vi_minus10'])), _js_str(fpct(o['otm_prob']['vi_current'])), _js_str(fpct(o['otm_prob']['vi_plus10'])), _js_str(fnum(o['bs_price'])))
    js += "h+='</table>';"
    if edges:
        js += "h+='<h3 style=\"color:#fff;font-size:13px;margin:12px 0 4px\">ゾーン別エッジ評価</h3>';"
        for e in edges:
            stars = '★' * e['stars'] + '☆' * (5 - e['stars'])
            if 'プット' in e['zone']:
                zone_color = 'var(--put)'
                border_color = 'rgba(248,113,113,.2)'
            elif 'コール' in e['zone']:
                zone_color = 'var(--call)'
                border_color = 'rgba(96,165,250,.2)'
            else:
                zone_color = 'var(--yellow)'
                border_color = 'rgba(251,191,36,.2)'
            js += "h+='<div class=\"zone-card\" style=\"border-color:%s\"><div class=\"zc-header\"><span class=\"zc-name\" style=\"color:%s\">%s</span><span class=\"zc-stars\">%s</span></div>';" % (border_color, zone_color, _js_str(e['zone']), stars)
            js += "h+='<div class=\"zc-detail\">';"
            if e['wall_max_oi']:
                js += "h+='🧱 壁: %s枚 @%s &nbsp; ';" % (_js_str(fnum(e['wall_max_oi'])), _js_str(fnum(e['wall_strike'])))
            js += "h+='📈 OTM: %.1f%% &nbsp; スコア: %.2f</div></div>';" % (e.get('otm_score', 0) * 50 + 50, e.get('total_score', 0))
    js += "h+='<div style=\"margin:14px 0;text-align:center\"><a href=\"pnl_simulator.html\" style=\"display:inline-block;padding:10px 24px;background:var(--accent);color:#fff;border-radius:8px;text-decoration:none;font-family:Outfit;font-weight:600;font-size:13px\">📊 P&Lシミュレーターを開く →</a></div>';"
    js += "return h;"
    return js


# ============================================================
# P&L Simulator, Archive, Main Pipeline (unchanged from original)
# ============================================================

def build_simulator_html(data):
    meta = data['metadata']
    s01 = data.get('s01', {})
    s11 = data.get('s11', {})
    atm = meta.get('atm', 0)
    vi = s01.get('vi', 0)
    days_to_sq = meta.get('days_to_sq', 0)
    presets = s11.get('presets', [])
    h = '<!DOCTYPE html>\n<html lang="ja">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width,initial-scale=1">\n'
    h += '<title>P&L Simulator %s</title>\n' % esc(meta.get('date_formatted', ''))
    h += '<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700&family=Noto+Sans+JP:wght@400;500;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">\n'
    h += '<style>\n%s\n' % DASHBOARD_CSS
    h += '.sim-section{max-width:900px;margin:0 auto;padding:16px}\n.preset-btn{display:inline-block;padding:6px 14px;margin:4px;background:var(--card);border:1px solid var(--border);border-radius:6px;color:var(--text);cursor:pointer;font-size:11px;font-family:Outfit}\n.preset-btn:hover{border-color:var(--accent);color:var(--accent)}\n.leg-row{display:flex;gap:8px;align-items:center;margin:4px 0;flex-wrap:wrap}\n.leg-row select,.leg-row input{background:var(--card);border:1px solid var(--border);color:var(--text);padding:4px 8px;border-radius:4px;font-size:12px;font-family:DM Mono}\n.leg-row input{width:80px}\n.btn{padding:6px 16px;background:var(--accent);color:#fff;border:none;border-radius:6px;cursor:pointer;font-family:Outfit;font-size:12px}\n.btn-outline{background:transparent;border:1px solid var(--border);color:var(--text)}\n.btn-outline:hover{border-color:var(--accent)}\n#pnl-canvas{width:100%;height:300px;background:var(--card);border-radius:8px;margin:12px 0}\n.pnl-table{font-size:11px}\n.pnl-table td,.pnl-table th{padding:3px 6px}\n'
    h += '</style>\n</head>\n<body>\n'
    h += '<div class="topbar"><span class="logo">P&L Simulator</span><nav><a href="index.html">← ダッシュボード</a><a href="weekly_trend.html">週次推移</a><a href="archive.html">アーカイブ</a></nav></div>\n'
    h += '<div class="hero"><h1>P&L Simulator</h1><div class="sub">%s / ATM %s / VI %s / SQまで%d日</div></div>\n' % (esc(meta.get('date_formatted', '')), fnum(atm), vi, days_to_sq)
    h += '<div class="kpi-strip">\n  <div class="kpi"><div class="label">ATM</div><div class="value">%s</div></div>\n  <div class="kpi"><div class="label">VI</div><div class="value">%s</div></div>\n  <div class="kpi"><div class="label">SQ</div><div class="value">%s</div></div>\n  <div class="kpi"><div class="label">残り営業日</div><div class="value">%d</div></div>\n</div>\n' % (fnum(atm), vi, esc(meta.get('sq_date', '')), days_to_sq)
    h += '<div class="sim-section">\n<div style="margin:12px 0"><div style="color:var(--sub);font-size:11px;margin-bottom:6px">プリセット戦略</div>\n'
    for i, p in enumerate(presets):
        h += '<span class="preset-btn" data-preset="%d">%s</span>\n' % (i, esc(p['name']))
    h += '</div>\n<div style="margin:12px 0"><div style="display:flex;gap:8px;margin-bottom:8px">\n  <button class="btn-outline btn" id="add-put">+ プット</button>\n  <button class="btn-outline btn" id="add-call">+ コール</button>\n  <button class="btn-outline btn" id="add-fut">+ 先物mini</button>\n  <button class="btn-outline btn" id="clear-legs">クリア</button>\n  <button class="btn" id="calc-btn">計算</button>\n</div>\n<div id="legs-container"></div></div>\n'
    h += '<div id="result-section" style="display:none">\n  <div class="kpi-strip" id="result-kpis"></div>\n  <canvas id="pnl-canvas" width="860" height="300"></canvas>\n  <div id="pnl-table-wrap"></div>\n</div>\n</div>\n'
    h += '<div class="footer"><a href="index.html">ダッシュボード</a> <a href="weekly_trend.html">週次推移</a> <a href="archive.html">アーカイブ</a></div>\n'
    h += '<script>\nvar ATM=%d,VI=%s,T=%s,DAYS=%d;\n' % (atm or 0, vi or 0, round(days_to_sq / 250, 6) if days_to_sq else 0, days_to_sq)
    h += 'var PRESETS=%s;\n' % json.dumps(presets, ensure_ascii=False)
    h += _build_simulator_js()
    h += '</script>\n</body>\n</html>'
    return h

def _build_simulator_js():
    return r"""
var legs=[];var legId=0;
function normCdf(x){if(x>=0){var t=1/(1+0.2316419*x)}else{var t=1/(1-0.2316419*x)}var d=0.3989422804014327;var p=((((1.330274429*t-1.821255978)*t+1.781477937)*t-0.356563782)*t+0.319381530)*t;if(x>=0)return 1-d*Math.exp(-0.5*x*x)*p;return d*Math.exp(-0.5*x*x)*p;}
function bsPrice(type,K,F,s,T){if(T<=0||s<=0){return type==='put'?Math.max(K-F,0):Math.max(F-K,0);}var sqT=Math.sqrt(T);var d1=(Math.log(F/K)+0.5*s*s*T)/(s*sqT);var d2=d1-s*sqT;if(type==='put')return K*normCdf(-d2)-F*normCdf(-d1);return F*normCdf(d1)-K*normCdf(d2);}
function addLeg(type,side,strike,premium,qty,mult){var id='leg'+legId++;legs.push({id:id,type:type,side:side||'short',strike:strike||ATM,premium:premium||0,qty:qty||1,mult:mult||(type==='futures'?100:1000),entry:strike||ATM});renderLegs();}
function renderLegs(){var c=document.getElementById('legs-container');var h='';for(var i=0;i<legs.length;i++){var L=legs[i];h+='<div class="leg-row" data-lid="'+L.id+'">';h+='<select class="leg-side"><option value="short"'+(L.side==='short'?' selected':'')+'>売</option><option value="long"'+(L.side==='long'?' selected':'')+'>買</option></select>';h+='<span style="color:var(--sub);font-size:11px;width:50px">'+L.type+'</span>';if(L.type==='futures'){h+='<label style="font-size:10px;color:var(--sub)">Entry</label><input class="leg-entry" type="number" value="'+L.entry+'" step="500">';}else{h+='<label style="font-size:10px;color:var(--sub)">K</label><input class="leg-strike" type="number" value="'+L.strike+'" step="500">';h+='<label style="font-size:10px;color:var(--sub)">Prem</label><input class="leg-prem" type="number" value="'+L.premium+'" step="10">';}h+='<label style="font-size:10px;color:var(--sub)">枚</label><input class="leg-qty" type="number" value="'+L.qty+'" step="1" style="width:50px">';h+='<select class="leg-mult"><option value="1000"'+(L.mult===1000?' selected':'')+'>x1000</option><option value="100"'+(L.mult===100?' selected':'')+'>x100</option></select>';h+='<span style="cursor:pointer;color:var(--red);font-size:14px" class="leg-del">✕</span>';h+='</div>';}c.innerHTML=h;}
function readLegsFromDOM(){var rows=document.querySelectorAll('.leg-row');for(var i=0;i<rows.length;i++){var lid=rows[i].getAttribute('data-lid');for(var j=0;j<legs.length;j++){if(legs[j].id===lid){var L=legs[j];L.side=rows[i].querySelector('.leg-side').value;L.qty=parseInt(rows[i].querySelector('.leg-qty').value)||1;L.mult=parseInt(rows[i].querySelector('.leg-mult').value)||1000;var sk=rows[i].querySelector('.leg-strike');if(sk)L.strike=parseInt(sk.value)||ATM;var pr=rows[i].querySelector('.leg-prem');if(pr)L.premium=parseFloat(pr.value)||0;var en=rows[i].querySelector('.leg-entry');if(en)L.entry=parseInt(en.value)||ATM;}}}}
function calculate(){readLegsFromDOM();if(legs.length===0)return;var sqLow=ATM-6000,sqHigh=ATM+6000,step=500;var results=[];var maxProfit=-Infinity,maxLoss=Infinity;for(var sq=sqLow;sq<=sqHigh;sq+=step){var total=0;var legPnls=[];for(var i=0;i<legs.length;i++){var L=legs[i];var pnl=0;if(L.type==='put'){var intrinsic=Math.max(L.strike-sq,0);pnl=L.side==='short'?(L.premium-intrinsic):(intrinsic-L.premium);}else if(L.type==='call'){var intrinsic=Math.max(sq-L.strike,0);pnl=L.side==='short'?(L.premium-intrinsic):(intrinsic-L.premium);}else{pnl=L.side==='short'?(L.entry-sq):(sq-L.entry);}var yen=pnl*L.qty*L.mult;legPnls.push(yen);total+=yen;}results.push({sq:sq,total:total,legs:legPnls});if(total>maxProfit)maxProfit=total;if(total<maxLoss)maxLoss=total;}drawChart(results,maxProfit,maxLoss);drawTable(results);var be=[];for(var i=1;i<results.length;i++){if((results[i-1].total<=0&&results[i].total>0)||(results[i-1].total>=0&&results[i].total<0)){be.push(results[i].sq);}}var kh=document.getElementById('result-kpis');var khtml='<div class="kpi"><div class="label">最大利益</div><div class="value up">'+fmtYen(maxProfit)+'</div></div>';khtml+='<div class="kpi"><div class="label">最大損失</div><div class="value down">'+fmtYen(maxLoss)+'</div></div>';khtml+='<div class="kpi"><div class="label">損益分岐</div><div class="value">'+be.join(' / ')+'</div></div>';kh.innerHTML=khtml;document.getElementById('result-section').style.display='block';}
function fmtYen(n){if(Math.abs(n)>=10000)return (n/10000).toFixed(1)+'万円';return n.toLocaleString()+'円';}
function drawChart(results,maxP,maxL){var canvas=document.getElementById('pnl-canvas');var ctx=canvas.getContext('2d');var W=canvas.width,H=canvas.height;ctx.clearRect(0,0,W,H);ctx.fillStyle='#111128';ctx.fillRect(0,0,W,H);var pad={l:60,r:20,t:20,b:30};var cw=W-pad.l-pad.r,ch=H-pad.t-pad.b;var range=Math.max(Math.abs(maxP),Math.abs(maxL))*1.1||1;var zy=pad.t+ch/2;ctx.strokeStyle='rgba(255,255,255,.15)';ctx.setLineDash([4,4]);ctx.beginPath();ctx.moveTo(pad.l,zy);ctx.lineTo(W-pad.r,zy);ctx.stroke();ctx.setLineDash([]);var atmIdx=-1;for(var i=0;i<results.length;i++){if(results[i].sq===ATM){atmIdx=i;break;}}if(atmIdx>=0){var ax=pad.l+(atmIdx/(results.length-1))*cw;ctx.strokeStyle='rgba(251,191,36,.4)';ctx.setLineDash([4,4]);ctx.beginPath();ctx.moveTo(ax,pad.t);ctx.lineTo(ax,H-pad.b);ctx.stroke();ctx.setLineDash([]);}ctx.beginPath();for(var i=0;i<results.length;i++){var x=pad.l+(i/(results.length-1))*cw;var y=pad.t+ch/2-(results[i].total/range)*(ch/2);if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);}ctx.strokeStyle='#818cf8';ctx.lineWidth=2;ctx.stroke();ctx.lineTo(pad.l+cw,zy);ctx.lineTo(pad.l,zy);ctx.closePath();ctx.fillStyle='rgba(129,140,248,.1)';ctx.fill();ctx.fillStyle='#8888aa';ctx.font='10px DM Mono';ctx.textAlign='center';for(var i=0;i<results.length;i+=2){var x=pad.l+(i/(results.length-1))*cw;ctx.fillText(results[i].sq,x,H-pad.b+14);}ctx.textAlign='right';ctx.fillText(fmtYen(Math.round(range)),pad.l-4,pad.t+10);ctx.fillText(fmtYen(Math.round(-range)),pad.l-4,H-pad.b-2);ctx.fillText('0',pad.l-4,zy+4);}
function drawTable(results){var w=document.getElementById('pnl-table-wrap');var h='<table class="pnl-table"><tr><th>SQ着地</th>';for(var i=0;i<legs.length;i++){var L=legs[i];var lbl=L.type==='futures'?'先物':(L.type==='put'?'P':'C')+L.strike+(L.side==='short'?'売':'買');h+='<th>'+lbl+'</th>';}h+='<th>合計P&L</th></tr>';for(var r=0;r<results.length;r++){var R=results[r];var cls=R.sq===ATM?' class="atm-row"':'';h+='<tr'+cls+'><td style="font-family:DM Mono">'+R.sq+'</td>';for(var j=0;j<R.legs.length;j++){var c=R.legs[j]>=0?'positive':'negative';h+='<td class="'+c+'" style="font-family:DM Mono">'+fmtYen(Math.round(R.legs[j]))+'</td>';}var tc=R.total>=0?'positive':'negative';h+='<td class="'+tc+'" style="font-family:DM Mono;font-weight:600">'+fmtYen(Math.round(R.total))+'</td>';h+='</tr>';}h+='</table>';w.innerHTML=h;}
document.getElementById('add-put').addEventListener('click',function(){var prem=Math.round(bsPrice('put',ATM-2000,ATM,VI/100,T));addLeg('put','short',ATM-2000,prem,1,1000);});
document.getElementById('add-call').addEventListener('click',function(){var prem=Math.round(bsPrice('call',ATM+2000,ATM,VI/100,T));addLeg('call','short',ATM+2000,prem,1,1000);});
document.getElementById('add-fut').addEventListener('click',function(){addLeg('futures','short',ATM,0,1,100);});
document.getElementById('clear-legs').addEventListener('click',function(){legs=[];renderLegs();document.getElementById('result-section').style.display='none';});
document.getElementById('calc-btn').addEventListener('click',calculate);
document.addEventListener('click',function(e){var el=e.target;if(el.classList.contains('preset-btn')){var idx=parseInt(el.getAttribute('data-preset'));if(PRESETS[idx]){legs=[];legId=0;var P=PRESETS[idx];for(var i=0;i<P.legs.length;i++){var L=P.legs[i];legs.push({id:'leg'+legId++,type:L.type,side:L.side,strike:L.strike||0,premium:L.premium||0,qty:L.qty||1,mult:L.multiplier||1000,entry:L.entry||ATM});}renderLegs();calculate();}}});
document.getElementById('legs-container').addEventListener('click',function(e){if(e.target.classList.contains('leg-del')){var row=e.target.closest('.leg-row');var lid=row.getAttribute('data-lid');legs=legs.filter(function(l){return l.id!==lid;});renderLegs();}});
"""

def build_archive_snippet(data):
    meta = data['metadata']
    s01 = data.get('s01', {})
    nikkei = s01.get('nikkei_close', 0)
    vi = s01.get('vi', 0)
    WEEKDAYS = ['月', '火', '水', '木', '金', '土', '日']
    date_str = meta.get('date', '')
    dt = None
    try:
        from datetime import datetime as _dt
        dt = _dt.strptime(date_str, '%Y%m%d')
    except:
        pass
    weekday = WEEKDAYS[dt.weekday()] if dt else ''
    date_disp = '%s.%s.%s' % (date_str[:4], date_str[4:6], date_str[6:8]) if len(date_str) == 8 else date_str
    vi_class = 'etag-vi high' if vi and vi > 30 else 'etag-vi'
    snippet = '<a href="JPX_portal_%s.html" class="entry">\n' % date_str
    snippet += '  <span class="entry-date">%s</span>\n  <span class="entry-weekday">%s</span>\n' % (date_disp, weekday)
    snippet += '  <span class="entry-tags">\n    <span class="etag etag-nikkei">日経平均 %s</span>\n    <span class="etag %s">VI %s</span>\n  </span>\n' % (fnum(nikkei), vi_class, vi)
    snippet += '  <span class="entry-arrow">→</span>\n</a>\n'
    return snippet

def update_archive(archive_path, data):
    if not os.path.exists(archive_path):
        print('[render.py] archive.html not found — skipping')
        return False
    meta = data['metadata']
    date_str = meta.get('date', '')
    s01 = data.get('s01', {})
    nikkei = s01.get('nikkei_close', 0)
    vi = s01.get('vi', 0)
    WEEKDAYS = ['月', '火', '水', '木', '金', '土', '日']
    dt = None
    try:
        from datetime import datetime as _dt
        dt = _dt.strptime(date_str, '%Y%m%d')
    except:
        pass
    weekday = WEEKDAYS[dt.weekday()] if dt else ''
    date_disp = '%s.%s.%s' % (date_str[:4], date_str[4:6], date_str[6:8]) if len(date_str) == 8 else date_str
    major_month = meta.get('major_month', '')
    if len(major_month) >= 6:
        section_id = 'archive-list-%s' % major_month[4:6]
    else:
        section_id = 'archive-list-06'
    vi_class = 'etag-vi high' if vi and vi > 30 else 'etag-vi'
    entry = '    <a href="JPX_portal_%s.html" class="entry">\n' % date_str
    entry += '      <span class="entry-date">%s</span>\n      <span class="entry-weekday">%s</span>\n' % (date_disp, weekday)
    entry += '      <span class="entry-tags">\n        <span class="etag etag-nikkei">%s</span>\n        <span class="etag %s">VI %s</span>\n      </span>\n' % (fnum(nikkei) if nikkei else '-', vi_class, vi if vi else '-')
    entry += '      <span class="entry-arrow">&rarr;</span>\n    </a>\n'
    with open(archive_path, 'r', encoding='utf-8') as f:
        html = f.read()
    portal_link = 'JPX_portal_%s.html' % date_str
    if portal_link in html:
        print('[render.py] archive already contains %s — skipping' % date_str)
        return False
    import re
    pattern = r'(<div[^>]*id=["\']%s["\'][^>]*>)' % re.escape(section_id)
    match = re.search(pattern, html)
    if match:
        insert_pos = match.end()
        html = html[:insert_pos] + '\n' + entry + html[insert_pos:]
        print('[render.py] Inserted into %s' % section_id)
    else:
        alt_pat = r'(<div[^>]*id=["\']archive-list-\d+["\'][^>]*>)'
        match = re.search(alt_pat, html)
        if match:
            html = html[:match.end()] + '\n' + entry + html[match.end():]
            print('[render.py] Inserted into first available archive-list')
        else:
            print('[render.py] WARNING: No archive-list section found')
            return False
    with open(archive_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return True

def run(args):
    with open(args.data, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # Load oi_timeseries.json (optional — produced by scripts/extract_oi_timeseries.py)
    data_dir = os.path.dirname(args.data) or '.'
    oi_ts = _load_oi_timeseries(data_dir)
    wt = _load_weekly_trend(data_dir)
    if wt and not wt.get('error'):
        print('[render.py] Loaded weekly_trend: %d weeks' % len(wt.get('weeks', [])))
    if oi_ts:
        print('[render.py] Loaded oi_timeseries: %d days, %d expiries, %d top puts, %d top calls' % (
            oi_ts.get('n_dates', 0),
            len(oi_ts.get('options', {}).get('aggregate', {})),
            len(oi_ts.get('options', {}).get('top_puts', [])),
            len(oi_ts.get('options', {}).get('top_calls', [])),
        ))
    else:
        print('[render.py] oi_timeseries.json not found — 建玉推移 card will show empty state')
    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)
    date_str = data['metadata'].get('date', 'unknown')
    md_path = os.path.join(outdir, 'JPX_market_analysis_%s.md' % date_str)
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(build_markdown(data))
    print('[render.py] Markdown: %s (%.1f KB)' % (md_path, os.path.getsize(md_path) / 1024))
    html_path = os.path.join(outdir, 'index.html')
    html = build_dashboard_html(data, oi_ts=oi_ts, wt=wt)
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print('[render.py] Dashboard: %s (%.1f KB)' % (html_path, os.path.getsize(html_path) / 1024))
    sim_path = os.path.join(outdir, 'pnl_simulator.html')
    with open(sim_path, 'w', encoding='utf-8') as f:
        f.write(build_simulator_html(data))
    print('[render.py] Simulator: %s' % sim_path)
    portal_path = os.path.join(outdir, 'JPX_portal_%s.html' % date_str)
    with open(portal_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print('[render.py] Portal: %s' % portal_path)
    snippet_path = os.path.join(outdir, 'archive_snippet_%s.txt' % date_str)
    with open(snippet_path, 'w', encoding='utf-8') as f:
        f.write(build_archive_snippet(data))
    print('[render.py] Snippet: %s' % snippet_path)
    archive_path = os.path.join(outdir, 'archive.html')
    update_archive(archive_path, data)
    print('\n[render.py] Done.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='JPX Market Analysis - Renderer')
    parser.add_argument('--data', default='data.json', help='Input data.json path')
    parser.add_argument('--outdir', default='.', help='Output directory')
    args = parser.parse_args()
    run(args)
