#!/usr/bin/env python3
"""
render_greeks.py — Greeks / GEX dashboard card for the JPX board.

Consumes greeks.json (produced by extract_greeks.py) and renders:
  - preview: front-expiry zero-gamma flip (Convention A & B) + net-gamma sign
  - detail : expiry tabs, A/B convention toggle, KPI strip, a GEX profile
             SVG (positive=stabilising/green, negative=accelerating/red,
             spot line, zero-gamma marker) and a per-strike greeks table.

Vanilla only: no template literals, inline onclick handlers use a delegated
listener with stopPropagation so taps inside the card don't collapse it.
Wired into render.py via four small hooks (see integration notes there).
"""
import json


GREEKS_CARD_CSS = r"""
.gk-wrap{font-family:'Noto Sans JP',sans-serif}
.gk-summary{display:flex;flex-wrap:wrap;align-items:center;gap:4px 2px;background:linear-gradient(180deg,#1f2433,#1a1f2b);border:1px solid var(--border);border-radius:10px;padding:10px 12px;margin:0 0 10px;font-size:13px;color:var(--sub)}
.gk-su-it{white-space:nowrap}
.gk-su-it b{color:var(--text);font-weight:700;margin-left:2px}
.gk-su-sep{color:var(--border);margin:0 6px}
.gk-tabs{display:flex;gap:0;margin:8px 0 6px;border-bottom:1px solid var(--border)}
.gk-tab{flex:1;padding:9px 4px;background:transparent;color:var(--sub);border:none;border-bottom:2px solid transparent;font-family:'Noto Sans JP',sans-serif;font-size:13px;cursor:pointer}
.gk-tab.gk-on{color:var(--accent);border-bottom-color:var(--accent)}
.gk-conv{display:flex;gap:6px;margin:6px 0 10px}
.gk-cv{flex:1;padding:8px 4px;border:1px solid var(--border);border-radius:8px;background:transparent;color:var(--sub);font-family:'Noto Sans JP',sans-serif;font-size:12.5px;cursor:pointer;text-align:center}
.gk-cv.gk-on{background:rgba(99,102,241,.18);border-color:var(--accent);color:#c7d2fe}
.gk-kpis{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 10px}
.gk-kpi{flex:1;min-width:96px;background:#1d2230;border:1px solid var(--border);border-radius:8px;padding:8px 9px}
.gk-kpi .l{font-size:11px;color:var(--sub);font-family:Outfit}
.gk-kpi .v{font-size:17px;font-family:'DM Mono',monospace;margin-top:3px}
.gk-pos{color:#4ade80}.gk-neg{color:#f87171}
.gk-svg-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--border);border-radius:10px;background:#141821;padding:6px 2px}
.gk-note{font-size:12px;color:var(--sub);margin:8px 2px;line-height:1.65}
.gk-scroll{overflow-x:auto;border:1px solid var(--border);border-radius:10px;margin-top:8px;-webkit-overflow-scrolling:touch}
.gk-tbl{border-collapse:separate;border-spacing:0;width:100%;font-size:13.5px}
.gk-tbl th{position:sticky;top:0;background:#1d2230;color:var(--sub);font-weight:500;text-align:right;padding:8px 10px;font-size:12px;white-space:nowrap}
.gk-tbl th:first-child{text-align:left}
.gk-tbl td{padding:8px 10px;border-bottom:1px solid var(--border);text-align:right;font-family:'DM Mono',monospace;white-space:nowrap}
.gk-tbl td:first-child{text-align:left;font-family:'Noto Sans JP',sans-serif}
.gk-atm td{background:rgba(99,102,241,.12)}
.gk-banner{font-size:13px;border-radius:9px;padding:10px 11px;margin:2px 0 11px;line-height:1.65}
.gk-banner b{font-weight:700}
.gk-warn{color:#f59e0b;border:1px solid rgba(245,158,11,.45);background:rgba(245,158,11,.09)}
.gk-tip{color:#c7d2fe;border:1px solid rgba(129,140,248,.45);background:rgba(129,140,248,.10)}
.gk-plain{font-size:13px;color:var(--text);background:#1d2230;border:1px solid var(--border);border-radius:9px;padding:9px 11px;margin:2px 0 9px;line-height:1.6}
.gk-plain b{font-weight:700}
.gk-legend{display:flex;gap:8px 18px;flex-wrap:wrap;margin:0 2px 10px;font-size:12.5px;color:var(--sub);line-height:1.5}
.gk-legend b{color:var(--text);font-weight:600}
.gk-legend i{display:inline-block;width:13px;height:13px;border-radius:3px;margin-right:6px;vertical-align:-2px}
.gk-sw.gk-g{background:#22c55e}.gk-sw.gk-r{background:#ef4444}
.gk-abc{display:flex;gap:6px;margin:0 0 10px}
.gk-abc-it{flex:1;text-align:center;background:#1d2230;border:1px solid var(--border);border-radius:8px;padding:7px 4px;font-size:12px;color:var(--sub)}
.gk-abc-it b{display:block;font-family:'DM Mono',monospace;font-size:13px;margin-top:3px}
.gk-sec2{font-family:Outfit;font-weight:600;color:var(--sub);font-size:12px;margin:14px 2px 6px}
.gk-gl-btn{width:100%;margin-top:12px;padding:11px;border:1px dashed var(--border);border-radius:9px;background:transparent;color:var(--accent);font-family:'Noto Sans JP',sans-serif;font-size:13px;cursor:pointer}
.gk-gl{margin-top:8px;border:1px solid var(--border);border-radius:9px;padding:2px 12px 12px;background:#141821}
.gk-gl-sec{font-family:Outfit;font-weight:600;color:var(--accent);font-size:12.5px;margin:14px 0 4px;padding-bottom:5px;border-bottom:1px solid var(--border)}
.gk-gl-row{font-size:12.5px;color:var(--sub);line-height:1.6;margin:9px 0}
.gk-gl-row b{display:block;color:var(--text);font-weight:700;font-size:13px;margin-bottom:2px}
"""


