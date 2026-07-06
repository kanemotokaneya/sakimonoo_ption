#!/usr/bin/env python3
"""Bundle the pipeline's persistent state into a single state.json.

The dashboard needs only the four *history/timeseries* files to carry over
between runs (self-recovery + accumulating charts):

    greeks_history.json, jnet_history.json,
    iv_timeseries.json,  oi_timeseries.json

Everything else the pipeline writes (greeks.json, jnet.json, iv.json,
weekly_trend.json, opt_weekly.json, data.json) is regenerated every run, and
the live site is a single self-contained index.html. So the only thing you
need to carry day-to-day is state.json (+ the day's raw uploads).

Usage:
    python state_bundle.py unpack --state state.json --data-dir data
    python state_bundle.py pack   --state state.json --data-dir data
"""
import argparse
import json
import os

STATE_FILES = [
    'greeks_history.json',
    'jnet_history.json',
    'iv_timeseries.json',
    'oi_timeseries.json',
]


def unpack(state_path, data_dir):
    """state.json -> individual files in data_dir (so extractors run unchanged)."""
    if not os.path.exists(state_path):
        return False
    try:
        with open(state_path, encoding='utf-8') as f:
            state = json.load(f)
    except Exception as e:
        print('[state] cannot read %s: %s' % (state_path, e))
        return False
    os.makedirs(data_dir, exist_ok=True)
    n = 0
    for name in STATE_FILES:
        key = name[:-5]  # strip .json
        if key in state and state[key] is not None:
            with open(os.path.join(data_dir, name), 'w', encoding='utf-8') as f:
                json.dump(state[key], f, ensure_ascii=False, separators=(',', ':'))
            n += 1
    print('[state] unpacked %d/%d files from %s' % (n, len(STATE_FILES), state_path))
    return True


def pack(data_dir, state_path):
    """individual files in data_dir -> state.json (the one file you carry)."""
    state = {}
    n = 0
    for name in STATE_FILES:
        p = os.path.join(data_dir, name)
        if os.path.exists(p):
            try:
                with open(p, encoding='utf-8') as f:
                    state[name[:-5]] = json.load(f)
                n += 1
            except Exception as e:
                print('[state] skip %s: %s' % (name, e))
    with open(state_path, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, separators=(',', ':'))
    sz = os.path.getsize(state_path) / 1024
    print('[state] packed %d files -> %s (%.0f KB)' % (n, state_path, sz))
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['pack', 'unpack'])
    ap.add_argument('--state', default='state.json')
    ap.add_argument('--data-dir', default='data')
    a = ap.parse_args()
    if a.cmd == 'unpack':
        unpack(a.state, a.data_dir)
    else:
        pack(a.data_dir, a.state)


if __name__ == '__main__':
    main()
