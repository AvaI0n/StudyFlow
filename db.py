
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, date, time
from pathlib import Path

DB = os.getenv(
    'DATABASE_PATH',
    str(Path(__file__).with_name('studyflow.db'))
)

def connect():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def setup():
    with connect() as c:
        c.execute('''
            CREATE TABLE IF NOT EXISTS assignments (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                course TEXT,
                due_date TEXT NOT NULL,
                difficulty TEXT,
                estimated_hours REAL
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS commitments (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                type TEXT,
                date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                flexibility TEXT,
                repeat_weekly INTEGER DEFAULT 0
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                assignment_id TEXT NOT NULL,
                title TEXT NOT NULL,
                starts TEXT NOT NULL,
                ends TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        columns = [
            r['name']
            for r in c.execute(
                'PRAGMA table_info(assignments)'
            )
        ]

        if 'completed' not in columns:
            c.execute(
                'ALTER TABLE assignments '
                'ADD COLUMN completed INTEGER DEFAULT 0'
            )

def all_rows(table):
    if table not in ('assignments', 'commitments', 'sessions'):
        raise ValueError('Invalid table')

    with connect() as c:
        return [
            dict(r)
            for r in c.execute('SELECT * FROM ' + table)
        ]

def add_assignment(a):
    with connect() as c:
        c.execute('''
            INSERT OR IGNORE INTO assignments
            (id, title, course, due_date,
             difficulty, estimated_hours)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            a.get('id') or uuid.uuid4().hex,
            a['title'],
            a.get('course', ''),
            a['due_date'],
            a.get('difficulty', ''),
            a.get('estimated_hours')
        ))

def setting(key, value=None):
    with connect() as c:
        if value is not None:
            c.execute(
                'INSERT OR REPLACE INTO settings VALUES (?, ?)',
                (key, value)
            )

        r = c.execute(
            'SELECT value FROM settings WHERE key=?',
            (key,)
        ).fetchone()

        return r['value'] if r else None

def is_busy(start, end, exclude_session_id=None):
    # Both fixed and flexible events block scheduling.
    with connect() as c:
        rows = [
            dict(x)
            for x in c.execute('SELECT * FROM commitments')
        ]

        plans = [
            dict(x)
            for x in c.execute("""
                SELECT * FROM sessions
                WHERE status IN ('pending', 'approved')
            """)
        ]

    for x in rows:
        if (x['flexibility'] or '').lower() == 'free':
            continue

        first_day = date.fromisoformat(x['date'])

        same_day = (
            (
                x['repeat_weekly']
                and start.date() >= first_day
                and start.weekday() == first_day.weekday()
            )
            or start.date() == first_day
        )

        if same_day:
            a = datetime.combine(
                start.date(),
                time.fromisoformat(x['start_time'])
            )

            b = datetime.combine(
                start.date(),
                time.fromisoformat(x['end_time'])
            )

            if start < b and end > a:
                return True

    for s in plans:
        if s['id'] == exclude_session_id:
            continue

        a = datetime.fromisoformat(s['starts'])
        b = datetime.fromisoformat(s['ends'])

        if start < b and end > a:
            return True

    return False

def priority(a):
    days = max(
        0,
        (
            date.fromisoformat(a['due_date']) -
            date.today()
        ).days
    )

    difficulty = {
        'Easy': 1,
        'Medium': 2,
        'Hard': 3
    }.get(a['difficulty'], 2)

    hours = float(a['estimated_hours'] or 2)

    return min(
        100,
        round(
            65 / (days + 1) +
            difficulty * 8 +
            min(20, hours * 3)
        )
    )

def suggest(assignment_id):
    with connect() as c:
        row = c.execute(
            'SELECT * FROM assignments WHERE id=?',
            (assignment_id,)
        ).fetchone()

    if not row:
        raise ValueError('Assignment not found')

    a = dict(row)

    if a['completed']:
        raise ValueError('Assignment is already complete')

    remaining = min(
        12,
        max(0.5, float(a['estimated_hours'] or 2))
    )

    deadline = date.fromisoformat(a['due_date'])
    today = date.today()

    if deadline < today:
        raise ValueError('Assignment due date is in the past')

    created = []

    last_day = min(
        deadline,
        today + timedelta(days=14)
    )

    for d in range((last_day - today).days + 1):
        day = today + timedelta(days=d)

        for hr in range(9, 21):
            for minute in (0, 30):
                duration = min(
                    90,
                    int(remaining * 60)
                )

                if duration < 30:
                    continue

                start = datetime.combine(
                    day,
                    time(hr, minute)
                )

                end = start + timedelta(minutes=duration)

                if (
                    start < datetime.now() + timedelta(minutes=10)
                    or end.date() != day
                    or end.hour > 22
                ):
                    continue

                if is_busy(start, end):
                    continue

                record = {
                    'id': uuid.uuid4().hex,
                    'assignment_id': assignment_id,
                    'title': 'Study: ' + a['title'],
                    'starts': start.isoformat(timespec='minutes'),
                    'ends': end.isoformat(timespec='minutes'),
                    'status': 'pending'
                }

                with connect() as c:
                    c.execute(
                        'INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?)',
                        tuple(record.values())
                    )

                created.append(record)
                remaining -= duration / 60
                break

            if (
                created and
                created[-1]['starts'].startswith(day.isoformat())
            ):
                break

        if remaining <= 0 or len(created) >= 6:
            break

    return {
        'suggestions': created,
        'hours_unscheduled': round(max(0, remaining), 1)
    }
