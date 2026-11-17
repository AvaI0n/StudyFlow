
# StudyFlow — AI Academic Planner

StudyFlow is a web application that helps students organize assignments, manage commitments, and plan study time around their existing schedules. It combines an AI assistant with a calendar dashboard, SQLite storage, Google Calendar integration, and Canvas assignment imports.

## Features

- **Assignment Management:** Add, view, complete, edit workload estimates, and delete assignments.
- **Interactive Calendar:** View deadlines, commitments, and study sessions in month, week, or day views.
- **AI Assistant:** Ask about priorities, review deadlines, create assignments on request, and request study-time suggestions.
- **AI Workload Estimates:** Generate suggested difficulty levels and estimated hours, which can be edited manually.
- **Conflict-Aware Scheduling:** Suggest study sessions around existing commitments. Sessions require approval before being finalized.
- **Google Calendar Integration:** Import events to recognize busy time and add approved study sessions to Google Calendar.
- **Canvas Integration:** Import deadlines through a subscribed Canvas Google Calendar or optionally through the Canvas API.
- **Searchable Lists:** Browse assignments and commitments with search, pagination, and collapsible sections.

## Technology Stack

- **Backend:** Python, Flask
- **Artificial Intelligence:** Google Agent Development Kit (ADK), Gemini API
- **Database:** SQLite
- **Frontend:** HTML, CSS, JavaScript, FullCalendar
- **Integrations:** Google Calendar API, Google OAuth 2.0, Canvas API

## Project Structure

```text
StudyFlow/
├── app.py
├── agent.py
├── db.py
├── integrations.py
├── requirements.txt
├── Procfile
├── templates/
│   └── index.html
├── static/
│   ├── style.css
│   └── calendar.js
└── README.md
```

### File Descriptions

- `app.py` — Flask application and API endpoints.
- `agent.py` — AI assistant, its instructions, and available tools.
- `db.py` — SQLite database and scheduling logic.
- `integrations.py` — Google Calendar and Canvas integrations.
- `templates/index.html` — Main dashboard interface.
- `static/style.css` — Dashboard styling.
- `static/calendar.js` — Calendar display and browser interactions.
- `requirements.txt` — Required Python packages.
- `Procfile` — Deployment start command.

## Installation

### Requirements

- Python 3.11
- Git
- Google Gemini API key for AI features
- Google account for optional calendar integration

### Step 1: Clone the Repository

```cmd
git clone https://github.com/AvaI0n/StudyFlow.git
cd StudyFlow
```

### Step 2: Create a Virtual Environment

```cmd
python -m venv venv
venv\Scripts\activate
```

### Step 3: Install Dependencies

```cmd
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

Create a file named `.env` inside the project folder.

Add your own credentials:

```dotenv
GOOGLE_API_KEY=your_gemini_api_key
MODEL=gemini-3.1-flash-lite

SECRET_KEY=replace_with_a_long_random_secret
APP_PASSWORD=choose_a_demo_password
APP_TIMEZONE=America/New_York

# Optional Google Calendar integration
GOOGLE_CLIENT_ID=your_google_oauth_client_id
GOOGLE_CLIENT_SECRET=your_google_oauth_client_secret
CANVAS_CALENDAR_NAME=Canvas

# Optional direct Canvas API integration
CANVAS_URL=https://your-school.instructure.com
CANVAS_TOKEN=your_canvas_api_token

# Local OAuth testing only
OAUTHLIB_INSECURE_TRANSPORT=1
```

Replace the placeholder values with your own credentials.

**Important:** Never share or upload your `.env` file. Remove `OAUTHLIB_INSECURE_TRANSPORT=1` before deploying publicly.

### Step 5: Run StudyFlow

```cmd
python -c "from app import app; app.run(debug=True, use_reloader=False)"
```

Open the following address:

http://127.0.0.1:5000

If an application password is configured, sign in with that password.

StudyFlow automatically creates its SQLite database when first started.

## Connecting Google Calendar

1. Create a project in Google Cloud Console.
2. Enable the Google Calendar API.
3. Configure the OAuth consent screen in Google Auth Platform.
4. Add your Google account as a test user if the application is in testing.
5. Create a Web application OAuth client.
6. Add this authorized redirect URI:

   `http://127.0.0.1:5000/google/callback`

7. Add your client ID and client secret to `.env`.
8. Restart StudyFlow.
9. Click **Connect Google Calendar** on the dashboard.
10. Authorize access and click **Refresh Google Events**.

Google Calendar events are imported into StudyFlow to help avoid scheduling study sessions during occupied times.

Approved study sessions can also be added to the connected primary Google Calendar.

## Connecting Canvas

### Method 1: Google Calendar Subscription

1. Open Canvas and locate its calendar feed.
2. Subscribe to the Canvas calendar in Google Calendar.
3. Connect Google Calendar to StudyFlow.
4. Set `CANVAS_CALENDAR_NAME` to the name of the subscribed calendar.
5. Click **Refresh Google Events**.

StudyFlow imports dated events from the matching Canvas calendar as candidate assignments.

### Method 2: Canvas API

Alternatively, enter the following information in `.env`:

```dotenv
CANVAS_URL=https://your-school.instructure.com
CANVAS_TOKEN=your_canvas_api_token
```

Click **Import Canvas Assignments** to import eligible assignments directly.

## How to Use StudyFlow

### Managing Assignments

Students can manually create assignments with a name, course, due date, difficulty, and estimated workload.

Assignments can be marked complete, edited, or deleted.

### AI Estimates

Click **AI Estimate** on an assignment to receive a suggested difficulty level and workload estimate.

Students can adjust the estimates afterward.

### Study Scheduling

Click **AI Suggest Study Time** to generate possible study sessions.

StudyFlow checks recorded commitments and existing sessions to reduce scheduling conflicts.

Suggested sessions remain pending until the student approves or rejects them.

### AI Assistant

The built-in AI assistant can help students:

- Decide which assignment to prioritize.
- Review deadlines and workloads.
- Create assignments when requested.
- Suggest available study times.
- Break larger assignments into manageable steps.

### Calendar Dashboard

The calendar displays assignments, commitments, and study sessions.

Students can switch between month, week, and day views.

Assignments and commitments can be searched through the dashboard.

## Current Limitations

- Google Calendar and Canvas assignment imports are not full two-way synchronization.
- Deleting an imported assignment in StudyFlow does not delete the original event in Google Calendar or Canvas.
- Refreshing Google Calendar may reimport previously deleted assignments.
- Synchronization is not continuously performed in the background.
- Canvas calendar feeds may contain events that are not assignments.
- Some multi-day calendar events may not be handled by the scheduling system.
- StudyFlow is designed as an academic demonstration project rather than a production multi-user service.

## Security

Sensitive information is stored in environment variables rather than hardcoded into the application.

The `.gitignore` file prevents common private files from being uploaded, including:

- `.env`
- `venv/`
- `studyflow.db`
- Python cache files
- Common credential and token JSON files

The application should use HTTPS and secure deployment settings if hosted publicly.

## GitHub Repository

https://github.com/AvaI0n/StudyFlow

## Author

Ryan Ali

Undergraduate Academic Project