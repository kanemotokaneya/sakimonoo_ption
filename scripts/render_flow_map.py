#!/usr/bin/env python3
"""Render the "売買推定マップ（価格軸）" card.

Lays each strike on a vertical price axis and shows, side by side, the put and
call flow for the day: bar length = |OI change|, colour = verdict
(green bought / red sold / grey decision-too-weak), with the spot and MaxPain
marked. Inspired by price-axis bubble charts, but carries the buy/sell verdict
those charts lack.
"""
import json


def _verdict(oi_chg, rel):
    if oi_chg is None or rel is None:
        return 'na'
    TH = 0.003
    if oi_chg > 0:
        if rel > TH:
            return 'buy'
        if rel < -TH:
            return 'sell'
        return 'weak'
    if oi_chg < 0:
        # closing flow: colour by which side closed
        if rel < -TH:
            return 'sell'   # long unwind
        if rel > TH:
            return 'buy'    # short cover
        return 'weak'
    return 'na'


def fm_data_script(greeks, indicators=None):
    if not greeks or not greeks.get('expiries'):
        return "window.FM_DATA=null;"
    e = greeks['expiries'][0]
    spot = e.get('spot')
    rows = []
    for r in e.get('per_strike', []):
        k = r['strike']
        rel = r.get('iv_chg_rel_mny')
        rel = rel if rel is not None else r.get('iv_chg_rel')
        pchg = r.get('put_oi_chg') or 0
        cchg = r.get('call_oi_chg') or 0
        if abs(pchg) < 100 and abs(cchg) < 100:
            continue
        rows.append({
            'k': k,
            'p_oi': round(r.get('put_oi', 0) or 0),
            'c_oi': round(r.get('call_oi', 0) or 0),
            'p_chg': round(pchg), 'c_chg': round(cchg),
            'p_v': _verdict(pchg, rel) if abs(pchg) >= 100 else 'na',
            'c_v': _verdict(cchg, rel) if abs(cchg) >= 100 else 'na',
        })
    rows.sort(key=lambda x: -x['k'])
    mp = (indicators or {}).get('max_pain')
    payload = {'spot': spot, 'expiry': e.get('expiry'), 'max_pain': mp,
               'rows': rows, 'T_days': e.get('T_days')}
    return "window.FM_DATA=%s;" % json.dumps(payload, ensure_ascii=False)


FM_CARD_CSS = r"""
.fm-intro{font-size:11.5px;color:var(--sub);line-height:1.6;margin:2px 2px 9px}
.fm-legend{display:flex;gap:12px;flex-wrap:wrap;font-size:10.5px;color:var(--sub);margin:0 2px 8px}
.fm-lg{display:inline-flex;align-items:center;gap:4px}
.fm-sw{width:10px;height:10px;border-radius:2px;display:inline-block}
.fm-grid{width:100%;border-collapse:collapse;font-family:'DM Mono',monospace}
.fm-grid td{padding:0;vertical-align:middle}
.fm-k{width:52px;text-align:right;padding-right:7px!important;font-size:11px;color:#cbd5e1;white-space:nowrap}
.fm-bar-cell{width:44%}
.fm-barwrap{position:relative;height:16px;display:flex;align-items:center}
.fm-barwrap.left{justify-content:flex-end}
.fm-bar{height:12px;border-radius:2px;min-width:1px}
.fm-lbl{font-size:9px;color:var(--sub);padding:0 4px;white-space:nowrap}
.fm-buy{background:#22c55e}.fm-sell{background:#ef4444}
.fm-weak{background:#5b6472}.fm-na{background:#2a3140}
.fm-krow.spot .fm-k{color:#818cf8;font-weight:700}
.fm-krow.spot td{border-top:1px dashed #818cf8;border-bottom:1px dashed #818cf8}
.fm-krow.mp .fm-k{color:#fbbf24}
.fm-hd{font-size:10px;color:var(--sub);text-align:center;padding:2px 0!important}
.fm-note{font-size:11px;color:var(--sub);line-height:1.55;margin:9px 2px 2px}
"""

