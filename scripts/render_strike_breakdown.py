#!/usr/bin/env python3
"""Render the "価格帯の内訳（建玉×手口×IV）" card.

Three layers stacked on one strike:
  1. OI change  — how much open interest actually moved (the outcome)
  2. Participant volume — how much was traded, through which venue, by whom
     (the mechanism: off-auction blocks vs on-screen flow)
  3. Relative IV move — which way the pressure pushed (the inferred direction)

Volume and OI change are different units on purpose: volume counts trades,
OI counts what stayed open. Volume far above the OI change means positions
were opened and closed within the day, or changed hands — that gap is itself
information, so we show both rather than reducing them to one ratio.
"""
import json


VENUE_JA = {'day_auction': '日中立会', 'day_jnet': '日中J-NET',
            'night_auction': '夜間立会', 'night_jnet': '夜間J-NET'}
CAT_JA = {'domestic': '国内', 'us': '米系', 'eu': '欧系', 'hf': 'HF代理', 'other': ''}


def _verdict(oi_chg, rel):
    if oi_chg is None or rel is None:
        return None
    TH = 0.003
    if oi_chg > 0:
        if rel > TH:
            return ('買われた', 'sb-buy')
        if rel < -TH:
            return ('売られた', 'sb-sell')
        return ('判定弱い', 'sb-weak')
    if oi_chg < 0:
        if rel > TH:
            return ('売り建ての決済', 'sb-buy')
        if rel < -TH:
            return ('買い建ての決済', 'sb-sell')
        return ('判定弱い', 'sb-weak')
    return None


def sb_data_script(greeks, venue_flow, indicators=None):
    """Join OI change + IV move (greeks) with participant volume (venue_flow)."""
    if not greeks or not greeks.get('expiries'):
        return "window.SB_DATA=null;"
    e = greeks['expiries'][0]
    ex4 = e.get('expiry', '')
    ex4 = ex4[2:] if len(ex4) == 6 else ex4

    vmap = {}
    if venue_flow:
        for r in venue_flow.get('rows', []):
            vmap[(r['expiry'], r['side'], r['strike'])] = r

    rows = []
    for r in e.get('per_strike', []):
        k = int(r['strike'])
        rel = r.get('iv_chg_rel_mny')
        rel = rel if rel is not None else r.get('iv_chg_rel')
        for side, chg_key, oi_key in (('P', 'put_oi_chg', 'put_oi'),
                                      ('C', 'call_oi_chg', 'call_oi')):
            chg = r.get(chg_key)
            vf = vmap.get((ex4, side, k))
            # include a strike if either layer has something worth showing
            if not vf and (chg is None or abs(chg) < 200):
                continue
            if vf is None and chg is None:
                continue
            v = _verdict(chg, rel)
            rows.append({
                'side': side, 'strike': k,
                'oi': round(r.get(oi_key, 0) or 0),
                'oi_chg': (round(chg) if chg is not None else None),
                'rel': (round(rel * 100, 1) if rel is not None else None),
                'verdict': (v[0] if v else None),
                'vcls': (v[1] if v else None),
                'vol': (vf['total'] if vf else None),
                'block_pct': (vf['block_pct'] if vf else None),
                'by_venue': (vf['by_venue'] if vf else None),
                'brokers': (vf['brokers'][:4] if vf else None),
            })
    # rank: contracts with participant data first, then by traded volume, then OI move
    rows.sort(key=lambda x: (x['vol'] is None, -(x['vol'] or 0),
                             -abs(x['oi_chg'] or 0)))
    payload = {'spot': e.get('spot'), 'expiry': e.get('expiry'),
               'date': (venue_flow or {}).get('date'),
               'venues': (venue_flow or {}).get('venues_found'),
               'rows': rows[:14]}
    return "window.SB_DATA=%s;" % json.dumps(payload, ensure_ascii=False)


SB_CARD_CSS = r"""
.sb-intro{font-size:11.5px;color:var(--sub);line-height:1.6;margin:2px 2px 10px}
.sb-row{border:1px solid var(--border);border-radius:10px;padding:10px 12px;margin:8px 0;background:#141822}
.sb-hd{display:flex;align-items:baseline;gap:8px;margin-bottom:7px;flex-wrap:wrap}
.sb-k{font-family:'DM Mono',monospace;font-weight:600;font-size:13.5px}
.sb-p{color:#fca5a5}.sb-c{color:#93c5fd}
.sb-tag{font-size:10.5px;padding:1px 7px;border-radius:6px;white-space:nowrap}
.sb-buy{background:rgba(34,197,94,.16);color:#86efac}
.sb-sell{background:rgba(248,113,113,.16);color:#fca5a5}
.sb-weak{background:rgba(139,147,167,.15);color:var(--sub)}
.sb-layer{display:flex;gap:8px;font-size:11px;margin-top:4px;align-items:flex-start}
.sb-lb{min-width:52px;color:var(--sub);font-size:10px;padding-top:1px}
.sb-val{font-family:'DM Mono',monospace;font-size:11.5px}
.sb-pos{color:#86efac}.sb-neg{color:#fca5a5}.sb-ze{color:var(--sub)}
.sb-bar{height:6px;border-radius:3px;background:#0f131b;overflow:hidden;margin-top:4px;display:flex}
.sb-bar i{display:block;height:100%}
.sb-jnet{background:#818cf8}.sb-auc{background:#3f4655}
.sb-bro{display:inline-block;padding:1px 6px;border-radius:6px;font-size:10.5px;margin:1px 2px 1px 0;background:rgba(129,140,248,.12);color:#c7cbf5}
.sb-bro.dom{background:rgba(248,113,113,.13);color:#fca5a5}
.sb-note{font-size:11px;color:var(--sub);line-height:1.55;margin:10px 2px 2px}
"""

