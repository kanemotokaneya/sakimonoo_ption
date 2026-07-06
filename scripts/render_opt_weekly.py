#!/usr/bin/env python3
"""Render the weekly option OI-by-participant card (who holds which strike)."""
import json

OPTW_CARD_CSS = r"""
.ow-intro{font-size:12px;color:var(--sub);line-height:1.6;margin:2px 2px 10px}
.ow-hl{background:rgba(129,140,248,.12);border:1px solid rgba(129,140,248,.3);border-radius:8px;padding:9px 11px;margin:0 0 12px;font-size:12.5px;line-height:1.6}
.ow-k{font-family:Outfit;font-weight:600;font-size:13px;margin:12px 2px 5px;color:var(--text)}
.ow-row{display:grid;grid-template-columns:38px 1fr;gap:6px;margin:3px 0;font-size:11.5px}
.ow-lab{color:var(--sub);font-family:'DM Mono',monospace;padding-top:3px}
.ow-cell{display:flex;flex-wrap:wrap;gap:3px}
.ow-t{display:inline-block;padding:1px 6px;border-radius:6px;font-size:11px}
.ow-buy{background:rgba(34,197,94,.14);color:#86efac}
.ow-sel{background:rgba(248,113,113,.14);color:#fca5a5}
.ow-dom{outline:1px solid rgba(248,113,113,.5)}
.ow-note{font-size:11px;color:var(--sub);line-height:1.55;margin:8px 2px 2px}
.ow-psum{font-size:11.5px;color:var(--sub);margin:2px 2px;line-height:1.7}
.ow-psum b{color:var(--text)}
"""


def _short(name):
    return str(name).replace('証券', '').replace('クリアリン', 'クリア').replace('グローバル', 'G')[:6]


def preview_opt_weekly(o):
    if not o or not o.get('strikes'):
        return '<span class="mm-label">週次OP建玉 未取込</span>'
    nb = (o.get('notable') or [{}])[0]
    txt = '%s P70k みずほ買い持ち' % (o.get('as_of', ''))
    return ('<div class="mini-metrics"><div class="mini-metric">'
            '<div class="mm-label">参加者別OP建玉（%s現在）</div>'
            '<div class="mm-value" style="font-size:12px;color:var(--accent)">'
            '誰がどの行使価格を持つか ▼</div></div></div>' % o.get('as_of', ''))


def optw_data_script(o):
    return 'window.OPTW_DATA = ' + json.dumps(o or {}, ensure_ascii=False) + ';\n'


OPTW_CARD_JS = r"""
function owTag(b,q,cat,buy){
  var cls = buy ? 'ow-buy' : 'ow-sel';
  if(cat==='domestic') cls += ' ow-dom';
  var nm = String(b).replace('証券','').replace('クリアリン','クリア').replace('グローバル','G');
  if(nm.length>6) nm = nm.slice(0,6);
  return '<span class="ow-t '+cls+'">'+nm+' '+Math.round(q)+'</span>';
}
function owCells(list, buy){
  if(!list||!list.length) return '<span class="ow-t">—</span>';
  return list.slice(0,3).map(function(x){return owTag(x[0],x[1],x[2],buy);}).join('');
}
function owBuildHTML(){
  var O = window.OPTW_DATA || {};
  var st = O.strikes || {};
  var keys = Object.keys(st).map(Number).sort(function(a,b){return b-a;});
  if(!keys.length) return '<div class="insight">週次OP建玉データがありません。</div>';
  var h = '';
  h += '<div class="ow-intro">OSE週次「日経平均オプション取引参加者別建玉残高」（'+(O.as_of||'')+'現在）。各行使価格で<b>誰がネットで買い持ち（買超）／売り持ち（売超）</b>かを示します。<span class="ow-t ow-buy">緑=買い持ち</span> <span class="ow-t ow-sel">赤=売り持ち</span>、<b>赤枠=国内勢</b>。</div>';
  // headline: Mizuho net long P70000 if present
  var p70 = st['70000'];
  if(p70 && p70.put && p70.put.buyers && p70.put.buyers.length){
    var top = p70.put.buyers[0];
    h += '<div class="ow-hl">📌 <b>P70,000 プット買い持ちの筆頭は '+String(top[0]).replace('証券','')+'（'+Math.round(top[1])+'枚）</b>。売り持ちは海外勢（'+(p70.put.sellers[0]?String(p70.put.sellers[0][0]).replace('証券',''):'')+'等）。国内が下方プットを買い＝ヘッジ、海外が書き手、という構図が建玉でも確認できます。</div>';
  }
  for(var i=0;i<keys.length;i++){
    var k = keys[i]; var sd = st[String(k)];
    h += '<div class="ow-k">行使価格 '+k.toLocaleString()+'</div>';
    h += '<div class="ow-row"><div class="ow-lab">P買</div><div class="ow-cell">'+owCells(sd.put.buyers,true)+'</div></div>';
    h += '<div class="ow-row"><div class="ow-lab">P売</div><div class="ow-cell">'+owCells(sd.put.sellers,false)+'</div></div>';
    h += '<div class="ow-row"><div class="ow-lab">C買</div><div class="ow-cell">'+owCells(sd.call.buyers,true)+'</div></div>';
    h += '<div class="ow-row"><div class="ow-lab">C売</div><div class="ow-cell">'+owCells(sd.call.sellers,false)+'</div></div>';
  }
  // participant summary (net across strikes)
  var pt = O.participants || {};
  var arr = Object.keys(pt).map(function(b){return [b, pt[b]];});
  arr.sort(function(a,b){return (Math.abs(b[1].put)+Math.abs(b[1].call))-(Math.abs(a[1].put)+Math.abs(a[1].call));});
  h += '<div class="ow-k">主な参加者のネット建玉（買い持ち＋／売り持ち−）</div>';
  for(var j=0;j<Math.min(arr.length,6);j++){
    var b = arr[j][0], d = arr[j][1];
    var tag = '';
    if(d.put>0 && d.call<0) tag='＝プット買い×コール売り（防御的・カラー/ヘッジ）';
    else if(d.put<0 && d.call>0) tag='＝プット売り×コール買い（書き手/強気寄り）';
    else if(d.put<0 && d.call<0) tag='＝両建て売り（プレミアム収受）';
    h += '<div class="ow-psum"><b>'+String(b).replace('証券','')+'</b>：P'+(d.put>=0?'+':'')+Math.round(d.put)+' / C'+(d.call>=0?'+':'')+Math.round(d.call)+' <span style="color:var(--sub)">'+tag+'</span></div>';
  }
  h += '<div class="ow-note">建玉のネット方向は当日のJ-NET手口（日次）と違い、週末時点で「実際に誰がどちら側を保有しているか」を表します。売買区分のある確報値なので、方向推定の"答え合わせ"に使えます。</div>';
  return h;
}
function owRender(card){
  var d = card.querySelector('.card-detail');
  if(d) d.innerHTML = owBuildHTML();
}
"""


def detail_opt_weekly_js(o):
    return "return owBuildHTML();"
