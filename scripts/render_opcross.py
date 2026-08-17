#!/usr/bin/env python3
"""Standalone card for today's large J-NET option cross blocks (by strike).
Reads the already-embedded window.JNET_DATA.option_crosses — no extra data."""


OPCROSS_CARD_CSS = r"""
.oc-sec{font-family:Outfit;font-weight:600;color:var(--sub);font-size:12px;margin:2px 2px 8px}
.oc-scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.oc-tbl{width:100%;border-collapse:collapse;font-size:12px}
.oc-tbl th{color:var(--sub);font-weight:600;text-align:left;padding:6px 6px;border-bottom:1px solid var(--border);font-size:11px}
.oc-tbl td{padding:8px 6px;border-bottom:1px solid rgba(38,44,58,.5);vertical-align:top}
.oc-tbl td:nth-child(1){font-family:'DM Mono',monospace;white-space:nowrap}
.oc-tbl td:nth-child(2){font-family:'DM Mono',monospace;text-align:right;white-space:nowrap}
.oc-big td{background:rgba(129,140,248,.12)}
.oc-leg{display:inline-block;padding:1px 6px;border-radius:6px;font-size:11px;margin:1px}
.oc-dom{background:rgba(248,113,113,.16);color:#fca5a5}
.oc-ovs{background:rgba(96,165,250,.16);color:#93c5fd}
.oc-x{color:var(--sub);margin:0 2px;font-size:10px}
.oc-exp{color:var(--sub);font-size:10.5px;white-space:nowrap}
.oc-solo{font-size:9.5px;color:var(--sub);margin-left:4px;padding:0 4px;border:1px solid var(--border);border-radius:4px}
.oc-note{font-size:11px;color:var(--sub);line-height:1.55;margin:10px 2px 2px}
.oc-empty{font-size:12px;color:var(--sub);line-height:1.6}
"""


OPCROSS_CARD_JS = r"""
function ocNum(n){ return (n===null||n===undefined)?'0':Number(n).toLocaleString(); }
function ocBuildHTML(){
  var J = window.JNET_DATA || {};
  var oc = J.option_crosses || [];
  var dt = J.date ? (J.date.slice(4,6)+'/'+J.date.slice(6,8)) : '';
  var h = '<div class="oc-sec">本日の大口オプション立会外取引（'+dt+'・限月×ストライク別）</div>';
  if(!oc.length){
    h += '<div class="oc-empty">本日は目立つ大口オプションクロスはありません（小口のみ）。大きなクロスが出た日はここにストライク別で並びます。</div>';
    return h;
  }
  h += '<div class="oc-scroll"><table class="oc-tbl"><thead><tr>'
     + '<th>限月</th><th>ストライク</th><th>枚数</th><th>当事者</th></tr></thead><tbody>';
  for(var i=0;i<oc.length;i++){
    var c = oc[i];
    var star = c.domestic_vs_overseas ? '★ ' : '';
    var legs = (c.legs||[]).map(function(l){
      var cc = (l.cat==='domestic') ? 'oc-dom' : 'oc-ovs';
      return '<span class="oc-leg '+cc+'">'+String(l.broker).replace('証券','').replace('クリアリン','クリア')+' '+ocNum(l.vol)+'</span>';
    }).join('<span class="oc-x">⟷</span>');
    var exp = c.expiry ? ('20'+String(c.expiry).slice(0,2)+'/'+String(c.expiry).slice(2,4)) : '—';
    var kind = c.is_cross ? '' : '<span class="oc-solo">単独</span>';
    h += '<tr class="'+(c.domestic_vs_overseas?'oc-big':'')+'">'
       + '<td class="oc-exp">'+exp+'</td>'
       + '<td>'+star+c.side+ocNum(c.strike)+'</td>'
       + '<td>'+ocNum(c.size)+kind+'</td><td>'+legs+'</td></tr>';
  }
  h += '</tbody></table></div>';
  h += '<div class="oc-note">★＝国内⟷海外の大口ブロック。<span class="oc-leg oc-dom">赤=国内</span> <span class="oc-leg oc-ovs">青=海外/HF</span>。'
     + '枚数は<b>最大の当事者の枚数</b>（クロスは同じ玉を売買両側で数えるため合算しない）。'
     + '<b>単独</b>＝相手方が特定できない大口で、対当する枚数が見当たらないもの。'
     + '<b>売買区分なし</b>のため「買い/売り」は断定不可。建玉の増減（クロス枚数と建玉増が一致すれば新規、しなければ手仕舞い/移転を含む）と翌日以降の値動きで事後判定してください。</div>';
  return h;
}
function ocRender(card){
  if(!card) return;
  var host = card.querySelector('.card-detail');
  if(host) host.innerHTML = ocBuildHTML();
}
"""


def preview_opcross(jnet):
    oc = (jnet or {}).get('option_crosses', []) if jnet else []
    if not oc:
        return '<span class="mm-label">本日 大口OPクロスなし</span>'
    top = oc[0]
    legs = top.get('legs', [])
    lead = legs[0]['broker'].replace('証券', '').replace('クリアリン', 'クリア') if legs else ''
    label = '%s%s ×%s' % (top['side'], format(int(top['strike']), ','), format(int(top['size']), ','))
    return ('<div class="mini-metrics"><div class="mini-metric">'
            '<div class="mm-label">本日最大のOPクロス</div>'
            '<div class="mm-value" style="font-size:12px;color:var(--accent)">%s（%s）</div>'
            '</div></div>' % (label, lead))


def detail_opcross_js(jnet):
    return "return ocBuildHTML();"