SB_CARD_JS = r"""
function sbNum(v,plus){
  if(v===null||v===undefined) return '—';
  var s=Math.round(v).toLocaleString();
  return (plus&&v>0?'+':'')+s;
}
function sbBuild(){
  var D=window.SB_DATA; if(!D||!D.rows||!D.rows.length) return '<div class="insight">データなし</div>';
  var h='<div class="sb-intro">同じ行使価格を<b>3層</b>で見ます。'
    +'<b>①建玉</b>＝実際に残った玉の増減、<b>②手口</b>＝その日に売買された枚数（立会／J-NETの内訳と参加者）、'
    +'<b>③相対IV</b>＝どちら向きの圧力だったか。'
    +'手口が建玉増減より大きい場合は、日中に建てて閉じた分や玉の移転が含まれます。</div>';
  var rows=D.rows;
  for(var i=0;i<rows.length;i++){
    var r=rows[i];
    h+='<div class="sb-row">';
    h+='<div class="sb-hd"><span class="sb-k '+(r.side==='P'?'sb-p':'sb-c')+'">'+r.side+r.strike.toLocaleString()+'</span>';
    if(r.verdict) h+='<span class="sb-tag '+r.vcls+'">'+r.verdict+'</span>';
    h+='</div>';
    // layer 1: OI
    var oc=r.oi_chg;
    var occls = oc===null?'sb-ze':(oc>0?'sb-pos':(oc<0?'sb-neg':'sb-ze'));
    h+='<div class="sb-layer"><span class="sb-lb">①建玉</span><span class="sb-val">'
      + sbNum(r.oi) + ' <span class="'+occls+'">('+ (oc===null?'前日比不明':sbNum(oc,true)) +')</span></span></div>';
    // layer 2: volume + venue split + brokers
    if(r.vol!==null&&r.vol!==undefined){
      var jn=r.block_pct||0;
      h+='<div class="sb-layer"><span class="sb-lb">②手口</span><span class="sb-val">'
        + sbNum(r.vol)+'枚 <span class="sb-ze">（J-NET '+jn+'%）</span></span></div>';
      h+='<div class="sb-bar"><i class="sb-jnet" style="width:'+jn+'%"></i><i class="sb-auc" style="width:'+(100-jn)+'%"></i></div>';
      if(r.brokers&&r.brokers.length){
        var bs=r.brokers.map(function(b){
          var cls=(b.cat==='domestic')?'sb-bro dom':'sb-bro';
          return '<span class="'+cls+'">'+String(b.broker).replace('証券','').replace('クリアリン','クリア')+' '+sbNum(b.vol)+'</span>';
        }).join('');
        h+='<div style="margin-top:5px">'+bs+'</div>';
      }
    }
    // layer 3: relative IV
    if(r.rel!==null&&r.rel!==undefined){
      var rc=r.rel>0?'sb-pos':(r.rel<0?'sb-neg':'sb-ze');
      h+='<div class="sb-layer"><span class="sb-lb">③相対IV</span><span class="sb-val '+rc+'">'
        +(r.rel>0?'+':'')+r.rel.toFixed(1)+'pt</span></div>';
    }
    h+='</div>';
  }
  h+='<div class="sb-note">手口は日中・夜間の立会／J-NETを合算。<span class="sb-bro dom">赤=国内</span> '
    +'<span class="sb-bro">青=海外/HF</span>。J-NET比率が高いほど大口の相対取引が主体。'
    +'手口には売買区分がないため、向きは③相対IVと建玉の増減から推定しています（断定不可）。</div>';
  return h;
}
"""


def preview_strike_breakdown(greeks, venue_flow):
    if not venue_flow or not venue_flow.get('rows'):
        return '<span class="mm-label">セッション別手口ファイル未取込</span>'
    top = venue_flow['rows'][0]
    return ('<span class="mm-label">本日最大の手口</span>'
            '<span class="tag %s">%s%s %s枚</span>'
            '<span class="tag">J-NET %d%%</span>' % (
                'tag-put' if top['side'] == 'P' else 'tag-call',
                top['side'], format(top['strike'], ','),
                format(top['total'], ','), top['block_pct']))
