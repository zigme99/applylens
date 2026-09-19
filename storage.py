"""Single-user local database with atomic claims and durable submission state."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3

DATA = Path(os.environ.get('APPLYLENS_DATA_DIR', Path(__file__).parent / 'private_data'))

def now():
    return datetime.now(timezone.utc).isoformat()

@contextmanager
def db():
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    con = sqlite3.connect(DATA / 'applylens.db', timeout=20)
    con.row_factory = sqlite3.Row
    con.executescript('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS applications (id TEXT PRIMARY KEY, job TEXT NOT NULL, status TEXT NOT NULL,
    note TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL, resume TEXT NOT NULL DEFAULT '', revision INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, job_id TEXT, message TEXT, created TEXT);
    CREATE TABLE IF NOT EXISTS attempts (job_id TEXT PRIMARY KEY, created TEXT NOT NULL);
    ''')
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback(); raise
    finally:
        con.close()

def get(key, default=None):
    with db() as con:
        row = con.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

def put(key, value):
    with db() as con:
        con.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (key, json.dumps(value)))

def save_configuration(key, value):
    with db() as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute("SELECT value FROM settings WHERE key='revision'").fetchone()
        revision = (json.loads(row[0]) if row else 0) + 1
        for k, v in [(key, value), ('revision', revision), ('enabled', False)]:
            con.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (k, json.dumps(v)))
        con.execute("UPDATE applications SET status='cancelled',note='Profile or rules changed. Queue again with current settings.',updated=? WHERE status IN ('queued','preparing')", (now(),))

def enqueue(job, manual=False):
    with db() as con:
        revision = get('revision', 0)
        old = con.execute('SELECT status,revision FROM applications WHERE id=?', (job['id'],)).fetchone()
        if old and (old['status'] != 'cancelled' or (old['revision'] == revision and not manual)):
            return False
        con.execute('INSERT OR REPLACE INTO applications VALUES (?,?,?,?,?,?,?,?)',
                    (job['id'], json.dumps(job), 'queued', 'Waiting for runner', now(), now(), '', revision))
        return True

def rows():
    with db() as con:
        return [dict(r) | {'job': json.loads(r['job'])} for r in con.execute('SELECT * FROM applications ORDER BY created DESC')]

def update(job_id, status, note, resume=None):
    with db() as con:
        con.execute('UPDATE applications SET status=?,note=?,updated=? WHERE id=?', (status, note, now(), job_id))
        if resume is not None:
            con.execute('UPDATE applications SET resume=? WHERE id=?', (resume, job_id))
        con.execute('INSERT INTO events(job_id,message,created) VALUES (?,?,?)', (job_id, note, now()))

def claim(limit):
    with db() as con:
        con.execute('BEGIN IMMEDIATE')
        used = con.execute('SELECT COUNT(*) FROM attempts WHERE created>=?', (now()[:10],)).fetchone()[0]
        if used >= limit:
            return None
        row = con.execute("SELECT * FROM applications WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
        if not row:
            return None
        con.execute("UPDATE applications SET status='preparing',updated=? WHERE id=?", (now(), row['id']))
        return dict(row) | {'job': json.loads(row['job'])}

def reserve_submission(job_id, revision, limit):
    """Recheck stop/revision and reserve quota immediately before any personal-data transmission."""
    with db() as con:
        con.execute('BEGIN IMMEDIATE')
        settings = {r['key']: json.loads(r['value']) for r in con.execute('SELECT * FROM settings')}
        row = con.execute('SELECT status FROM applications WHERE id=?', (job_id,)).fetchone()
        if not settings.get('enabled') or settings.get('revision', 0) != revision or not row or row['status'] != 'preparing':
            return False
        used = con.execute('SELECT COUNT(*) FROM attempts WHERE created>=?', (now()[:10],)).fetchone()[0]
        if used >= limit:
            return False
        if con.execute('SELECT 1 FROM attempts WHERE job_id=?', (job_id,)).fetchone():
            return False
        con.execute('INSERT INTO attempts VALUES (?,?)', (job_id, now()))
        con.execute("UPDATE applications SET status='submitting',updated=? WHERE id=?", (now(), job_id))
        return True

def recover():
    with db() as con:
        con.execute("UPDATE applications SET status='needs_attention',note='Runner stopped during submission. Check the employer site before doing anything else.' WHERE status='submitting'")
        con.execute("UPDATE applications SET status='queued' WHERE status='preparing'")
