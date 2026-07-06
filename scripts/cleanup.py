#!/usr/bin/env python3
"""Tidy the working folder so only what matters stays at the top level.

Keeps:
  - index.html                (the only file you deploy)
  - state.json                (the only state you carry to the next run)
  - manual_assessment_*.md     newest N (default 7); older ones -> assessments/
Removes (regenerated every run, safe to delete):
  - greeks.json jnet.json iv.json weekly_trend.json opt_weekly.json data.json
  - the 4 individual history files IF a fresh state.json exists (they live inside it)
Deletes known junk:
  - *_DEMO.json, cache_*.json

Dry-run by default. Add --apply to actually move/delete.
    python cleanup.py --dir /path/to/outputs --keep-md 7 --apply
"""
import argparse
import glob
import os
import shutil

SCRATCH = ['greeks.json', 'jnet.json', 'iv.json', 'weekly_trend.json',
           'opt_weekly.json', 'data.json']
STATE_FILES = ['greeks_history.json', 'jnet_history.json',
               'iv_timeseries.json', 'oi_timeseries.json']
JUNK_GLOBS = ['*_DEMO.json', 'cache_*.json', '*_DEMO*.json']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='.')
    ap.add_argument('--keep-md', type=int, default=7)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--drop-unbundled', action='store_true',
                    help='also delete the 4 history files when state.json exists')
    a = ap.parse_args()
    d = a.dir
    act = a.apply
    tag = '' if act else '[dry-run] '

    def rm(p):
        print('%sdelete  %s' % (tag, os.path.basename(p)))
        if act:
            os.remove(p)

    def mv(p, dst):
        print('%sarchive %s -> %s/' % (tag, os.path.basename(p), os.path.basename(dst)))
        if act:
            os.makedirs(dst, exist_ok=True)
            shutil.move(p, os.path.join(dst, os.path.basename(p)))

    # 1) junk
    for g in JUNK_GLOBS:
        for p in glob.glob(os.path.join(d, g)):
            rm(p)
    # 2) scratch (regenerated each run)
    for name in SCRATCH:
        p = os.path.join(d, name)
        if os.path.exists(p):
            rm(p)
    # 3) history files -> only if a fresh state.json exists and user opts in
    if a.drop_unbundled and os.path.exists(os.path.join(d, 'state.json')):
        for name in STATE_FILES:
            p = os.path.join(d, name)
            if os.path.exists(p):
                rm(p)
    # 4) archive old manual_assessment md (keep newest N)
    mds = sorted(glob.glob(os.path.join(d, 'manual_assessment_*.md')))
    if len(mds) > a.keep_md:
        for p in mds[:-a.keep_md]:
            mv(p, os.path.join(d, 'assessments'))

    if not act:
        print('\n(dry-run only — re-run with --apply to make changes)')


if __name__ == '__main__':
    main()
