#!/usr/bin/env python3
"""
JPX Market Analysis - Pipeline Runner (run_pipeline.py)
========================================================
Orchestrates: fetch_market → extract → render

Usage:
    python scripts/run_pipeline.py --datadir data/
    python scripts/run_pipeline.py --datadir data/ --nikkei 53739 --vi 49.45
    
If --nikkei/--vi are not provided, auto-fetches from web.
"""

import argparse
import json
import os
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description='JPX Analysis Pipeline Runner')
    parser.add_argument('--datadir', default='data', help='Directory with Excel files')
    parser.add_argument('--outdir', default='.', help='Output directory for generated files')
    parser.add_argument('--nikkei', type=float, default=None, help='Nikkei 225 close (auto-fetch if omitted)')
    parser.add_argument('--vi', type=float, default=None, help='Nikkei VI close (auto-fetch if omitted)')
    args = parser.parse_args()

    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(scripts_dir)

    datadir = os.path.join(repo_root, args.datadir) if not os.path.isabs(args.datadir) else args.datadir
    outdir = os.path.join(repo_root, args.outdir) if not os.path.isabs(args.outdir) else args.outdir

    # Step 0: unpack the single carry-over state.json into the 4 history files
    # so the extractors run unchanged. (See state_bundle.py.)
    try:
        import state_bundle
        state_path = os.path.join(datadir, 'state.json')
        state_bundle.unpack(state_path, datadir)
    except Exception as _e:
        print('[state] unpack skipped: %s' % _e)

    nikkei = args.nikkei
    vi = args.vi
    basis = None
    spot = None

    # Step 1: Fetch market data if not provided
    if nikkei is None or vi is None:
        print('=== Step 1: Fetching market data ===')
        market_json = os.path.join(datadir, 'market_latest.json')
        result = subprocess.run(
            [sys.executable, os.path.join(scripts_dir, 'fetch_market.py'), '--out', market_json],
            capture_output=True, text=True
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        if os.path.exists(market_json):
            with open(market_json) as f:
                market = json.load(f)
            if nikkei is None and market.get('nikkei_close'):
                nikkei = market['nikkei_close']
            if vi is None and market.get('vi'):
                vi = market['vi']
            basis = market.get('basis')
            spot = market.get('nikkei_spot')

        if nikkei is None:
            print('[WARN] Nikkei close not available. Using ATM from futures as fallback.', file=sys.stderr)
        if vi is None:
            print('[WARN] VI not available. OTM probabilities will be skipped.', file=sys.stderr)

    print('Nikkei: %s / VI: %s' % (nikkei, vi))

    # Step 2: Extract data
    print('\n=== Step 2: Extracting data ===')
    data_json = os.path.join(datadir, 'data.json')
    extract_cmd = [sys.executable, os.path.join(scripts_dir, 'extract.py'),
                   '--dir', datadir, '--out', data_json]
    if nikkei:
        extract_cmd += ['--nikkei', str(nikkei)]
    if vi:
        extract_cmd += ['--vi', str(vi)]
    if basis is not None:
        extract_cmd += ['--basis', str(basis)]
    if spot is not None:
        extract_cmd += ['--spot', str(spot)]

    result = subprocess.run(extract_cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print('ERROR: extract.py failed', file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)

    # Step 2.5: ⑧ assessment — manual override first, else Gemini
    # Priority: data/manual_assessment_YYYYMMDD.md (dated, must match the data
    # date) > Gemini (if GEMINI_API_KEY) > placeholder. The dated manual file
    # lets a human-written (Claude) analysis appear with the 👤手動分析 badge,
    # and the date match prevents a stale older file from being reused.
    print('\n=== Step 2.5: ⑧ assessment ===')
    data_date = None
    try:
        with open(data_json, encoding='utf-8') as f:
            _d = json.load(f)
        data_date = (_d.get('metadata') or {}).get('date')
    except Exception as e:
        print('[WARN] could not read data.json for date: %s' % e, file=sys.stderr)

    manual_used = False
    if data_date:
        manual_path = os.path.join(datadir, 'manual_assessment_%s.md' % data_date)
        if os.path.exists(manual_path):
            try:
                with open(manual_path, encoding='utf-8') as f:
                    manual_text = f.read().strip()
                if manual_text:
                    with open(data_json, encoding='utf-8') as f:
                        dj = json.load(f)
                    dj['s08_assessment'] = manual_text
                    dj['s08_source'] = 'manual'
                    with open(data_json, 'w', encoding='utf-8') as f:
                        json.dump(dj, f, ensure_ascii=False, indent=2)
                    manual_used = True
                    print('[assessment] manual override: %s (%d chars) -> manual'
                          % (os.path.basename(manual_path), len(manual_text)))
            except Exception as e:
                print('[WARN] failed to inject manual assessment: %s' % e, file=sys.stderr)
        else:
            print('[assessment] no manual file for %s (looked for %s)'
                  % (data_date, os.path.basename(manual_path)))

    if not manual_used:
        # No manual ⑧ → deterministic template assessment from real numbers.
        # (Accurate, no API key. Replaces the old Gemini fallback.)
        print('[assessment] no manual file → deterministic 定型⑧')
        assess_cmd = [sys.executable, os.path.join(scripts_dir, 'generate_assessment.py'),
                      '--data', data_json]
        result = subprocess.run(assess_cmd, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(result.stderr)

    # Step 2.6: Build time-series cards (建玉推移 / 週次手口推移)
    # These regenerate oi_timeseries.json and weekly_trend.json which render.py
    # embeds into the dashboard. Without this step the 建玉推移 and 週次手口推移
    # cards stay stale even when new Excel files are pushed. Non-fatal: a missing
    # weekly file (non-weekly days) should not break the whole pipeline.
    print('\n=== Step 2.6: Building time-series cards ===')
    oi_ts_cmd = [sys.executable, os.path.join(scripts_dir, 'extract_oi_timeseries.py'),
                 '--data-dir', datadir,
                 '--out', os.path.join(datadir, 'oi_timeseries.json'),
                 '--top-strikes', '6']
    if nikkei:
        oi_ts_cmd += ['--nikkei', str(nikkei)]
    result = subprocess.run(oi_ts_cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print('[WARN] extract_oi_timeseries.py failed (建玉推移 card may be stale)', file=sys.stderr)
        print(result.stderr, file=sys.stderr)

    wt_cmd = [sys.executable, os.path.join(scripts_dir, 'extract_weekly_trend.py'),
              '--data-dir', datadir,
              '--out', os.path.join(datadir, 'weekly_trend.json')]
    result = subprocess.run(wt_cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print('[WARN] extract_weekly_trend.py failed (週次手口推移 card may be stale)', file=sys.stderr)
        print(result.stderr, file=sys.stderr)

    # Step 2.7: Extract implied volatility (IVスマイル card) from the OSE
    # theoretical-price file (oseYYYYMMDDtp.csv). Non-fatal: if the tp.csv is not
    # present, the IVスマイル card simply shows an empty state.
    iv_cmd = [sys.executable, os.path.join(scripts_dir, 'extract_iv.py'),
              '--data-dir', datadir,
              '--out', os.path.join(datadir, 'iv.json')]
    result = subprocess.run(iv_cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print('[WARN] extract_iv.py failed (IVスマイル card may be empty)', file=sys.stderr)
        print(result.stderr, file=sys.stderr)

    # Step 2.8: Accumulate the daily IV / skew time-series (IV推移 card). Reads
    # the ose<date>tp.csv files present and upserts into iv_timeseries.json, so
    # the history grows one point per day. Non-fatal.
    ivts_cmd = [sys.executable, os.path.join(scripts_dir, 'extract_iv_timeseries.py'),
                '--data-dir', datadir,
                '--out', os.path.join(datadir, 'iv_timeseries.json')]
    result = subprocess.run(ivts_cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print('[WARN] extract_iv_timeseries.py failed (IV推移 card may be stale)', file=sys.stderr)
        print(result.stderr, file=sys.stderr)

    # Step 2.9: Per-strike greeks + GEX profile (グリークス/GEX card). Reads the
    # current open_interest + ose<date>tp.csv (and prior day for the OI x IV
    # sign of Convention B) and writes greeks.json. Non-fatal.
    greeks_cmd = [sys.executable, os.path.join(scripts_dir, 'extract_greeks.py'),
                  '--data-dir', datadir,
                  '--out', os.path.join(datadir, 'greeks.json')]
    result = subprocess.run(greeks_cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print('[WARN] extract_greeks.py failed (グリークス/GEX card may be empty)', file=sys.stderr)
        print(result.stderr, file=sys.stderr)

    # Step 2.95: Per-broker J-NET (cross) volume + history (大口手口 card).
    # Accumulates jnet_history.json so broker cross activity (e.g. UBS) can be
    # tracked vs price over time. Non-fatal.
    jnet_cmd = [sys.executable, os.path.join(scripts_dir, 'extract_jnet.py'),
                '--data-dir', datadir,
                '--out', os.path.join(datadir, 'jnet.json')]
    result = subprocess.run(jnet_cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print('[WARN] extract_jnet.py failed (大口手口 card may be empty)', file=sys.stderr)
        print(result.stderr, file=sys.stderr)

    # Step 2.97: Weekly option OI by participant (参加者別OP建玉 card). Only runs
    # when a *nk225op_oi_by_tp*.xlsx is present (published Mondays). Non-fatal.
    ow_cmd = [sys.executable, os.path.join(scripts_dir, 'extract_opt_weekly.py'),
              '--data-dir', datadir,
              '--out', os.path.join(datadir, 'opt_weekly.json')]
    result = subprocess.run(ow_cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print('[WARN] extract_opt_weekly.py failed (参加者別OP建玉 card may be empty)', file=sys.stderr)
        print(result.stderr, file=sys.stderr)

    # Step 2.98: merge weekly futures + weekly options per participant.
    pos_cmd = [sys.executable, os.path.join(scripts_dir, 'extract_positions.py'),
               '--data-dir', datadir,
               '--out', os.path.join(datadir, 'positions.json')]
    result = subprocess.run(pos_cmd, capture_output=True, text=True)
    print(result.stdout)

    # Step 2.985: aggregate participant volume across all four session files
    # (day/night x auction/J-NET). Optional — older days only have the day
    # J-NET file, in which case this simply reports fewer venues.
    vf_cmd = [sys.executable, os.path.join(scripts_dir, 'extract_venue_flow.py'),
              '--data-dir', datadir,
              '--out', os.path.join(datadir, 'venue_flow.json')]
    result = subprocess.run(vf_cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print('[WARN] extract_venue_flow.py failed (価格帯の内訳 card may be stale)', file=sys.stderr)

    # Step 2.99: accumulate weekly per-broker nets into broker_history.json
    # (persistent across weeks; powers the 大口動向 card). Runs only when
    # weekly files are present, otherwise leaves the existing history intact.
    bh_cmd = [sys.executable, os.path.join(scripts_dir, 'extract_broker_history.py'),
              '--data-dir', datadir,
              '--out', os.path.join(datadir, 'broker_history.json')]
    result = subprocess.run(bh_cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print('[WARN] extract_broker_history.py failed (大口動向 card may be stale)', file=sys.stderr)
        print(result.stderr, file=sys.stderr)

    # Step 3: Render outputs
    print('\n=== Step 3: Rendering outputs ===')
    render_cmd = [sys.executable, os.path.join(scripts_dir, 'render.py'),
                  '--data', data_json, '--outdir', outdir]

    result = subprocess.run(render_cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print('ERROR: render.py failed', file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)

    # Step 4: re-pack the 4 history files into the single carry-over state.json
    try:
        import state_bundle
        state_bundle.pack(datadir, os.path.join(datadir, 'state.json'))
    except Exception as _e:
        print('[state] pack skipped: %s' % _e)

    # Summary
    print('\n=== Pipeline Complete ===')
    for f in os.listdir(outdir):
        if f.endswith(('.html', '.md', '.txt')):
            fp = os.path.join(outdir, f)
            print('  %s (%.1f KB)' % (f, os.path.getsize(fp) / 1024))


if __name__ == '__main__':
    main()
