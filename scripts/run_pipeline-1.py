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

    nikkei = args.nikkei
    vi = args.vi

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

    result = subprocess.run(extract_cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print('ERROR: extract.py failed', file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)

    # Step 2.1: Weekly trend (multi-week WoW for futures OI by participant)
    # Reads all *_indexfut_oi_by_tp.xlsx files in datadir, writes weekly_trend.json
    # for the standalone weekly_trend.html page. Non-fatal: if it fails or no
    # weekly archive exists yet, the page just shows "データ蓄積中".
    print('\n=== Step 2.1: Building weekly trend ===')
    weekly_script = os.path.join(scripts_dir, 'extract_weekly_trend.py')
    if os.path.exists(weekly_script):
        weekly_json = os.path.join(datadir, 'weekly_trend.json')
        result = subprocess.run(
            [sys.executable, weekly_script,
             '--data-dir', datadir,
             '--out', weekly_json],
            capture_output=True, text=True
        )
        print(result.stdout)
        if result.returncode != 0:
            print('[WARN] extract_weekly_trend.py failed (non-fatal):', file=sys.stderr)
            print(result.stderr, file=sys.stderr)
    else:
        print('[SKIP] scripts/extract_weekly_trend.py not found')

    # Step 2.5: Generate ⑧ assessment (if API key available)
    gemini_key = os.environ.get('GEMINI_API_KEY', '')
    if gemini_key:
        print('\n=== Step 2.5: Generating assessment (Gemini) ===')
        assess_cmd = [sys.executable, os.path.join(scripts_dir, 'generate_assessment.py'),
                      '--data', data_json, '--key', gemini_key]
        result = subprocess.run(assess_cmd, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
    else:
        print('\n[SKIP] No GEMINI_API_KEY — ⑧ assessment will use placeholder')

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

    # Summary
    print('\n=== Pipeline Complete ===')
    for f in os.listdir(outdir):
        if f.endswith(('.html', '.md', '.txt')):
            fp = os.path.join(outdir, f)
            print('  %s (%.1f KB)' % (f, os.path.getsize(fp) / 1024))


if __name__ == '__main__':
    main()
