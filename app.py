
import os
import uuid
import hmac
from datetime import date, datetime

from flask import (
    Flask, render_template, request,
    jsonify, redirect, url_for, session
)
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()

import db
import integrations

app = Flask(__name__)

app.secret_key = os.getenv(
    'SECRET_KEY',
    'local-development-only-change-me'
)

app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_proto=1,
    x_host=1
)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax'
)

db.setup()

@app.before_request
def protect_demo():
    password = os.getenv('APP_PASSWORD')

    if (
        not password
        or request.endpoint in ('login', 'static', 'google_callback')
    ):
        return

    if session.get('logged_in'):
        return

    if request.path.startswith('/api/'):
        return jsonify(error='Sign in first'), 401

    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and hmac.compare_digest(
        request.form.get('password', ''),
        os.getenv('APP_PASSWORD', '')
    ):
        session['logged_in'] = True
        return redirect('/')

    return '''
    <form method="post"
        style="max-width:340px;margin:100px auto;font:18px Arial">
    <h2>StudyFlow Demo Login</h2>
    <input type="password" name="password"
            placeholder="Password" required>
    <button>Sign in</button>
    </form>
    '''

@app.get('/')
def home():
    return render_template('index.html')

@app.route('/api/assignments', methods=['GET', 'POST'])
def assignments():
    if request.method == 'GET':
        return jsonify(db.all_rows('assignments'))

    data = request.get_json(silent=True) or {}

    try:
        if not str(data.get('title', '')).strip():
            raise ValueError('Title is required')

        date.fromisoformat(data['due_date'])

        data['title'] = data['title'].strip()
        data['id'] = data.get('id') or uuid.uuid4().hex

        db.add_assignment(data)

        return jsonify(id=data['id']), 201

    except (ValueError, KeyError, TypeError) as e:
        return jsonify(error=str(e)), 400

@app.route(
    '/api/assignments/<ident>',
    methods=['PATCH', 'DELETE']
)
def assignment_item(ident):
    if request.method == 'DELETE':
        with db.connect() as c:
            c.execute(
                'DELETE FROM assignments WHERE id=?',
                (ident,)
            )

        return jsonify(ok=True)

    data = request.get_json(silent=True) or {}

    allowed = {
        'difficulty',
        'estimated_hours',
        'completed'
    }

    updates = {
        k: v for k, v in data.items()
        if k in allowed
    }

    if not updates:
        return jsonify(error='No editable fields supplied'), 400

    try:
        if (
            'estimated_hours' in updates
            and updates['estimated_hours'] not in (None, '')
        ):
            updates['estimated_hours'] = max(
                0.5,
                float(updates['estimated_hours'])
            )

        if 'completed' in updates:
            updates['completed'] = int(
                bool(updates['completed'])
            )

    except (ValueError, TypeError):
        return jsonify(error='Invalid hours'), 400

    with db.connect() as c:
        c.execute(
            'UPDATE assignments SET ' +
            ','.join(k + '=?' for k in updates) +
            ' WHERE id=?',
            [*updates.values(), ident]
        )

    return jsonify(ok=True)

