#!/usr/bin/env python3
"""Render the merged per-participant大口 card: weekly futures + weekly options
(建玉/stock) and today's J-NET futures + option crosses (出来高/flow), in one
place, with a plain read of each player's stance."""
import json

POS_CARD_CSS = r"""
.ps-intro{font-size:12px;color:var(--sub);line-height:1.6;margin:2px 2px 12px}
.ps-p{border:1px solid var(--border);border-radius:10px;padding:9px 11px;margin:7px 0;background:#141822}
.ps-nm{font-family:Outfit;font-weight:600;font-size:13.5px;margin-bottom:5px}
.ps-nm .ps-cat{font-size:10px;color:var(--sub);font-weight:400;margin-left:6px}
.ps-line{display:flex;gap:6px;font-size:11.5px;line-height:1.7;flex-wrap:wrap}
.ps-tag{color:var(--sub);font-family:'DM Mono',monospace;min-width:74px}
.ps-v{font-family:'DM Mono',monospace}
.ps-pos{color:#86efac}.ps-neg{color:#fca5a5}.ps-zero{color:var(--sub)}
.ps-flow{color:#93c5fd}
.ps-read{font-size:10.5px;color:#cbd5e1;line-height:1.45;margin-top:5px;border-top:1px solid rgba(38,44,58,.6);padding-top:5px}
.ps-note{font-size:11px;color:var(--sub);line-height:1.55;margin:10px 2px 2px}
.ps-det{margin-top:12px;border:1px solid var(--border);border-radius:10px;padding:8px 11px;background:#141822}
.ps-det summary{font-size:12px;font-weight:600;color:var(--accent);cursor:pointer}
.ps-k{font-family:Outfit;font-weight:600;font-size:12.5px;margin:10px 0 4px}
.ps-t{display:inline-block;padding:1px 6px;border-radius:6px;font-size:11px;margin:1px}
.ps-tb{background:rgba(34,197,94,.14);color:#86efac}
.ps-ts{background:rgba(248,113,113,.14);color:#fca5a5}
.ps-td{outline:1px solid rgba(248,113,113,.5)}
"""


def pos_data_script(p):
    return 'window.POS_DATA = ' + json.dumps(p or {}, ensure_ascii=False) + ';\n'


def preview_positions(p):
    if not p or not p.get('rows'):
        return '<span class="mm-label">統合ポジション 未取込</span>'
    return ('<div class="mini-metrics"><div class="mini-metric">'
            '<div class="mm-label">大口の週次(建玉)＋本日(出来高)を集約</div>'
            '<div class="mm-value" style="font-size:12px;color:var(--accent)">'
            '先物×OP×週次×日次 ▼</div></div></div>')


