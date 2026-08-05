#!/usr/bin/env python3
"""Render the "大口動向（週次の推移）" card from broker_history.json.

Shows, per major broker, the multi-week trend of futures net and option
put/call net (buy +, sell -), with a derived tendency tag. Futures and
options are the two separate battlegrounds, so each broker line carries both.
"""
import json


CAT_JA = {'us': '米系', 'eu': '欧系', 'hf': 'HF代理',
          'domestic': '国内', 'other': '', 'グローバルマクロ': 'マクロ'}


def _short(n):
    return str(n).replace('ＪＰモルガン', 'JPモルガン')[:8]


def bw_data_script(hist):
    dates = sorted(hist.keys())
    # union of brokers, ranked by footprint (|fut| + 20*|put|+|call|)
    foot = {}
    for d in dates:
        for b, v in hist[d].items():
            f = abs(v.get('fut', 0) or 0) + 20 * (abs(v.get('put', 0) or 0)
                                                  + abs(v.get('call', 0) or 0))
            foot[b] = max(foot.get(b, 0), f)
    order = [b for b, _ in sorted(foot.items(), key=lambda x: -x[1])]

    def series(b, field):
        return [hist[d].get(b, {}).get(field) for d in dates]

    rows = []
    for b in order:
        cat = ''
        for d in dates:
            if hist[d].get(b, {}).get('cat'):
                cat = hist[d][b]['cat']
                break
        rows.append({
            'broker': b, 'cat': CAT_JA.get(cat, cat),
            'fut': series(b, 'fut'), 'put': series(b, 'put'),
            'call': series(b, 'call'),
        })
    payload = {'dates': [d[4:6] + '/' + d[6:] for d in dates], 'rows': rows}
    return "window.BW_DATA=%s;" % json.dumps(payload, ensure_ascii=False)


BW_CARD_CSS = r"""
.bw-intro{font-size:11.5px;color:var(--sub);line-height:1.6;margin:2px 2px 10px}
.bw-row{border:1px solid var(--border);border-radius:10px;padding:10px 12px;margin:8px 0;background:#141822}
.bw-name{font-family:Outfit;font-weight:700;font-size:13.5px;margin-bottom:8px}
.bw-cat{font-size:10px;color:var(--sub);font-weight:400;margin-left:6px}
.bw-metrics{display:flex;gap:10px}
.bw-metric{flex:1;min-width:0}
.bw-mlabel{font-size:10px;color:var(--sub);margin-bottom:3px}
.bw-spark{background:#0f131b;border-radius:5px;padding:2px 3px}
.bw-mval{font-family:'DM Mono',monospace;font-size:12px;font-weight:600;margin-top:3px;white-space:nowrap}
.bw-wow{font-size:9.5px;margin-left:2px;opacity:.85}
.bw-pos{color:#86efac}.bw-neg{color:#fca5a5}.bw-ze{color:var(--sub)}
.bw-read{font-size:10.5px;color:#cbd5e1;line-height:1.45;margin-top:8px;border-top:1px solid rgba(38,44,58,.6);padding-top:6px}
.bw-note{font-size:11px;color:var(--sub);line-height:1.55;margin:10px 2px 2px}
"""

