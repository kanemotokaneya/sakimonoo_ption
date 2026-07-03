#!/usr/bin/env python3
"""
render_jnet.py — "J-NET手口(クロス)" card for the dashboard.

Shows per-broker J-NET (off-auction / cross) futures volume for the day, with
UBS highlighted, plus a small history chart of UBS cross volume vs spot so the
"UBS crosses often cap price" lore can be tested against subsequent price
action over time.

J-NET has NO buy/sell split — this is VOLUME only, not direction.
"""
import json

JNET_CARD_CSS = r"""
.jn-wrap{font-family:'Noto Sans JP',sans-serif}
.jn-banner{font-size:12.5px;color:#c7d2fe;border:1px solid rgba(129,140,248,.4);background:rgba(129,140,248,.10);border-radius:9px;padding:9px 11px;margin:0 0 11px;line-height:1.6}
.jn-banner b{font-weight:700}
.jn-sec{font-family:Outfit;font-weight:600;color:var(--sub);font-size:12px;margin:12px 2px 6px}
.jn-svg-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--border);border-radius:10px;background:#141821;padding:6px 2px}
.jn-scroll{overflow-x:auto;border:1px solid var(--border);border-radius:10px;-webkit-overflow-scrolling:touch}
.jn-tbl{border-collapse:separate;border-spacing:0;width:100%;font-size:13px}
.jn-tbl th{position:sticky;top:0;background:#1d2230;color:var(--sub);font-weight:500;text-align:right;padding:8px 10px;font-size:12px;white-space:nowrap}
.jn-tbl th:first-child{text-align:left}
.jn-tbl td{padding:8px 10px;border-bottom:1px solid var(--border);text-align:right;font-family:'DM Mono',monospace;white-space:nowrap}
.jn-tbl td:first-child{text-align:left;font-family:'Noto Sans JP',sans-serif}
.jn-ubs td{background:rgba(245,158,11,.14)}
.jn-ocbig td{background:rgba(129,140,248,.12)}
.jn-leg{display:inline-block;padding:1px 6px;border-radius:6px;font-size:11px;margin:1px}
.jn-dom{background:rgba(248,113,113,.16);color:#fca5a5}
.jn-ovs{background:rgba(96,165,250,.16);color:#93c5fd}
.jn-x{color:var(--sub);margin:0 2px;font-size:10px}
.jn-note{font-size:12px;color:var(--sub);margin:8px 2px;line-height:1.6}
"""