FM_CARD_JS = r"""
function fmBuild(){
  var D=window.FM_DATA; if(!D||!D.rows||!D.rows.length) return '<div class="insight">データなし</div>';
  var rows=D.rows, spot=D.spot, mp=D.max_pain;
  var maxchg=1;
  rows.forEach(function(r){ maxchg=Math.max(maxchg,Math.abs(r.p_chg),Math.abs(r.c_chg)); });
  // insert a synthetic spot row marker between straddling strikes
  var ks=rows.map(function(r){return r.k;});
  var h='<div class="fm-intro">当日の建玉増減を<b>価格軸（縦＝行使価格）</b>に並べ、'
    +'<span style="color:#22c55e">緑＝買われた</span>／<span style="color:#ef4444">赤＝売られた</span>で色分け。'
    +'左がプット、右がコール、棒の長さ＝増減の大きさ。青破線＝現値、黄＝MaxPain。'
    +'（残存'+(D.T_days!=null?D.T_days+'日':'-')+'）</div>';
  h+='<div class="fm-legend">'
    +'<span class="fm-lg"><span class="fm-sw fm-buy"></span>買われた</span>'
    +'<span class="fm-lg"><span class="fm-sw fm-sell"></span>売られた</span>'
    +'<span class="fm-lg"><span class="fm-sw fm-weak"></span>判定弱い</span></div>';
  h+='<table class="fm-grid">';
  h+='<tr><td class="fm-hd">◀ プット</td><td class="fm-hd">行使価格</td><td class="fm-hd">コール ▶</td></tr>';
  var spotShown=false;
  function bar(chg,v,side){
    var w=Math.round(Math.abs(chg)/maxchg*100);
    var lbl=(chg>0?'+':'')+chg.toLocaleString();
    var b='<div class="fm-bar fm-'+v+'" style="width:'+w+'%"></div>';
    var t='<span class="fm-lbl">'+lbl+'</span>';
    if(side==='left') return '<div class="fm-barwrap left">'+t+b+'</div>';
    return '<div class="fm-barwrap">'+b+t+'</div>';
  }
  for(var i=0;i<rows.length;i++){
    var r=rows[i];
    // spot divider
    if(!spotShown && spot!=null && r.k<spot){
      h+='<tr class="fm-krow spot"><td class="fm-k">'+Math.round(spot).toLocaleString()+'</td><td colspan="2" class="fm-lbl" style="text-align:center">← 現値</td></tr>';
      spotShown=true;
    }
    var cls='fm-krow';
    if(mp!=null && r.k===mp) cls+=' mp';
    var pcell = (Math.abs(r.p_chg)>=100)? bar(r.p_chg,r.p_v,'left') : '<div class="fm-barwrap left"></div>';
    var ccell = (Math.abs(r.c_chg)>=100)? bar(r.c_chg,r.c_v,'right') : '<div class="fm-barwrap"></div>';
    var klbl=r.k.toLocaleString()+(mp!=null&&r.k===mp?' ◆':'');
    h+='<tr class="'+cls+'"><td class="fm-bar-cell">'+pcell+'</td>'
      +'<td class="fm-k">'+klbl+'</td>'
      +'<td class="fm-bar-cell">'+ccell+'</td></tr>';
  }
  h+='</table>';
  h+='<div class="fm-note">「買われた/売られた」は建玉増減×相対IV変化（現値距離を揃えて算出）による推定。'
    +'厚い緑＝新規の買い（ヘッジ/狙い）、厚い赤＝新規の売り（受け皿/オーバーライト）。'
    +'◆＝MaxPain。大きく動いたストライクほど棒が長い。</div>';
  return h;
}
function fmPreview(){
  var D=window.FM_DATA; if(!D||!D.rows) return "var h='<div>データなし</div>';return h;";
  // biggest bought put & call
  var bp=null,bc=null;
  D.rows.forEach(function(r){
    if(r.p_v==='buy' && (!bp||r.p_chg>bp.p_chg)) bp=r;
    if(r.c_v==='buy' && (!bc||r.c_chg>bc.c_chg)) bc=r;
  });
  return '';
}
"""


def preview_flow_map(greeks, indicators=None):
    """Text preview (raw HTML): the single biggest bought put and call today."""
    if not greeks or not greeks.get('expiries'):
        return '<span class="mm-label">データなし</span>'
    e = greeks['expiries'][0]
    bp = bc = None
    for r in e.get('per_strike', []):
        rel = r.get('iv_chg_rel_mny')
        rel = rel if rel is not None else r.get('iv_chg_rel')
        pchg = r.get('put_oi_chg') or 0
        cchg = r.get('call_oi_chg') or 0
        if pchg >= 100 and _verdict(pchg, rel) == 'buy':
            if bp is None or pchg > bp[1]:
                bp = (r['strike'], pchg)
        if cchg >= 100 and _verdict(cchg, rel) == 'buy':
            if bc is None or cchg > bc[1]:
                bc = (r['strike'], cchg)
    tags = []
    if bp:
        tags.append('<span class="tag tag-put">P%s +%d 買</span>' % (format(bp[0], ','), bp[1]))
    if bc:
        tags.append('<span class="tag tag-call">C%s +%d 買</span>' % (format(bc[0], ','), bc[1]))
    if not tags:
        return '<span class="mm-label">本日は大きな新規買いなし</span>'
    return '<span class="mm-label">本日の最大買い</span>' + ''.join(tags)


if __name__ == '__main__':
    import sys
    g = json.load(open(sys.argv[1], encoding='utf-8'))
    print(fm_data_script(g)[:300])
