
import os
import json
import hashlib
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
import db

TZ = ZoneInfo(
    os.getenv('APP_TIMEZONE', 'America/New_York')
)

SCOPE = [
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/calendar.calendarlist.readonly'
]


def canvas_sync():
    """Import assignments directly from Canvas, if configured."""
    base = os.getenv('CANVAS_URL', '').rstrip('/')
    token = os.getenv('CANVAS_TOKEN', '')

    if not base or not token:
        raise ValueError(
            'Canvas API credentials are not configured.'
        )

    client = requests.Session()
    client.headers['Authorization'] = 'Bearer ' + token

    def pages(url, params=None):
        while url:
            response = client.get(
                url, params=params, timeout=20
            )
            response.raise_for_status()

            yield from response.json()

            url = response.links.get(
                'next', {}
            ).get('url')

            params = None

    count = 0

    for course in pages(
        base + '/api/v1/courses',
        {
            'enrollment_state': 'active',
            'per_page': 100
        }
    ):
        course_id = course.get('id')

        if not course_id:
            continue

        for item in pages(
            base + f'/api/v1/courses/{course_id}/assignments',
            {'per_page': 100}
        ):
            if not item.get('due_at'):
                continue

            due = datetime.fromisoformat(
                item['due_at'].replace('Z', '+00:00')
            ).astimezone(TZ)

            db.add_assignment({
                'id': f"canvas-{course_id}-{item['id']}",
                'title': item['name'],
                'course': course.get('name', 'Canvas'),
                'due_date': due.date().isoformat()
            })

            count += 1

    return {'imported_or_seen': count}


def oauth_config(redirect_url):
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    secret = os.getenv('GOOGLE_CLIENT_SECRET')

    if not client_id or not secret:
        raise ValueError(
            'Google OAuth credentials are missing from .env'
        )

    return {
        'web': {
            'client_id': client_id,
            'client_secret': secret,
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'redirect_uris': [redirect_url]
        }
    }


def calendar_service():
    raw = db.setting('google_token')

    if not raw:
        raise ValueError(
            'Google Calendar is not connected. Click Connect Google Calendar.'
        )

    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    credentials = Credentials.from_authorized_user_info(
        json.loads(raw),
        scopes=SCOPE
    )

    if not credentials.valid:
        if not credentials.refresh_token:
            raise ValueError('Reconnect your Google account.')

        credentials.refresh(Request())

        db.setting(
            'google_token',
            credentials.to_json()
        )

    return build(
        'calendar',
        'v3',
        credentials=credentials,
        cache_discovery=False
    )


def google_sync():
    """Import Canvas deadlines and other Google Calendar events."""
    service = calendar_service()

    start = datetime.now(timezone.utc) - timedelta(days=30)
    end = start + timedelta(days=396)

    canvas_name = os.getenv(
        'CANVAS_CALENDAR_NAME', 'Canvas'
    ).lower().strip()

    calendars = []
    page_token = None

    while True:
        result = service.calendarList().list(
            pageToken=page_token
        ).execute()

        calendars.extend(result.get('items', []))

        page_token = result.get('nextPageToken')

        if not page_token:
            break

    imported = 0
    busy_events = 0
    calendar_names = []

    for calendar in calendars:
        calendar_id = calendar['id']
        name = calendar.get('summary', '')
        calendar_names.append(name)

        is_canvas = (
            bool(canvas_name)
            and canvas_name in name.lower()
        )

        token = None

        while True:
            result = service.events().list(
                calendarId=calendar_id,
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True,
                maxResults=250,
                pageToken=token
            ).execute()

            for item in result.get('items', []):
                if item.get('status') == 'cancelled':
                    continue

                title = item.get(
                    'summary', 'Untitled event'
                )

                begin = item.get('start', {})
                finish = item.get('end', {})

                if is_canvas:
                    # Canvas calendar feeds can include both
                    # assignments and ordinary calendar events.
                    # We import dated items as candidate deadlines.
                    raw_date = (
                        begin.get('dateTime')
                        or begin.get('date')
                    )

                    if not raw_date:
                        continue

                    if 'T' in raw_date:
                        due = datetime.fromisoformat(
                            raw_date.replace('Z', '+00:00')
                        ).astimezone(TZ).date()
                    else:
                        due = datetime.fromisoformat(
                            raw_date
                        ).date()

                    identifier = hashlib.sha256(
                        (calendar_id + ':' + item['id']).encode()
                    ).hexdigest()[:24]

                    assignment_id = 'gcanvas-' + identifier

                    with db.connect() as conn:
                        conn.execute('''
                            INSERT INTO assignments
                            (id, title, course, due_date,
                             difficulty, estimated_hours)
                            VALUES (?, ?, ?, ?, '', NULL)
                            ON CONFLICT(id) DO UPDATE SET
                                title=excluded.title,
                                course=excluded.course,
                                due_date=excluded.due_date
                        ''', (
                            assignment_id,
                            title,
                            name,
                            due.isoformat()
                        ))

                    imported += 1
                    continue

                # Other Google Calendar events block study time.
                if item.get('transparency') == 'transparent':
                    continue

                if item.get(
                    'description', ''
                ).startswith('StudyFlow session:'):
                    continue

                if 'dateTime' in begin and 'dateTime' in finish:
                    a = datetime.fromisoformat(
                        begin['dateTime'].replace('Z', '+00:00')
                    ).astimezone(TZ)

                    b = datetime.fromisoformat(
                        finish['dateTime'].replace('Z', '+00:00')
                    ).astimezone(TZ)

                    # Simple demo supports same-day commitments.
                    if a.date() != b.date():
                        continue

                    day = a.date().isoformat()
                    from_time = a.strftime('%H:%M')
                    to_time = b.strftime('%H:%M')

                elif 'date' in begin:
                    day = begin['date']
                    from_time = '00:00'
                    to_time = '23:59'
                else:
                    continue

                identifier = hashlib.sha256(
                    (calendar_id + ':' + item['id']).encode()
                ).hexdigest()[:24]

                commitment_id = 'google-' + identifier

                with db.connect() as conn:
                    old = conn.execute(
                        'SELECT flexibility FROM commitments WHERE id=?',
                        (commitment_id,)
                    ).fetchone()

                    flexibility = (
                        old['flexibility'] if old else 'Fixed'
                    )

                    conn.execute('''
                        INSERT OR REPLACE INTO commitments
                        (id, title, type, date,
                         start_time, end_time,
                         flexibility, repeat_weekly)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                    ''', (
                        commitment_id,
                        title,
                        'Google',
                        day,
                        from_time,
                        to_time,
                        flexibility
                    ))

                busy_events += 1

            token = result.get('nextPageToken')

            if not token:
                break

    return {
        'events_synced': imported + busy_events,
        'canvas_items_imported': imported,
        'other_events_imported': busy_events,
        'calendars_scanned': calendar_names
    }


def google_add_session(s):
    """Add an approved study session to the primary calendar."""
    service = calendar_service()

    event = {
        'summary': s['title'],
        'description': 'StudyFlow session: ' + s['id'],
        'start': {
            'dateTime': datetime.fromisoformat(
                s['starts']
            ).replace(tzinfo=TZ).isoformat()
        },
        'end': {
            'dateTime': datetime.fromisoformat(
                s['ends']
            ).replace(tzinfo=TZ).isoformat()
        }
    }

    return service.events().insert(
        calendarId='primary',
        body=event
    ).execute()