GREEKS_CARD_JS = r"""
window.GK_STATE = {ei: 0, conv: 'A', gl: false};
function gkFmt(n){ if(n===null||n===undefined) return '—'; var a=Math.abs(n);
  if(a>=1000) return Math.round(n).toLocaleString(); if(a>=10) return n.toFixed(1);
  if(a>=1) return n.toFixed(2); return n.toFixed(3); }
function gkInt(n){ return (n===null||n===undefined)?'—':Math.round(n).toLocaleString(); }

function gkDrawGEX(e, conv){
  var rows = e['gex_'+conv] || e.gex_A;
  if(!rows || !rows.length) return '<div class="gk-note">GEXデータなし</div>';
  // focus the strikes around spot for readability
  var spot = e.spot;
  rows = rows.filter(function(r){ return Math.abs(r.strike-spot) <= spot*0.07; });
  var W = Math.max(rows.length*32+44, 320), H=210, pad=28, midY=H/2;
  var maxv = 0.0001;
  for(var i=0;i<rows.length;i++){ maxv=Math.max(maxv, Math.abs(rows[i].gex)); }
  var bw = (W-pad*2)/rows.length;
  var zg = e['zero_gamma_'+conv] || e.zero_gamma_A;
  var s = '<svg width="'+W+'" height="'+H+'" viewBox="0 0 '+W+' '+H+'">';
  s += '<line x1="'+pad+'" y1="'+midY+'" x2="'+(W-pad)+'" y2="'+midY+'" stroke="#3a4156" stroke-width="1"/>';
  // spot x-position (interpolate by strike order)
  function xOf(strike){
    for(var i=0;i<rows.length;i++){ if(rows[i].strike>=strike){
      var x0=(i>0?rows[i-1].strike:rows[0].strike), x1=rows[i].strike;
      var px0=pad+(i-1)*bw+bw/2, px1=pad+i*bw+bw/2;
      if(x1===x0) return px1; return px0+(px1-px0)*(strike-x0)/(x1-x0);
    }}
    return W-pad;
  }
  for(var i=0;i<rows.length;i++){
    var r=rows[i], h=Math.abs(r.gex)/maxv*(midY-pad);
    var x=pad+i*bw+2, w=Math.max(bw-4,3);
    var pos=r.gex>=0;
    var y=pos?(midY-h):midY;
    s+='<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+Math.max(h,0.5)+'" fill="'+(pos?'#22c55e':'#ef4444')+'" opacity="0.78"/>';
    s+='<text x="'+(x+w/2)+'" y="'+(H-7)+'" fill="#828ca0" font-size="10" text-anchor="middle">'+(r.strike/1000)+'k</text>';
  }
  // spot line
  var sx=xOf(spot);
  s+='<line x1="'+sx+'" y1="'+pad+'" x2="'+sx+'" y2="'+(H-16)+'" stroke="#e9ecf1" stroke-width="1" stroke-dasharray="3,3"/>';
  s+='<text x="'+sx+'" y="'+(pad-4)+'" fill="#e9ecf1" font-size="10" text-anchor="middle">現値</text>';
  // zero-gamma flip line
  if(zg && zg.flip){
    var zx=xOf(zg.flip);
    s+='<line x1="'+zx+'" y1="'+pad+'" x2="'+zx+'" y2="'+(H-16)+'" stroke="#f59e0b" stroke-width="1.2" stroke-dasharray="2,2"/>';
    s+='<text x="'+zx+'" y="'+(pad-4)+'" fill="#f59e0b" font-size="10" text-anchor="middle">0Γ</text>';
  }
  s+='</svg>';
  return s;
}

function gkRegimeChart(G){
  var rh = G.regime_history || [];
  if(rh.length < 2) return '';
  var W = Math.max(rh.length*46+40, 280), H=126, pad=22, midY=H/2;
  var maxv = 0.5;
  for(var i=0;i<rh.length;i++){ maxv = Math.max(maxv, Math.abs(rh[i].B2)); }
  var bw = (W-pad*2)/rh.length;
  var s = '<svg width="'+W+'" height="'+H+'" viewBox="0 0 '+W+' '+H+'">';
  s += '<line x1="'+pad+'" y1="'+midY+'" x2="'+(W-pad)+'" y2="'+midY+'" stroke="#3a4152" stroke-width="1"/>';
  for(var i=0;i<rh.length;i++){
    var v = rh[i].B2;
    var bh = (H/2-pad)*Math.min(Math.abs(v)/maxv, 1);
    var up = v>=0;
    var x = pad+i*bw+bw*0.22, w = bw*0.56;
    var y = up ? midY-bh : midY;
    var col = up ? '#22c55e' : '#ef4444';
    s += '<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+Math.max(bh,1)+'" fill="'+col+'" rx="2"/>';
    s += '<text x="'+(x+w/2)+'" y="'+(up?y-3:y+bh+11)+'" fill="'+col+'" font-size="9" text-anchor="middle">'+(v>=0?'+':'')+v.toFixed(1)+'</text>';
    s += '<text x="'+(pad+i*bw+bw/2)+'" y="'+(H-5)+'" fill="#828ca0" font-size="9" text-anchor="middle">'+rh[i].date.slice(4,6)+'/'+rh[i].date.slice(6,8)+'</text>';
  }
  s += '</svg>';
  return s;
}
function gkBuildHTML(){
  var G = window.GREEKS_DATA;
  if(!G || G.error || !G.expiries || !G.expiries.length){
    return '<div class="gk-note">グリークスデータなし — extract_greeks.py を実行して greeks.json を生成してください（open_interest と ose tp.csv が必要）。</div>';
  }
  if(window.GK_STATE.ei >= G.expiries.length) window.GK_STATE.ei = 0;
  var e = G.expiries[window.GK_STATE.ei], conv = window.GK_STATE.conv;
  var net = e['net_'+conv] || e.net_A;
  var zg  = e['zero_gamma_'+conv] || e.zero_gamma_A;
  var h = '<div class="gk-wrap">';
  // one-glance summary line (top of card)
  var suReg = (zg && zg.sign_at_spot==='positive') ? '🟩 安定' : '🟥 加速';
  var suFlip;
  if(zg && zg.flip){
    var suRel = (zg.flip < e.spot) ? '現値の下' : ((zg.flip > e.spot) ? '現値の上' : '現値付近');
    suFlip = zg.flip.toLocaleString('ja-JP') + '（' + suRel + '）';
  } else { suFlip = '圏内になし'; }
  var suReco;
  if(G.prior_used===false){ suReco = '前日待ち'; }
  else {
    var suAic = (e.atm_iv_chg!=null) ? e.atm_iv_chg*100 : null;
    suReco = (suAic!=null && Math.abs(suAic)>=2.0) ? 'B2' : 'B';
  }
  h += '<div class="gk-summary">'
    + '<span class="gk-su-it">地合い <b>'+suReg+'</b></span>'
    + '<span class="gk-su-sep">｜</span>'
    + '<span class="gk-su-it">転換点 <b>'+suFlip+'</b></span>'
    + '<span class="gk-su-sep">｜</span>'
    + '<span class="gk-su-it">今日は <b>'+suReco+'</b></span>'
    + '</div>';
  // A/B/B2 net-gamma at a glance (see divergence without toggling)
  var abc = [['A', e.net_A], ['B', e.net_B], ['B2', e.net_B2]];
  h += '<div class="gk-abc">';
  for(var ai=0; ai<abc.length; ai++){
    var av = (abc[ai][1]||{}).gamma || 0;
    var acl = av>=0 ? 'gk-pos' : 'gk-neg';
    var amk = av>=0 ? '🟩' : '🟥';
    h += '<span class="gk-abc-it">'+abc[ai][0]+' <b class="'+acl+'">'+amk+' '+(av>=0?'+':'')+av.toFixed(1)+'</b></span>';
  }
  h += '</div>';
  // expiry tabs
  h += '<div class="gk-tabs">';
  for(var i=0;i<G.expiries.length;i++){
    h += '<button class="gk-tab'+(i===window.GK_STATE.ei?' gk-on':'')+'" data-gk-ei="'+i+'">'+G.expiries[i].label+'</button>';
  }
  h += '</div>';
  // convention toggle
  h += '<div class="gk-conv">';
  h += '<button class="gk-cv'+(conv==='A'?' gk-on':'')+'" data-gk-cv="A">慣例A</button>';
  h += '<button class="gk-cv'+(conv==='B'?' gk-on':'')+'" data-gk-cv="B">OI×IV B</button>';
  h += '<button class="gk-cv'+(conv==='B2'?' gk-on':'')+'" data-gk-cv="B2">相対IV B2</button>';
  h += '</div>';
  // guidance banner — always shown, tells the user which convention to trust
  if(G.prior_used===false){
    h += '<div class="gk-banner gk-warn">⚠️ 前日データが無いため <b>B/B2 は慣例Aと同一</b>（フォールバック中）。前日の open_interest.xlsx と ose…tp.csv を data/ に置いて再生成すると分岐します。</div>';
  } else {
    var aic = (e.atm_iv_chg!=null) ? e.atm_iv_chg*100 : null; // 市場全体IV変化(pt)
    if(aic!=null && Math.abs(aic)>=2.0){
      h += '<div class="gk-banner gk-tip">📌 <b>今日の見方</b>：IV(市場全体)が <b>'+(aic>0?'+':'')+aic.toFixed(1)+'pt</b> と大きく動いた日。<b>「相対IV B2」</b>を見てください。Bは市場全体のIV変動を「需要」と誤読しがちです。</div>';
    } else if(aic!=null){
      h += '<div class="gk-banner gk-tip">📌 <b>今日の見方</b>：IV(市場全体)の変動は小さめ（'+(aic>0?'+':'')+aic.toFixed(1)+'pt）。<b>B と B2 はほぼ一致</b>します。素直な「OI×IV B」でOK。</div>';
    }
  }
  // KPIs
  var signTxt = (zg && zg.sign_at_spot==='positive') ? '正（安定/ピン）' : '負（加速/不安定）';
  var signCls = (zg && zg.sign_at_spot==='positive') ? 'gk-pos' : 'gk-neg';
  h += '<div class="gk-kpis">';
  h += '<div class="gk-kpi"><div class="l">現値</div><div class="v">'+gkInt(e.spot)+'</div></div>';
  h += '<div class="gk-kpi"><div class="l">ゼロガンマ</div><div class="v" style="color:#f59e0b">'+gkInt(zg?zg.flip:null)+'</div></div>';
  h += '<div class="gk-kpi"><div class="l">今の地合い</div><div class="v '+signCls+'" style="font-size:12px">'+signTxt+'</div></div>';
  h += '<div class="gk-kpi"><div class="l">netΔ</div><div class="v">'+gkInt(net.delta)+'</div></div>';
  h += '<div class="gk-kpi"><div class="l">netVega</div><div class="v">'+gkInt(net.vega)+'</div></div>';
  h += '<div class="gk-kpi"><div class="l">netΘ/日</div><div class="v">'+gkInt(net.theta)+'</div></div>';
  h += '</div>';
  // plain-language one-liner about the current regime
  var regimePlain = (zg && zg.sign_at_spot==='positive')
    ? '今は現値が<b>「止まりやすい」</b>ゾーン（緑優勢）。値動きは比較的落ち着きやすい地合いです。'
    : '今は現値が<b>「滑りやすい」</b>ゾーン（赤優勢）。動き出すと速く、荒れやすい地合いです。';
  h += '<div class="gk-plain">'+regimePlain+'</div>';
  // color legend (plain words)
  h += '<div class="gk-legend">'
    + '<span><i class="gk-sw gk-g"></i>緑＝その価格帯は<b>止まりやすい</b>（ピン・支持/抵抗）</span>'
    + '<span><i class="gk-sw gk-r"></i>赤＝その価格帯は<b>抜けると加速</b>（滑りやすい）</span>'
    + '</div>';
  // GEX svg
  h += '<div class="gk-svg-wrap">'+gkDrawGEX(e, conv)+'</div>';
  // regime history timeline
  if((G.regime_history||[]).length >= 2){
    h += '<div class="gk-sec2">地合いの推移（各日の netΓ・B2基準　🟩正＝安定／🟥負＝加速）</div>';
    h += '<div class="gk-svg-wrap">'+gkRegimeChart(G)+'</div>';
    h += '<div class="gk-note">日ごとの地合いの移り変わり。棒が上（緑）＝その日はディーラー正ガンマで安定、下（赤）＝負ガンマで荒れやすい。</div>';
  }
  h += '<div class="gk-note">GEXプロファイル（'+e.label+'・残存'+e.T_days+'日）。橙線=ゼロガンマ転換点（地合いが切替わる価格）、白破線=現値。縦軸は各価格帯のガンマの強さ（億円/1%）。'
    + (conv==='B' ? ' ※B=各ストライクのOI×IV増減から売買方向を推定（不明時は慣例にフォールバック）。IV一斉急騰日は市場全体のIV上昇を需要と誤読しやすい。'
        : conv==='B2' ? ' ※B2=各ストライクのIV変化からATM（市場全体）のIV変化を引いた「相対IV」で符号付け。市場全体のvol変動を除き、そのストライク固有の需要だけを抽出（vol急騰日に強い）。'
        : ' ※A=ディーラー＝コール買い/プット売りの標準仮定（毎日同ルールの基準線）。') + '</div>';
  // greeks table (strikes near spot)
  var per = e.per_strike.filter(function(p){ return Math.abs(p.strike-e.spot)<=e.spot*0.035; });
  h += '<div class="gk-scroll"><table class="gk-tbl"><thead><tr><th>ストライク</th><th>IV</th><th>Δ</th><th>Γ(e-5)</th><th>Vega</th><th>Θ/日</th><th>C-OI</th><th>P-OI</th></tr></thead><tbody>';
  for(var i=0;i<per.length;i++){
    var p=per[i], cp=(p.strike>=e.spot)?'call':'put', g=p[cp];
    var atm = Math.abs(p.strike-e.spot)<250 ? ' class="gk-atm"' : '';
    h += '<tr'+atm+'><td>'+(cp==='put'?'P':'C')+(p.strike).toLocaleString()+'</td>'
      + '<td>'+(p.iv*100).toFixed(1)+'%</td>'
      + '<td>'+g.delta.toFixed(3)+'</td>'
      + '<td>'+(g.gamma*1e5).toFixed(2)+'</td>'
      + '<td>'+gkFmt(g.vega)+'</td>'
      + '<td>'+gkFmt(g.theta)+'</td>'
      + '<td>'+gkInt(p.call_oi)+'</td>'
      + '<td>'+gkInt(p.put_oi)+'</td></tr>';
  }
  h += '</tbody></table></div>';
  h += '</div>';
  // collapsible glossary
  h += '<button class="gk-gl-btn" data-gk-gl="1">📖 用語の意味を'+(window.GK_STATE.gl?'閉じる ▲':'ひらく ▼')+'</button>';
  if(window.GK_STATE.gl){ h += '<div class="gk-gl">'+gkGlossaryHTML()+'</div>'; }
  return h;
}
function gkGlossaryHTML(){
  var h = '';
  h += '<div class="gk-gl-sec">グリークス（オプションの感応度）</div>';
  h += '<div class="gk-gl-row"><b>Δ デルタ＝方向の感応度</b>原資産（日経）が動いたとき、オプション価格がどっち向きに・どれだけ動くか。コールは＋、プットは−。</div>';
  h += '<div class="gk-gl-row"><b>Γ ガンマ＝変化の起きやすさ（加速度）</b>そのΔ自体がどれだけ変わりやすいか。大きいほど、価格が動くと一気に効いて荒れやすい。</div>';
  h += '<div class="gk-gl-row"><b>Vega ベガ＝ボラへの感応度</b>IV（予想変動率）が1%上がると、オプション価格がどれだけ動くか。</div>';
  h += '<div class="gk-gl-row"><b>Θ シータ＝時間の目減り</b>1日経つだけでオプション価格がどれだけ減るか。買い手にはコスト、売り手には収益。</div>';
  h += '<div class="gk-gl-sec">このカードの指標</div>';
  h += '<div class="gk-gl-row"><b>ゼロガンマ</b>ディーラーの地合いが「安定⇄加速」に切り替わる価格。ここを境に値動きの質が変わる目安。</div>';
  h += '<div class="gk-gl-row"><b>GEX 緑/赤</b>緑＝その価格帯は止まりやすい（ピン・支持/抵抗）。赤＝抜けると加速（滑りやすい）。棒の高さ＝効きの強さ。</div>';
  h += '<div class="gk-gl-row"><b>今の地合い</b>現値の位置が、いま緑（安定）寄りか赤（加速）寄りか。</div>';
  h += '<div class="gk-gl-row"><b>netΔ / netVega / netΘ</b>全建玉を合計した、ディーラー想定ポジション全体のΔ・Vega・Θ。市場全体の傾きの目安。</div>';
  h += '<div class="gk-gl-row"><b>C-OI / P-OI</b>コール／プットの建玉（未決済の量）。多い価格帯ほど節目になりやすい。</div>';
  h += '<div class="gk-gl-sec">A / B / B2（符号の置き方）</div>';
  h += '<div class="gk-gl-row"><b>A 慣例</b>ディーラー＝コール買い・プット売りと決め打ちする標準ルール。毎日ブレない基準線。</div>';
  h += '<div class="gk-gl-row"><b>B OI×IV</b>各価格のOIとIVの増減から、買われたか売られたかを推定して符号を置く。穏やかな日向き。</div>';
  h += '<div class="gk-gl-row"><b>B2 相対IV</b>市場全体のIV変動を差し引いた「相対IV」で推定。vol一斉急騰/急落の日に強い（荒れた日はこれ）。</div>';
  return h;
}
function gkRender(card){
  if(!card) return;
  var host = card.querySelector('.card-detail');
  if(host) host.innerHTML = gkBuildHTML();
}

document.addEventListener('click', function(ev){
  var t = ev.target;
  if(!t || !t.getAttribute) return;
  var ei = t.getAttribute('data-gk-ei');
  var cv = t.getAttribute('data-gk-cv');
  var gl = t.getAttribute('data-gk-gl');
  if(ei===null && cv===null && gl===null) return;
  ev.stopPropagation();
  var card = t.closest ? t.closest('.card') : null;
  if(!card) return;
  if(ei!==null) window.GK_STATE.ei = parseInt(ei,10);
  if(cv!==null) window.GK_STATE.conv = cv;
  if(gl!==null) window.GK_STATE.gl = !window.GK_STATE.gl;
  gkRender(card);
}, true);
"""