POS_CARD_JS = r"""
function psSigned(x){
  if(x===0||x===null||x===undefined) return '<span class="ps-zero">0</span>';
  return '<span class="'+(x>0?'ps-pos':'ps-neg')+'">'+(x>0?'+':'')+x.toLocaleString()+'</span>';
}
function psRead(r){
  var FB=3000, OB=200, f=r.fut, p=r.put, c=r.call;
  var fl=f>=FB, fs=f<=-FB, pl=p>=OB, psh=p<=-OB, cl=c>=OB, csh=c<=-OB;
  var base='';
  if(fl && csh && !pl) base='週次: ロング＋コール売り＝カバードコール';
  else if(fl && pl) base='週次: ロング＋プット買い＝保険付きロング';
  else if(fs && pl) base='週次: ショート＋プット買い＝一貫して弱気';
  else if(fs && csh) base='週次: ショート＋コール売り＝戻り売り';
  else if(psh && cl) base='週次: プット売り×コール買い＝書き手/在庫';
  else if(psh && Math.abs(p)>=Math.abs(c)) base='週次: プット書き手（下値の受け皿）';
  else if(pl && csh) base='週次: 下方カラー（防御的）';
  else if(fl) base='週次: 先物ロング中心';
  else if(fs) base='週次: 先物ショート中心';
  else base='週次: 中立〜小口';
  // flag divergence with today's option flow
  if(r.day_opt_top){
    var isPut = r.day_opt_top.charAt(0)==='P';
    if(fl && isPut) base += ' ／ 本日はプットを大量クロス＝週次ロングにヘッジ or 反対の動き（要事後確認）';
    else if(fs && isPut) base += ' ／ 本日もプット関与＝下方目線と整合的';
    else base += ' ／ 本日 '+r.day_opt_top+' に関与';
  }
  return base;
}
function psBuildHTML(){
  var P = window.POS_DATA || {};
  var rows = P.rows || [];
  if(!rows.length) return '<div class="insight">週次データ（先物・OP）が揃うと表示されます。</div>';
  var h = '';
  h += '<div class="ps-intro">大口ごとに<b>週次の建玉（ストック）</b>と<b>本日のJ-NET出来高（フロー）</b>を1か所に。'
     + '週次先物='+(P.fut_limgetsu||'')+'・週次OP='+(P.opt_as_of||'')+'・本日='+(P.day_date||'')+'。'
     + '<span class="ps-pos">緑=買い越し/ロング</span> <span class="ps-neg">赤=売り越し/ショート</span> <span class="ps-flow">青=本日フロー</span>。</div>';
  for(var i=0;i<rows.length;i++){
    var r = rows[i];
    var nm = String(r.broker).replace('證券','').replace('証券','').replace('クリアリン','クリア');
    h += '<div class="ps-p">';
    h += '<div class="ps-nm">'+nm+'<span class="ps-cat">'+(r.cat||'')+'</span></div>';
    // weekly (stock)
    h += '<div class="ps-line"><span class="ps-tag">週次·先物</span>'+psSigned(r.fut)
       + '<span class="ps-tag" style="min-width:44px">P</span>'+psSigned(r.put)
       + '<span class="ps-tag" style="min-width:44px">C</span>'+psSigned(r.call)+'</div>';
    // today (flow)
    var dopt = r.day_opt_lots ? ('<span class="ps-flow ps-v">'+r.day_opt_lots.toLocaleString()+'枚</span>'
              + (r.day_opt_top?' <span class="ps-flow ps-v" style="font-size:10.5px">('+r.day_opt_top+')</span>':'')) : '<span class="ps-zero">0</span>';
    h += '<div class="ps-line"><span class="ps-tag">本日·ラージ</span><span class="ps-flow ps-v">'+(r.day_fut||0).toLocaleString()+'</span>'
       + '<span class="ps-tag" style="min-width:44px">OP</span>'+dopt+'</div>';
    h += '<div class="ps-read">↳ '+psRead(r)+'</div>';
    h += '</div>';
  }
  h += '<div class="ps-note">週次＝売買区分のある確報建玉（ストック）。本日＝J-NET立会外の出来高（フロー・売買区分なし）。ラージ＝機関のブロック/クロス。両者の向きが揃うほど方向性、ズレるほどヘッジ/転換の可能性。方向は翌日の値動きで事後確認。</div>';
  // strike-level weekly option holdings (absorbed from the old OP建玉 card)
  var OW = window.OPTW_DATA || {};
  var st = OW.strikes || {};
  var ks = Object.keys(st).map(Number).sort(function(a,b){return b-a;});
  if(ks.length){
    h += '<details class="ps-det"><summary>ストライク別：誰がどの行使価格を持つか（週次OP・'+(OW.as_of||'')+'）</summary>';
    for(var i2=0;i2<ks.length;i2++){
      var k2 = ks[i2]; var sd = st[String(k2)];
      var cell = function(list, buy){
        if(!list||!list.length) return '<span class="ps-t">—</span>';
        return list.slice(0,3).map(function(x){
          var cls = buy ? 'ps-t ps-tb' : 'ps-t ps-ts';
          if(x[2]==='domestic') cls += ' ps-td';
          var nm2 = String(x[0]).replace('証券','').replace('クリアリン','クリア'); if(nm2.length>6) nm2=nm2.slice(0,6);
          return '<span class="'+cls+'">'+nm2+' '+Math.round(x[1])+'</span>';
        }).join('');
      };
      h += '<div class="ps-k">行使価格 '+k2.toLocaleString()+'</div>';
      h += '<div class="ps-line"><span class="ps-tag" style="min-width:44px">P買</span><span>'+cell(sd.put.buyers,true)+'</span></div>';
      h += '<div class="ps-line"><span class="ps-tag" style="min-width:44px">P売</span><span>'+cell(sd.put.sellers,false)+'</span></div>';
      h += '<div class="ps-line"><span class="ps-tag" style="min-width:44px">C買</span><span>'+cell(sd.call.buyers,true)+'</span></div>';
      h += '<div class="ps-line"><span class="ps-tag" style="min-width:44px">C売</span><span>'+cell(sd.call.sellers,false)+'</span></div>';
    }
    h += '<div class="ps-note">緑=買い持ち（買超）／赤=売り持ち（売超）、赤枠=国内勢。売買区分のある確報値なので、日次の方向推定の答え合わせに使えます。</div>';
    h += '</details>';
  }
  return h;
}
function posRender(card){
  var d = card.querySelector('.card-detail');
  if(d) d.innerHTML = psBuildHTML();
}
"""


def detail_positions_js(p):
    return "return psBuildHTML();"
