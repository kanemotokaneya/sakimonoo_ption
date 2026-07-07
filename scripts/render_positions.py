#!/usr/bin/env python3
"""Render the merged per-participant weekly positioning card
(futures direction + option put/call in one place, with a plain read)."""
import json

POS_CARD_CSS = r"""
.ps-intro{font-size:12px;color:var(--sub);line-height:1.6;margin:2px 2px 10px}
.ps-tbl{width:100%;border-collapse:collapse;font-size:12px}
.ps-tbl th{color:var(--sub);font-weight:600;text-align:right;padding:6px 5px;border-bottom:1px solid var(--border);font-size:11px}
.ps-tbl th:first-child{text-align:left}
.ps-tbl td{padding:7px 5px;border-bottom:1px solid rgba(38,44,58,.5);text-align:right;font-family:'DM Mono',monospace}
.ps-tbl td:first-child{text-align:left;font-family:'Noto Sans JP',sans-serif}
.ps-pos{color:#86efac}.ps-neg{color:#fca5a5}.ps-zero{color:var(--sub)}
.ps-read{font-size:10.5px;color:var(--sub);font-family:'Noto Sans JP',sans-serif;line-height:1.4}
.ps-cat{font-size:10px;color:var(--sub)}
.ps-note{font-size:11px;color:var(--sub);line-height:1.55;margin:10px 2px 2px}
"""


def pos_data_script(p):
    return 'window.POS_DATA = ' + json.dumps(p or {}, ensure_ascii=False) + ';\n'


def preview_positions(p):
    if not p or not p.get('rows'):
        return '<span class="mm-label">統合ポジション 未取込</span>'
    return ('<div class="mini-metrics"><div class="mini-metric">'
            '<div class="mm-label">大口の先物＋OPを一括（%s）</div>'
            '<div class="mm-value" style="font-size:12px;color:var(--accent)">'
            '先物の向き × OPの向き ▼</div></div></div>' % (p.get('opt_as_of', '')))


POS_CARD_JS = r"""
function psNum(x){
  if(x===0||x===null||x===undefined) return '<span class="ps-zero">0</span>';
  var c = x>0 ? 'ps-pos' : 'ps-neg';
  return '<span class="'+c+'">'+(x>0?'+':'')+x.toLocaleString()+'</span>';
}
function psRead(f,p,c){
  var FB=3000, OB=200;  // "big" thresholds
  var fl = f>=FB, fs = f<=-FB;
  var pl = p>=OB, psh = p<=-OB, cl = c>=OB, csh = c<=-OB;
  if(fl && csh && !pl) return 'ロング＋コール売り＝カバードコール（上値でプレミアム収受）';
  if(fl && pl) return 'ロング＋プット買い＝保険付きロング（ヘッジ）';
  if(fs && pl) return 'ショート＋プット買い＝一貫して弱気（下方）';
  if(fs && csh) return 'ショート＋コール売り＝弱気（戻り売り）';
  if(psh && cl) return 'プット売り×コール買い＝書き手/在庫（強気寄り）';
  if(psh && Math.abs(p)>=Math.abs(c)) return 'プット書き手（プレミアム収受・下値の受け皿）';
  if(pl && csh) return 'プット買い×コール売り＝下方カラー（防御的）';
  if(fl) return '先物ロング中心';
  if(fs) return '先物ショート中心';
  if(cl) return 'コール買い（上値取り）';
  return '—';
}
function psBuildHTML(){
  var P = window.POS_DATA || {};
  var rows = P.rows || [];
  if(!rows.length) return '<div class="insight">週次データ（先物・OP）が揃うと表示されます。</div>';
  var h = '';
  h += '<div class="ps-intro">大口ごとに<b>先物の向き（'+(P.fut_limgetsu||'')+'・N225ラージ）</b>と<b>オプションのネット建玉（'+(P.opt_as_of||'')+'・P/C）</b>を1か所に。両者が同じ向き＝方向性、逆向き＝ヘッジ/カラー、と読めます。<span class="ps-pos">緑=買い越し/ロング</span> <span class="ps-neg">赤=売り越し/ショート</span>。</div>';
  h += '<table class="ps-tbl"><thead><tr><th>参加者</th><th>先物</th><th>P</th><th>C</th></tr></thead><tbody>';
  for(var i=0;i<rows.length;i++){
    var r = rows[i];
    var nm = String(r.broker).replace('證券','').replace('証券','').replace('クリアリン','クリア');
    h += '<tr>'
       + '<td>'+nm+'<div class="ps-cat">'+(r.cat||'')+'</div></td>'
       + '<td>'+psNum(r.fut)+'</td><td>'+psNum(r.put)+'</td><td>'+psNum(r.call)+'</td>'
       + '</tr>';
    h += '<tr><td colspan="4" class="ps-read">↳ '+psRead(r.fut,r.put,r.call)+'</td></tr>';
  }
  h += '</tbody></table>';
  h += '<div class="ps-note">先物は9月限・OPは7月限と限月が異なるため、水準の単純比較でなく「向きの組み合わせ」を読むのが要点。OPは売買区分のある確報建玉、先物は投資部門別建玉（いずれも週次・'+(P.opt_as_of||'')+'時点）。</div>';
  return h;
}
function posRender(card){
  var d = card.querySelector('.card-detail');
  if(d) d.innerHTML = psBuildHTML();
}
"""


def detail_positions_js(p):
    return "return psBuildHTML();"