def preview_greeks(greeks):
    if not greeks or greeks.get('error') or not greeks.get('expiries'):
        return ('<div class="card-stat"><span class="label">GEX</span>'
                '<span class="value">—</span></div>')
    e = greeks['expiries'][0]
    za = (e.get('zero_gamma_A') or {}).get('flip')
    zb = (e.get('zero_gamma_B') or {}).get('flip')
    sign = (e.get('zero_gamma_A') or {}).get('sign_at_spot')
    sgn_txt = '正(ピン)' if sign == 'positive' else '負(加速)'
    sgn_col = '#4ade80' if sign == 'positive' else '#f87171'

    def f(x):
        return '{:,}'.format(int(x)) if x else '—'
    h = '<div style="font-size:11px;line-height:1.7">'
    h += '<div><span style="color:var(--sub)">ゼロガンマ </span>'
    h += '<b style="color:#f59e0b">A %s</b> / <b style="color:#c7d2fe">B %s</b></div>' % (f(za), f(zb))
    h += '<div><span style="color:var(--sub)">現値のディーラーΓ </span>'
    h += '<b style="color:%s">%s</b></div>' % (sgn_col, sgn_txt)
    h += '<div style="color:var(--sub);font-size:10px;margin-top:2px">%s・残存%d日</div>' % (
        e.get('label', ''), e.get('T_days', 0))
    h += '</div>'
    return h


def detail_greeks_js(greeks):
    # The framework injects this card's detail via: detail.innerHTML = b_greeks().
    # So b_greeks() must RETURN the HTML string (gkBuildHTML reads the globals).
    return "return gkBuildHTML();"


def greeks_data_script(greeks):
    payload = greeks or {}
    return 'window.GREEKS_DATA = ' + json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + ';\n'
