#!/usr/bin/env python3
"""
JPX Market Analysis - Market Data Fetcher (fetch_market.py)
============================================================
Fetches Nikkei 225 close, VI, and 25-day OHLC history.

Usage:
    python fetch_market.py [--out market_latest.json]
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError


def fetch_stooq_nikkei():
    """Fetch Nikkei 225 cash close from stooq.com."""
    try:
        url = 'https://stooq.com/q/l/?s=^nkx&f=sd2t2ohlcv&h&e=csv'
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urlopen(req, timeout=10)
        text = resp.read().decode('utf-8').strip()
        lines = text.split('\n')
        if len(lines) >= 2:
            parts = lines[1].split(',')
            close = float(parts[6])
            if 20000 < close < 80000:
                return close
    except Exception as e:
        print('[fetch] stooq nikkei failed: %s' % e, file=sys.stderr)
    return None


def fetch_yahoo_nikkei():
    """Fallback: Fetch from Yahoo Finance Japan."""
    try:
        url = 'https://finance.yahoo.co.jp/quote/998407.O'
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urlopen(req, timeout=10)
        text = resp.read().decode('utf-8')
        m = re.search(r'([\d,]+\.\d+)', text)
        if m:
            val = float(m.group(1).replace(',', ''))
            if 20000 < val < 80000:
                return val
    except Exception as e:
        print('[fetch] yahoo nikkei failed: %s' % e, file=sys.stderr)
    return None


def fetch_stooq_vi():
    """Fetch Nikkei VI from stooq.com."""
    try:
        url = 'https://stooq.com/q/l/?s=^jniv&f=sd2t2ohlcv&h&e=csv'
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urlopen(req, timeout=10)
        text = resp.read().decode('utf-8').strip()
        lines = text.split('\n')
        if len(lines) >= 2:
            parts = lines[1].split(',')
            close = float(parts[6])
            if 10 < close < 100:
                return close
    except Exception as e:
        print('[fetch] stooq VI failed: %s' % e, file=sys.stderr)
    return None


def fetch_investing_vi():
    """Fetch Nikkei VI from Investing.com."""
    try:
        url = 'https://jp.investing.com/indices/nikkei-volatility'
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'ja'})
        resp = urlopen(req, timeout=10)
        text = resp.read().decode('utf-8')
        m = re.search(r'data-test="instrument-price-last"[^>]*>([\d,.]+)', text)
        if m:
            val = float(m.group(1).replace(',', ''))
            if 10 < val < 100:
                return val
    except Exception as e:
        print('[fetch] investing VI failed: %s' % e, file=sys.stderr)
    return None


def fetch_yahoo_vi():
    """Fetch Nikkei VI from Yahoo Finance Japan."""
    try:
        url = 'https://finance.yahoo.co.jp/quote/2035.T'
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urlopen(req, timeout=10)
        text = resp.read().decode('utf-8')
        m = re.search(r'<span[^>]*class="[^"]*StyledNumber[^"]*"[^>]*>([\d,.]+)</span>', text)
        if m:
            val = float(m.group(1).replace(',', ''))
            if 10 < val < 100:
                return val
    except Exception as e:
        print('[fetch] yahoo VI failed: %s' % e, file=sys.stderr)
    return None


def fetch_stooq_ohlc_history(days=30):
    """Fetch N225 daily OHLC history from stooq (last N calendar days).

    Tries multiple symbols and Yahoo Finance as fallback.
    Returns list of {date, open, high, low, close} sorted oldest-first.
    """
    end = datetime.now()
    start = end - timedelta(days=days + 15)
    d1 = start.strftime('%Y%m%d')
    d2 = end.strftime('%Y%m%d')

    # Try multiple stooq symbols
    symbols = ['^nkx', 'nk225.jp', '^nki']
    for sym in symbols:
        try:
            url = 'https://stooq.com/q/d/l/?s=%s&d1=%s&d2=%s&i=d' % (sym, d1, d2)
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            resp = urlopen(req, timeout=15)
            text = resp.read().decode('utf-8').strip()
            lines = text.split('\n')
            print('[fetch] stooq %s: %d lines, first=%s' % (sym, len(lines), lines[0][:60] if lines else ''), file=sys.stderr)

            history = _parse_ohlc_csv(lines)
            if history:
                history = history[-days:]
                print('[fetch] OHLC history from stooq(%s): %d trading days' % (sym, len(history)), file=sys.stderr)
                return history
        except Exception as e:
            print('[fetch] stooq %s failed: %s' % (sym, e), file=sys.stderr)

    # Fallback: Yahoo Finance chart API
    try:
        period2 = int(end.timestamp())
        period1 = int(start.timestamp())
        url = 'https://query1.finance.yahoo.com/v8/finance/chart/%%5EN225?period1=%d&period2=%d&interval=1d' % (period1, period2)
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urlopen(req, timeout=15)
        data = json.loads(resp.read().decode('utf-8'))
        result = data.get('chart', {}).get('result', [])
        if result:
            timestamps = result[0].get('timestamp', [])
            quotes = result[0].get('indicators', {}).get('quote', [{}])[0]
            opens = quotes.get('open', [])
            highs = quotes.get('high', [])
            lows = quotes.get('low', [])
            closes = quotes.get('close', [])
            history = []
            for i in range(len(timestamps)):
                try:
                    o = opens[i]
                    h = highs[i]
                    l = lows[i]
                    c = closes[i]
                    if o and h and l and c and 20000 < c < 80000:
                        dt = datetime.fromtimestamp(timestamps[i])
                        history.append({
                            'date': dt.strftime('%Y-%m-%d'),
                            'open': round(o, 2),
                            'high': round(h, 2),
                            'low': round(l, 2),
                            'close': round(c, 2),
                        })
                except (TypeError, IndexError):
                    continue
            if history:
                history.sort(key=lambda x: x['date'])
                history = history[-days:]
                print('[fetch] OHLC history from Yahoo: %d trading days' % len(history), file=sys.stderr)
                return history
    except Exception as e:
        print('[fetch] Yahoo OHLC history failed: %s' % e, file=sys.stderr)

    print('[fetch] OHLC history: 0 trading days (all sources failed)', file=sys.stderr)
    return []


def _parse_ohlc_csv(lines):
    """Parse OHLC CSV lines (skip header). Returns list sorted oldest-first."""
    history = []
    for line in lines[1:]:
        parts = line.strip().split(',')
        if len(parts) < 5:
            continue
        try:
            o = float(parts[1])
            h = float(parts[2])
            l = float(parts[3])
            c = float(parts[4])
            if 20000 < c < 80000:
                history.append({
                    'date': parts[0],
                    'open': o,
                    'high': h,
                    'low': l,
                    'close': c,
                })
        except (ValueError, IndexError):
            continue
    history.sort(key=lambda x: x['date'])
    return history


def fetch_yahoo_futures():
    """Fetch front-month Nikkei 225 futures close (CME NIY=F, yen-denominated)
    from Yahoo Finance. Used as a proxy for the OSE Nikkei 225 large futures to
    compute a real basis (futures - spot). Tracks the index closely; contract
    and session timing differ slightly, so treat the basis as indicative."""
    try:
        url = 'https://query1.finance.yahoo.com/v8/finance/chart/NIY%3DF?interval=1d&range=5d'
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urlopen(req, timeout=12)
        data = json.loads(resp.read().decode('utf-8'))
        result = data.get('chart', {}).get('result', [])
        if result:
            meta = result[0].get('meta', {})
            price = meta.get('regularMarketPrice')
            if price and 20000 < price < 80000:
                return float(price)
            closes = result[0].get('indicators', {}).get('quote', [{}])[0].get('close', [])
            for c in reversed(closes):
                if c and 20000 < c < 80000:
                    return float(c)
    except Exception as e:
        print('[fetch] yahoo futures (NIY=F) failed: %s' % e, file=sys.stderr)
    return None


def fetch_stooq_futures():
    """Best-effort fallback: try stooq for a Nikkei 225 futures symbol."""
    for sym in ['nk225.f', 'jp225', 'nkz']:
        try:
            url = 'https://stooq.com/q/l/?s=%s&f=sd2t2ohlcv&h&e=csv' % sym
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            resp = urlopen(req, timeout=10)
            text = resp.read().decode('utf-8').strip()
            lines = text.split('\n')
            if len(lines) >= 2:
                parts = lines[1].split(',')
                close = float(parts[6])
                if 20000 < close < 80000:
                    return close
        except Exception:
            continue
    return None


def fetch_nikkei_futures():
    """Return (futures_close, source) for the front-month Nikkei 225 future."""
    f = fetch_yahoo_futures()
    if f:
        return f, 'yahoo:NIY=F'
    f = fetch_stooq_futures()
    if f:
        return f, 'stooq'
    return None, None


def run(args):
    source = 'none'

    # Spot Nikkei 225 cash index
    spot = fetch_stooq_nikkei()
    if spot:
        source = 'stooq'
    else:
        spot = fetch_yahoo_nikkei()
        if spot:
            source = 'yahoo'

    # Front-month Nikkei 225 futures (for ATM + real basis)
    futures, fut_source = fetch_nikkei_futures()
    if futures:
        print('[fetch] futures close from %s: %.0f' % (fut_source, futures), file=sys.stderr)
    else:
        print('[fetch] futures close unavailable — basis will be omitted, ATM falls back to spot', file=sys.stderr)

    # Real basis = futures - spot (only when both are available; never faked)
    basis = None
    basis_signal = None
    if futures and spot:
        basis = round(futures - spot)
        if basis > 0:
            basis_signal = 'コンタンゴ（先物プレミアム）'
        elif basis < 0:
            basis_signal = 'バックワーデーション（先物ディスカウント）'
        else:
            basis_signal = 'フラット'
        print('[fetch] basis = futures(%.0f) - spot(%.0f) = %+d (%s)' % (futures, spot, basis, basis_signal), file=sys.stderr)

    # ATM prefers the CASH index close (^nkx, JST 15:00), which tracks the OSE
    # Nikkei 225 large-futures day-session close (15:15) within a few hundred yen.
    # NIY=F is the CME continuous future: it settles in the US session (later than
    # the OSE close) and rolls on a different schedule, so on a trending day it can
    # diverge from the OSE 先物ラージ終値 by 1,000+ (e.g. an evening rally after the
    # OSE close). We therefore use it only as an indicative reference / basis, not
    # as the ATM source. Falls back to futures only if the cash index is missing.
    nikkei_for_atm = spot if spot else futures

    # VI (try multiple sources)
    vi = fetch_stooq_vi()
    if vi:
        print('[fetch] VI from stooq: %.2f' % vi, file=sys.stderr)
    else:
        vi = fetch_investing_vi()
        if vi:
            print('[fetch] VI from investing.com: %.2f' % vi, file=sys.stderr)
        else:
            vi = fetch_yahoo_vi()
            if vi:
                print('[fetch] VI from yahoo: %.2f' % vi, file=sys.stderr)
            else:
                print('[fetch] VI unavailable from all sources', file=sys.stderr)

    # OHLC history (25 trading days for technical analysis)
    ohlc_history = fetch_stooq_ohlc_history(25)

    result = {
        'nikkei_close': nikkei_for_atm,   # value used downstream for ATM (cash index preferred; tracks OSE close)
        'nikkei_spot': spot,              # cash index close
        'futures_close': futures,         # front-month futures close
        'futures_source': fut_source,
        'basis': basis,                   # real basis = futures - spot (or None)
        'basis_signal': basis_signal,
        'vi': vi,
        'source': source,
        'timestamp': datetime.now().isoformat(),
        'ohlc_history': ohlc_history,
    }

    print(json.dumps({k: v for k, v in result.items() if k != 'ohlc_history'}, ensure_ascii=False))

    if args.out:
        with open(args.out, 'w') as f:
            json.dump(result, f, ensure_ascii=False)
        print('[fetch] Written to %s' % args.out, file=sys.stderr)

    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fetch Nikkei 225 close and VI')
    parser.add_argument('--out', default=None, help='Output JSON file path')
    args = parser.parse_args()
    run(args)