JNET_CARD_JS = r"""
function jnNum(x){ return (x||0).toLocaleString('ja-JP'); }
function jnFindUBS(bro){
  for(var k in bro){ if(k.indexOf('ＵＢＳ')>=0 || k.indexOf('UBS')>=0) return k; }
  return null;
}
function jnHistChart(J){
  var hist = J.history || {};
  var dates = Object.keys(hist).sort();
  if(!dates.length) return '';
  // UBS futures volume bars + spot line
  var vols=[], spots=[];
  for(var i=0;i<dates.length;i++){
    var hd = hist[dates[i]]; var bro = (hd&&hd.brokers)||{};
    var uk = jnFindUBS(bro);
    vols.push(uk ? (bro[uk].fut||0) : 0);
    spots.push(hd ? (hd.spot||null) : null);
  }
  var W = Math.max(dates.length*54+40, 300), H=150, pad=26;
  var maxv=1; for(var i=0;i<vols.length;i++){ maxv=Math.max(maxv,vols[i]); }
  var sp=spots.filter(function(x){return x!=null;});
  var smin=Math.min.apply(null,sp), smax=Math.max.apply(null,sp);
  if(smin===smax){ smin-=100; smax+=100; }
  var bw=(W-pad*2)/dates.length;
  var s='<svg width="'+W+'" height="'+H+'" viewBox="0 0 '+W+' '+H+'">';
  // bars
  for(var i=0;i<dates.length;i++){
    var bh=(H-pad*2)*(vols[i]/maxv);
    var x=pad+i*bw+bw*0.2, y=H-pad-bh, w=bw*0.6;
    s+='<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+bh+'" fill="#f59e0b" opacity="0.85" rx="2"/>';
    s+='<text x="'+(x+w/2)+'" y="'+(y-3)+'" fill="#f59e0b" font-size="9" text-anchor="middle">'+jnNum(vols[i])+'</text>';
    s+='<text x="'+(pad+i*bw+bw/2)+'" y="'+(H-8)+'" fill="#828ca0" font-size="9" text-anchor="middle">'+dates[i].slice(4,6)+'/'+dates[i].slice(6,8)+'</text>';
  }
  // spot line
  function sy(v){ return pad + (H-pad*2)*(1-(v-smin)/(smax-smin)); }
  var pts='';
  for(var i=0;i<dates.length;i++){
    if(spots[i]==null) continue;
    var cx=pad+i*bw+bw/2, cy=sy(spots[i]);
    pts += (pts?' ':'')+cx+','+cy;
    s+='<circle cx="'+cx+'" cy="'+cy+'" r="3" fill="#22d3ee"/>';
  }
  if(pts.indexOf(' ')>=0) s+='<polyline points="'+pts+'" fill="none" stroke="#22d3ee" stroke-width="1.5"/>';
  s+='</svg>';
  return s;
}
function jnBuildHTML(){
  var J = window.JNET_DATA;
  if(!J || J.error || !J.brokers || !J.brokers.length){
    return '<div class="jn-note">J-NETデータなし — extract_jnet.py を実行して jnet.json を生成してください。</div>';
  }
  var h = '<div class="jn-wrap">';
  h += '<div class="jn-banner">J-NET＝立会外（クロス）取引。<b>売買区分なし＝出来高のみ</b>です。UBS等のクロスが「蓋」になるかは、出来高スパイクと<b>翌日以降の値動き</b>を照合して事後に確認してください（手口だけで売り＝蓋とは断定できません）。</div>';

  // UBS focus + history
  var hist = J.history || {};
  var nd = Object.keys(hist).length;
  h += '<div class="jn-sec">UBSのJ-NET先物クロス推移（橙）と現値（水色）</div>';
  if(nd >= 1){
    h += '<div class="jn-svg-wrap">'+jnHistChart(J)+'</div>';
    if(nd < 3){ h += '<div class="jn-note">※ まだ'+nd+'日分。数日貯まると「UBSの出来高が膨らんだ翌日に、現値がそこで止まったか」が見えてきます。</div>'; }
  }

  // today's table
  h += '<div class="jn-sec">本日のJ-NET先物 出来高ランキング（'+J.date.slice(4,6)+'/'+J.date.slice(6,8)+'）</div>';
  h += '<div class="jn-scroll"><table class="jn-tbl"><thead><tr>'
     + '<th>参加者</th><th>ラージ</th><th>ミニ</th><th>先物計</th></tr></thead><tbody>';
  var rows = J.brokers.slice(0, 12);
  for(var i=0;i<rows.length;i++){
    var r = rows[i];
    var isU = (r.broker.indexOf('ＵＢＳ')>=0 || r.broker.indexOf('UBS')>=0);
    h += '<tr class="'+(isU?'jn-ubs':'')+'"><td>'+(isU?'★ ':'')+r.broker+'</td>'
       + '<td>'+jnNum(r.large)+'</td><td>'+jnNum(r.mini)+'</td><td>'+jnNum(r.fut)+'</td></tr>';
  }
  h += '</tbody></table></div>';
  h += '<div class="jn-note">ラージ＝機関のブロック/クロスが中心。ミニはリテール（SBI・楽天等）が大半。「蓋」を読むならラージ側のクロスに注目。</div>';

  // notable option cross blocks by strike (dynamic — whoever moved big today)
  var oc = J.option_crosses || [];
  if(oc.length){
    h += '<div class="jn-sec">本日の大口オプション立会外クロス（ストライク別）</div>';
    h += '<div class="jn-scroll"><table class="jn-tbl"><thead><tr>'
       + '<th>ストライク</th><th>枚数</th><th>当事者</th></tr></thead><tbody>';
    for(var i=0;i<oc.length;i++){
      var c = oc[i];
      var star = c.domestic_vs_overseas ? '★ ' : '';
      var legs = (c.legs||[]).map(function(l){
        var cc = l.cat==='domestic' ? 'jn-dom' : 'jn-ovs';
        return '<span class="jn-leg '+cc+'">'+l.broker.replace('証券','').replace('クリアリン','')+' '+jnNum(l.vol)+'</span>';
      }).join('<span class="jn-x">⟷</span>');
      h += '<tr class="'+(c.domestic_vs_overseas?'jn-ocbig':'')+'">'
         + '<td>'+star+c.side+jnNum(c.strike)+'</td>'
         + '<td>'+jnNum(c.size)+'</td><td>'+legs+'</td></tr>';
    }
    h += '</tbody></table></div>';
    h += '<div class="jn-note">★＝国内⟷海外の大口ブロック。<b>売買区分なし</b>なので「国内が買った/売った」は断定不可。今日のみずほ⟷ＡＢＮのような形は、当日のOI増減（我々のグリークスカード）と<b>翌日の値動き</b>で「保険買いか・売り抜けか」を事後判定してください。</div>';
  }
  h += '</div>';
  return h;
}
function jnRender(card){
  if(!card) return;
  var host = card.querySelector('.card-detail');
  if(host) host.innerHTML = jnBuildHTML();
}
"""


def jnet_data_script(jnet, history=None):
    data = dict(jnet or {})
    if history is not None:
        data['history'] = history
    # Concatenated INSIDE the dashboard's single <script> block — must NOT wrap
    # itself in <script> tags (nesting would close the outer script early and
    # break every card toggle). Return raw JS, like greeks_data_script.
    return 'window.JNET_DATA = ' + json.dumps(data, ensure_ascii=False) + ';\n'


def preview_jnet(jnet):
    if not jnet or jnet.get('error') or not jnet.get('brokers'):
        return ('<div class="card-stat"><span class="label">J-NET</span>'
                '<span class="value">—</span></div>')
    ubs = next((r for r in jnet['brokers']
                if 'ＵＢＳ' in r['broker'] or 'UBS' in r['broker']), None)
    top = jnet['brokers'][0]
    ubs_v = ('%s枚' % format(int(ubs['fut']), ',')) if ubs else '—'
    return (
        '<div class="card-stat"><span class="label">UBS先物クロス</span>'
        '<span class="value">%s</span></div>'
        '<div class="card-stat"><span class="label">首位</span>'
        '<span class="value" style="font-size:13px">%s</span></div>'
        '<div class="card-stat"><span class="label">参加者</span>'
        '<span class="value">%d社</span></div>'
        % (ubs_v, top['broker'], len(jnet['brokers'])))


def detail_jnet_js(jnet):
    return "return jnBuildHTML();"