BW_CARD_JS = r"""
function bwFmt(v){
  if(v===null||v===undefined) return '<span class="bw-ze">—</span>';
  var r=Math.round(v), cls = r>0?'bw-pos':(r<0?'bw-neg':'bw-ze');
  var s=(r>0?'+':'')+r.toLocaleString();
  return '<span class="'+cls+'">'+s+'</span>';
}
function bwTrend(arr){
  var v=arr.filter(function(x){return x!==null&&x!==undefined;});
  if(v.length<2) return '';
  var a=v[0], b=v[v.length-1], d=b-a;
  if(Math.abs(d)<Math.max(300,Math.abs(a)*0.15)) return '横ばい';
  return d>0?'↑増':'↓減';
}
function bwLean(arr, kind){
  // arr of nets; decide buy/sell lean
  var v=arr.filter(function(x){return x!==null&&x!==undefined&&Math.abs(x)>50;});
  if(!v.length) return '';
  var pos=v.filter(function(x){return x>0;}).length;
  var neg=v.filter(function(x){return x<0;}).length;
  if(pos>=neg*2 && pos>=2) return kind+'買い持ちが基調';
  if(neg>=pos*2 && neg>=2) return kind+'売り持ちが基調';
  return kind+'は局面で入れ替え';
}
function bwReadFut(r){
  var t=bwTrend(r.fut), l=bwLean(r.fut,'先物');
  var last=r.fut.filter(function(x){return x!==null;}).pop();
  if(last===undefined) return '';
  var side = last>0?'買い越し（ロング）':'売り越し（ショート）';
  return '先物は'+side+'で'+(t||'推移')+'。'+l+'。';
}
function bwReadOpt(r){
  var pl=bwLean(r.put,'プット'), cl=bwLean(r.call,'コール');
  var out=[];
  if(pl) out.push(pl);
  if(cl) out.push(cl);
  return out.join('／');
}
function bwSpark(arr, w, hgt){
  // mini bar chart centered on zero. positive=green up, negative=red down.
  w = w||150; hgt = hgt||26;
  var vals = arr.map(function(x){return (x===null||x===undefined)?null:x;});
  var mx = 1;
  vals.forEach(function(v){ if(v!==null) mx=Math.max(mx, Math.abs(v)); });
  var n = vals.length, bw = w/n, mid = hgt/2;
  var bars='';
  for(var i=0;i<n;i++){
    var v=vals[i];
    if(v===null){ continue; }
    var hh = Math.max(1, Math.abs(v)/mx*(mid-1));
    var x = i*bw+0.5, bwid=Math.max(1.5,bw-1.5);
    var y = v>=0 ? (mid-hh) : mid;
    var col = v>0?'#4ade80':(v<0?'#f87171':'#5b6472');
    bars += '<rect x="'+x.toFixed(1)+'" y="'+y.toFixed(1)+'" width="'+bwid.toFixed(1)+'" height="'+hh.toFixed(1)+'" fill="'+col+'" rx="0.5"/>';
  }
  return '<svg width="'+w+'" height="'+hgt+'" viewBox="0 0 '+w+' '+hgt+'" style="display:block">'
    +'<line x1="0" y1="'+mid+'" x2="'+w+'" y2="'+mid+'" stroke="#2a3140" stroke-width="0.5"/>'+bars+'</svg>';
}
function bwLast(arr){
  var v=arr.filter(function(x){return x!==null&&x!==undefined;});
  return v.length? v[v.length-1] : null;
}
function bwPrev(arr){
  var v=arr.filter(function(x){return x!==null&&x!==undefined;});
  return v.length>1? v[v.length-2] : null;
}
function bwChip(arr, label){
  var last=bwLast(arr), prev=bwPrev(arr);
  if(last===null) return '';
  var cls=last>0?'bw-pos':(last<0?'bw-neg':'bw-ze');
  var s=(last>0?'+':'')+Math.round(last).toLocaleString();
  var wow='';
  if(prev!==null){
    var d=last-prev;
    if(Math.abs(d)>=Math.max(200,Math.abs(prev)*0.1)){
      wow='<span class="bw-wow '+(d>0?'bw-pos':'bw-neg')+'">'+(d>0?'▲':'▼')+Math.abs(Math.round(d)).toLocaleString()+'</span>';
    }
  }
  return '<div class="bw-metric"><div class="bw-mlabel">'+label+'</div>'
    +'<div class="bw-spark">'+bwSpark(arr)+'</div>'
    +'<div class="bw-mval '+cls+'">'+s+' '+wow+'</div></div>';
}
function bwBuild(){
  var D=window.BW_DATA||{}; if(!D.rows) return '<div>データなし</div>';
  var dates=D.dates||[];
  var h='<div class="bw-intro">主要大口の<b>週次ネット建玉</b>（売買区分あり＝確定値）の推移を、直近'+dates.length+'週のミニ棒グラフで表示。'
    +'<span class="bw-pos">緑＝買い持ち</span>／<span class="bw-neg">赤＝売り持ち</span>。先物は方向観、オプション（P/C）は壁・受け皿を映す。'
    +'右端が最新（'+dates[dates.length-1]+'）、▲▼は前週差。</div>';
  var rows=D.rows.slice(0,10);
  for(var i=0;i<rows.length;i++){
    var r=rows[i];
    h+='<div class="bw-row">';
    h+='<div class="bw-name">'+r.broker.replace('ＪＰモルガン','JPモルガン')+'<span class="bw-cat">'+(r.cat||'')+'</span></div>';
    h+='<div class="bw-metrics">';
    h+=bwChip(r.fut,'先物');
    h+=bwChip(r.put,'プット');
    h+=bwChip(r.call,'コール');
    h+='</div>';
    var read=[bwReadFut(r), bwReadOpt(r)].filter(function(x){return x;}).join(' ');
    if(read) h+='<div class="bw-read">↳ '+read+'</div>';
    h+='</div>';
  }
  h+='<div class="bw-note">週次建玉は売買区分のある確報値。過去の傾向であり将来を保証しない。'
    +'「先物で方向を出す社（GS・HSBC・CTA）」と「オプションで壁を作る社（ABN・BNP・JPM）」を両面で追える。</div>';
  return h;
}
"""


def preview_broker_watch(hist):
    """Short preview: highlight the biggest futures long/short and a note."""
    dates = sorted(hist.keys())
    if not dates:
        return "var h='<div>データなし</div>';return h;"
    last = hist[dates[-1]]
    fut = [(b, v.get('fut', 0)) for b, v in last.items() if v.get('fut')]
    if not fut:
        return "var h='<div>週次データ待ち</div>';return h;"
    top_long = max(fut, key=lambda x: x[1])
    top_short = min(fut, key=lambda x: x[1])
    js = "var h='';"
    js += ("h+='<div style=\"font-size:12px;line-height:1.7\">"
           "先物ロング首位: <b>%s</b> (%+d)<br>"
           "先物ショート首位: <b>%s</b> (%+d)</div>';") % (
        _short(top_long[0]), round(top_long[1]),
        _short(top_short[0]), round(top_short[1]))
    return js


if __name__ == '__main__':
    import sys
    h = json.load(open(sys.argv[1], encoding='utf-8'))
    print(bw_data_script(h)[:200])