@app.route('/api/commitments', methods=['GET', 'POST'])
def commitments():
    if request.method == 'GET':
        return jsonify(db.all_rows('commitments'))

    data = request.get_json(silent=True) or {}

    try:
        if not str(data.get('title', '')).strip():
            raise ValueError('Title is required')

        date.fromisoformat(data['date'])

        if data['start_time'] >= data['end_time']:
            raise ValueError('End must follow start')

        ident = data.get('id') or uuid.uuid4().hex

        with db.connect() as c:
            c.execute('''
                INSERT INTO commitments
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ident,
                data['title'],
                data.get('type', 'Personal'),
                data['date'],
                data['start_time'],
                data['end_time'],
                data.get('flexibility', 'Fixed'),
                int(bool(data.get('repeat_weekly')))
            ))

        return jsonify(id=ident), 201

    except (ValueError, KeyError, TypeError) as e:
        return jsonify(error=str(e)), 400

@app.route(
    '/api/commitments/<ident>',
    methods=['DELETE', 'PATCH']
)
def commitment_item(ident):
    with db.connect() as c:
        if request.method == 'DELETE':
            c.execute(
                'DELETE FROM commitments WHERE id=?',
                (ident,)
            )
        else:
            flexibility = (
                request.get_json(silent=True) or {}
            ).get('flexibility')

            if flexibility not in ('Fixed', 'Flexible', 'Free'):
                return jsonify(error='Invalid classification'), 400

            c.execute(
                'UPDATE commitments SET flexibility=? WHERE id=?',
                (flexibility, ident)
            )

    return jsonify(ok=True)

@app.get('/api/sessions')
def sessions():
    return jsonify(db.all_rows('sessions'))

@app.post('/api/suggest/<assignment_id>')
def suggest(assignment_id):
    try:
        if db.setting('google_token'):
            integrations.google_sync()

        return jsonify(db.suggest(assignment_id))

    except Exception as e:
        return jsonify(error=str(e)), 400

@app.route(
    '/api/sessions/<ident>',
    methods=['POST', 'DELETE']
)
def session_action(ident):
    with db.connect() as c:
        row = c.execute(
            'SELECT * FROM sessions WHERE id=?',
            (ident,)
        ).fetchone()

    if not row:
        return jsonify(error='Session not found'), 404

    if request.method == 'DELETE':
        if row['status'] == 'approved':
            return jsonify(
                error='Approved sessions cannot be deleted here'
            ), 400

        with db.connect() as c:
            c.execute(
                'DELETE FROM sessions WHERE id=?',
                (ident,)
            )

        return jsonify(ok=True)

    start = datetime.fromisoformat(row['starts'])
    end = datetime.fromisoformat(row['ends'])

    if db.setting('google_token'):
        try:
            integrations.google_sync()
        except Exception as e:
            return jsonify(
                error='Cannot verify Google availability: ' + str(e)
            ), 503

    if db.is_busy(
        start,
        end,
        exclude_session_id=ident
    ):
        return jsonify(
            error='Time conflict found. Please request another suggestion.'
        ), 409

    google_status = 'Not connected'

    if db.setting('google_token'):
        try:
            integrations.google_add_session(dict(row))
            google_status = 'Added to Google Calendar'

        except Exception as e:
            return jsonify(
                error='Google Calendar failed: ' + str(e)
            ), 502

    with db.connect() as c:
        c.execute(
            "UPDATE sessions SET status='approved' WHERE id=?",
            (ident,)
        )

    return jsonify(
        ok=True,
        google=google_status
    )

@app.post('/api/estimate/<ident>')
def estimate(ident):
    with db.connect() as c:
        row = c.execute(
            'SELECT * FROM assignments WHERE id=?',
            (ident,)
        ).fetchone()

    if not row:
        return jsonify(error='Assignment not found'), 404

    try:
        import json
        from google import genai
        from google.genai import types

        if not os.getenv('GOOGLE_API_KEY'):
            return jsonify(error='GOOGLE_API_KEY missing'), 503

        client = genai.Client(
            api_key=os.environ['GOOGLE_API_KEY']
        )

        result = client.models.generate_content(
            model=os.getenv('MODEL', 'gemini-2.5-flash'),
            contents=(
                'Estimate student workload for assignment: ' +
                row['title'] +
                ', course: ' +
                str(row['course']) +
                '. Return a cautious estimate.'
            ),
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
                response_schema={
                    'type': 'OBJECT',
                    'properties': {
                        'difficulty': {
                            'type': 'STRING',
                            'enum': ['Easy', 'Medium', 'Hard']
                        },
                        'hours': {
                            'type': 'NUMBER'
                        }
                    },
                    'required': ['difficulty', 'hours']
                }
            )
        )

        estimate_data = json.loads(result.text)

        difficulty = estimate_data['difficulty']
        hours = min(
            30,
            max(0.5, float(estimate_data['hours']))
        )

        with db.connect() as c:
            c.execute('''
                UPDATE assignments
                SET difficulty=?, estimated_hours=?
                WHERE id=?
            ''', (
                difficulty,
                hours,
                ident
            ))

        return jsonify(
            difficulty=difficulty,
            estimated_hours=hours,
            note='AI estimate only. You can edit it.'
        )

    except Exception as e:
        return jsonify(
            error='AI estimation failed: ' + str(e)
        ), 503

@app.post('/api/chat')
def chat():
    message = str(
        (request.get_json(silent=True) or {}).get(
            'message', ''
        )
    ).strip()

    if not message:
        return jsonify(error='Message is required'), 400

    if len(message) > 3000:
        return jsonify(error='Message too long'), 400

    try:
        from agent import chat as ask_agent

        sid = session.setdefault(
            'chat_id',
            uuid.uuid4().hex
        )

        return jsonify(
            reply=ask_agent(message, sid)
        )

    except Exception as e:
        app.logger.exception('AI error')

        return jsonify(
            error='AI request failed. Check your API key and model. ' +
                  str(e)
        ), 503

@app.post('/api/canvas/sync')
def canvas_sync():
    try:
        return jsonify(integrations.canvas_sync())

    except Exception as e:
        return jsonify(error=str(e)), 400

@app.get('/google/connect')
def google_connect():
    try:
        from google_auth_oauthlib.flow import Flow

        redirect_uri = url_for(
            'google_callback',
            _external=True
        )

        flow = Flow.from_client_config(
            integrations.oauth_config(redirect_uri),
            scopes=integrations.SCOPE,
            autogenerate_code_verifier=True
        )

        flow.redirect_uri = redirect_uri

        url, state = flow.authorization_url(
            access_type='offline',
            prompt='consent'
        )

        # Save the OAuth state and PKCE verifier
        session['oauth_state'] = state
        session['oauth_code_verifier'] = flow.code_verifier

        return redirect(url)

    except Exception as e:
        return 'Google connection failed: ' + str(e), 400

@app.get('/google/callback')
def google_callback():
    try:
        from google_auth_oauthlib.flow import Flow

        if (
            not session.get('logged_in')
            and os.getenv('APP_PASSWORD')
        ):
            return 'Please sign in to StudyFlow first.', 401

        redirect_uri = url_for(
            'google_callback',
            _external=True
        )

        # Retrieve the saved state and PKCE verifier
        state = session.pop('oauth_state', None)
        verifier = session.pop('oauth_code_verifier', None)

        if not state or not verifier:
            return (
                'Google sign-in session expired. '
                'Please click Connect Google Calendar again.'
            ), 400

        flow = Flow.from_client_config(
            integrations.oauth_config(redirect_uri),
            scopes=integrations.SCOPE,
            state=state,
            code_verifier=verifier,
            autogenerate_code_verifier=False
        )

        flow.redirect_uri = redirect_uri

        # Exchange Google's authorization code for tokens
        flow.fetch_token(
            authorization_response=request.url
        )

        # Save Google authorization credentials
        db.setting(
            'google_token',
            flow.credentials.to_json()
        )

        # Try to import the calendar events
        try:
            integrations.google_sync()
        except Exception:
            app.logger.exception(
                'Google Calendar import failed'
            )

        return redirect('/')

    except Exception as e:
        return 'Google sign-in failed: ' + str(e), 400

@app.post('/api/google/sync')
def google_sync():
    try:
        return jsonify(integrations.google_sync())

    except Exception as e:
        return jsonify(error=str(e)), 400

if __name__ == '__main__':
    app.run(debug=True)
