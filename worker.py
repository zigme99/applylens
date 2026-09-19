"""Local background runner; one process per data directory, no browser sessions stored."""
import argparse
import fcntl
import os
import time
from pathlib import Path
import storage as store
from sources import discover, fetch_board, match
from resumes import tailor, docx_bytes
from automation import apply_lever, NeedsAttention


def run_cycle():
    store.put('heartbeat', store.now())
    if not store.get('enabled', False):
        return
    profile, rules = store.get('profile', {}), store.get('rules', {})
    if not profile.get('resume') or not profile.get('name') or not profile.get('email') or not rules.get('roles'):
        store.put('enabled', False); return
    if time.time() - store.get('last_search_epoch', 0) > 1800:
        jobs, errors = discover(rules['boards'])
        store.put('last_search_epoch', time.time())
        store.put('search_errors', errors)
        store.put('last_search', store.now())
        store.put('jobs', jobs)
        for job in jobs:
            if not match(job, rules, resume=profile['resume']) and store.get('enabled'):
                store.enqueue(job)
    item = store.claim(rules['daily_limit'])
    if not item:
        return
    job = item['job']
    try:
        if item['revision'] != store.get('revision', 0):
            store.update(job['id'], 'cancelled', 'Settings changed. Queue again with the current rules.'); return
        # Never apply to a cached job without verifying it is still listed and still matches.
        current = next((j for j in fetch_board(job['source']) if j['id'] == job['id']), None)
        if not current:
            store.update(job['id'], 'closed', 'The job is no longer in the live feed.'); return
        reasons = match(current, rules, resume=profile['resume'])
        if reasons:
            store.update(job['id'], 'cancelled', '; '.join(reasons)); return
        text, _ = tailor(profile['resume'], current['description'])
        store.update(job['id'], 'preparing', 'Prepared a resume using only your original text.', text)
        path = store.DATA / (str(abs(hash(job['id']))) + '.docx')
        path.write_bytes(docx_bytes(text)); os.chmod(path, 0o600)
        try:
            note = apply_lever(current, profile, path,
                authorize=lambda: store.reserve_submission(job['id'], item['revision'], rules['daily_limit']),
                still_enabled=lambda: store.get('enabled', False) and store.get('revision', 0) == item['revision'])
            store.update(job['id'], 'submitted', note)
        finally:
            path.unlink(missing_ok=True)
    except NeedsAttention as exc:
        store.update(job['id'], 'needs_attention', str(exc))
    except Exception:
        # Do not persist raw provider exceptions that might contain personal data.
        store.update(job['id'], 'needs_attention', 'The runner encountered an error. Check the employer application before retrying.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    store.DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (store.DATA / 'worker.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        store.recover()
        while True:
            try:
                run_cycle()
                store.put('runner_error', '')
            except Exception:
                store.put('runner_error', 'Search or runner failed. Check source settings and your connection.')
                store.put('heartbeat', store.now())
            if args.once:
                return
            time.sleep(10)

if __name__ == '__main__':
    main()
