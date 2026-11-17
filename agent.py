
import os
import asyncio
from datetime import date

from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.runners import InMemoryRunner
from google.genai import types

import db

def get_assignments() -> dict:
    """Read assignments, deadlines, difficulty, and estimated hours."""
    return {
        'assignments': db.all_rows('assignments')
    }

def get_commitments() -> dict:
    """Read work, classes, recurring events, and study sessions."""
    return {
        'commitments': db.all_rows('commitments'),
        'sessions': db.all_rows('sessions')
    }

def rank_assignments() -> dict:
    """Rank unfinished assignments by urgency and workload."""
    items = [
        dict(x, priority=db.priority(x))
        for x in db.all_rows('assignments')
        if not x['completed']
    ]

    return {
        'ranked': sorted(
            items,
            key=lambda x: -x['priority']
        )
    }

def create_assignment(
    title: str,
    due_date: str,
    course: str = ''
) -> dict:
    """Add a task explicitly requested by the student. Date: YYYY-MM-DD."""
    try:
        date.fromisoformat(due_date)

        a = {
            'title': title.strip(),
            'due_date': due_date,
            'course': course
        }

        if not a['title']:
            raise ValueError('Missing title')

        db.add_assignment(a)

        return {
            'status': 'created',
            'assignment': a
        }

    except ValueError as e:
        return {'error': str(e)}

def propose_study_sessions(assignment_id: str) -> dict:
    """Propose conflict-free study sessions without approving them."""
    try:
        return db.suggest(assignment_id)

    except ValueError as e:
        return {'error': str(e)}

root_agent = LlmAgent(
    name='studyflow_assistant',

    model=os.getenv(
        'MODEL',
        'gemini-2.5-flash'
    ),

    instruction=(
        'You are StudyFlow, an AI academic scheduling assistant. '
        'Today is ' + str(date.today()) + '. '
        'Use your tools to check real assignments and commitments '
        'before making recommendations. '
        'Rank assignments by deadlines, difficulty, and workload. '
        'Estimate difficulty and required hours when appropriate. '
        'Explain that estimates are approximate. '
        'Break large assignments into manageable steps. '
        'Help balance workloads and suggest rescheduling. '
        'Fixed and flexible events are both occupied times. '
        'Never double-book a student. '
        'Only add assignments when explicitly requested. '
        'Use propose_study_sessions for scheduling suggestions. '
        'Never automatically approve study sessions. '
        'Tell the student to approve suggestions in the website. '
        'Never claim Google Calendar has been updated before approval. '
        'Be clear if Google Calendar or Canvas is not connected.'
    ),

    tools=[
        get_assignments,
        get_commitments,
        rank_assignments,
        create_assignment,
        propose_study_sessions
    ]
)

runner = InMemoryRunner(
    app=App(
        name='studyflow',
        root_agent=root_agent
    )
)

async def _chat(message, session_id):
    existing = await runner.session_service.get_session(
        app_name='studyflow',
        user_id='student',
        session_id=session_id
    )

    if existing is None:
        await runner.session_service.create_session(
            app_name='studyflow',
            user_id='student',
            session_id=session_id
        )

    response = ''

    async for event in runner.run_async(
        user_id='student',
        session_id=session_id,
        new_message=types.Content(
            role='user',
            parts=[
                types.Part.from_text(text=message)
            ]
        )
    ):
        if event.is_final_response() and event.content:
            response = '\n'.join(
                p.text
                for p in event.content.parts
                if p.text
            )

    return response or 'Please try again.'

def chat(message, session_id):
    if not os.getenv('GOOGLE_API_KEY'):
        raise RuntimeError(
            'Add GOOGLE_API_KEY to your .env file.'
        )

    return asyncio.run(
        _chat(message, session_id)
    )
