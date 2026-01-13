#!/usr/bin/env python3
"""
Calendar CLI - Simple wrapper for Google Calendar API operations.

Used by the fgp-calendar daemon for Calendar API calls.
Handles OAuth2 authentication using tokens from ~/.fgp/auth/google/

Usage:
    calendar-cli.py today
    calendar-cli.py upcoming [--days N] [--limit N]
    calendar-cli.py search QUERY [--days N]
    calendar-cli.py create SUMMARY START END [--description DESC]
    calendar-cli.py free-slots --duration MINUTES [--days N]
"""

import argparse
import json
import pickle
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Google API imports
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from dateutil import parser as date_parser
except ImportError:
    print(json.dumps({
        "error": "Google API libraries not installed. Run: pip install google-api-python-client google-auth-oauthlib python-dateutil"
    }))
    sys.exit(1)

# Calendar API scopes
SCOPES = ['https://www.googleapis.com/auth/calendar']

# Auth paths - try FGP first, then legacy
FGP_AUTH_DIR = Path.home() / ".fgp" / "auth" / "google"
LEGACY_AUTH_DIR = Path.home() / ".wolfie-gateway" / "auth" / "google"


def get_credentials():
    """Get OAuth2 credentials, refreshing if needed."""
    creds = None

    # Try FGP auth first
    token_file = FGP_AUTH_DIR / "calendar_token.pickle"
    credentials_file = FGP_AUTH_DIR / "credentials.json"

    # Fallback to legacy
    if not token_file.exists():
        legacy_token = LEGACY_AUTH_DIR / "calendar_token.pickle"
        if legacy_token.exists():
            token_file = legacy_token
            credentials_file = LEGACY_AUTH_DIR / "credentials.json"

    # Also check gmail token as fallback (same Google account)
    if not token_file.exists():
        gmail_token = FGP_AUTH_DIR / "gmail_token.pickle"
        if gmail_token.exists():
            token_file = gmail_token

    # Try to load existing token
    if token_file.exists():
        with open(token_file, 'rb') as f:
            creds = pickle.load(f)

    # Refresh or get new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        elif credentials_file.exists():
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
            creds = flow.run_local_server(port=0)
        else:
            raise FileNotFoundError(
                f"No credentials found. Place credentials.json in {FGP_AUTH_DIR} or {LEGACY_AUTH_DIR}"
            )

        # Save refreshed token
        save_path = FGP_AUTH_DIR / "calendar_token.pickle"
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, 'wb') as f:
            pickle.dump(creds, f)

    return creds


def get_service():
    """Build Calendar API service."""
    creds = get_credentials()
    return build('calendar', 'v3', credentials=creds)


def format_event(event):
    """Format an event for output."""
    start = event.get('start', {})
    end = event.get('end', {})

    # Parse start/end times
    start_str = start.get('dateTime', start.get('date', ''))
    end_str = end.get('dateTime', end.get('date', ''))

    return {
        'id': event.get('id'),
        'summary': event.get('summary', '(No title)'),
        'start': start_str,
        'end': end_str,
        'location': event.get('location'),
        'description': event.get('description', '')[:200] if event.get('description') else None,
        'html_link': event.get('htmlLink'),
        'all_day': 'date' in start
    }


def cmd_today(args):
    """Get today's events."""
    service = get_service()

    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    results = service.events().list(
        calendarId='primary',
        timeMin=start_of_day.isoformat(),
        timeMax=end_of_day.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = [format_event(e) for e in results.get('items', [])]

    print(json.dumps({
        'date': start_of_day.strftime('%Y-%m-%d'),
        'events': events,
        'count': len(events)
    }))


def cmd_upcoming(args):
    """Get upcoming events."""
    service = get_service()

    now = datetime.now(timezone.utc)
    time_max = now + timedelta(days=args.days)

    results = service.events().list(
        calendarId='primary',
        timeMin=now.isoformat(),
        timeMax=time_max.isoformat(),
        maxResults=args.limit,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = [format_event(e) for e in results.get('items', [])]

    print(json.dumps({
        'days': args.days,
        'events': events,
        'count': len(events)
    }))


def cmd_search(args):
    """Search events by query."""
    service = get_service()

    now = datetime.now(timezone.utc)
    time_max = now + timedelta(days=args.days)

    results = service.events().list(
        calendarId='primary',
        timeMin=now.isoformat(),
        timeMax=time_max.isoformat(),
        q=args.query,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = [format_event(e) for e in results.get('items', [])]

    print(json.dumps({
        'query': args.query,
        'events': events,
        'count': len(events)
    }))


def cmd_create(args):
    """Create a new event."""
    service = get_service()

    # Parse start/end times
    try:
        start_dt = date_parser.parse(args.start)
        end_dt = date_parser.parse(args.end)
    except Exception as e:
        print(json.dumps({'error': f'Invalid date format: {e}'}))
        sys.exit(1)

    event = {
        'summary': args.summary,
        'start': {
            'dateTime': start_dt.isoformat(),
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': end_dt.isoformat(),
            'timeZone': 'UTC',
        },
    }

    if args.description:
        event['description'] = args.description

    created = service.events().insert(
        calendarId='primary',
        body=event
    ).execute()

    print(json.dumps({
        'created': True,
        'event_id': created.get('id'),
        'html_link': created.get('htmlLink'),
        'summary': created.get('summary')
    }))


def cmd_free_slots(args):
    """Find available time slots."""
    service = get_service()

    now = datetime.now(timezone.utc)
    time_max = now + timedelta(days=args.days)
    duration = timedelta(minutes=args.duration)

    # Get all events in the time range
    results = service.events().list(
        calendarId='primary',
        timeMin=now.isoformat(),
        timeMax=time_max.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    # Extract busy periods
    busy_periods = []
    for event in results.get('items', []):
        start = event.get('start', {})
        end = event.get('end', {})

        start_str = start.get('dateTime', start.get('date'))
        end_str = end.get('dateTime', end.get('date'))

        if start_str and end_str:
            busy_periods.append({
                'start': date_parser.parse(start_str),
                'end': date_parser.parse(end_str)
            })

    # Find free slots (working hours: 9am-5pm, weekdays only)
    free_slots = []
    current = now
    working_start = 9
    working_end = 17

    while current < time_max and len(free_slots) < 20:
        # Skip to working hours
        if current.hour < working_start:
            current = current.replace(hour=working_start, minute=0, second=0, microsecond=0)
        elif current.hour >= working_end:
            current = (current + timedelta(days=1)).replace(hour=working_start, minute=0, second=0, microsecond=0)
            continue

        # Skip weekends
        if current.weekday() >= 5:
            days_to_monday = 7 - current.weekday()
            current = (current + timedelta(days=days_to_monday)).replace(hour=working_start, minute=0, second=0, microsecond=0)
            continue

        slot_end = current + duration

        # Check if slot extends past working hours
        if slot_end.hour > working_end or (slot_end.hour == working_end and slot_end.minute > 0):
            current = (current + timedelta(days=1)).replace(hour=working_start, minute=0, second=0, microsecond=0)
            continue

        # Check for conflicts
        is_free = True
        for busy in busy_periods:
            if current < busy['end'] and slot_end > busy['start']:
                current = busy['end']
                is_free = False
                break

        if is_free:
            free_slots.append({
                'start': current.isoformat(),
                'end': slot_end.isoformat()
            })
            current = current + timedelta(minutes=15)

    print(json.dumps({
        'duration_minutes': args.duration,
        'days': args.days,
        'free_slots': free_slots,
        'count': len(free_slots)
    }))


def main():
    parser = argparse.ArgumentParser(description='Calendar CLI for FGP daemon')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # today
    p_today = subparsers.add_parser('today', help="Get today's events")
    p_today.set_defaults(func=cmd_today)

    # upcoming
    p_upcoming = subparsers.add_parser('upcoming', help='Get upcoming events')
    p_upcoming.add_argument('--days', type=int, default=7)
    p_upcoming.add_argument('--limit', type=int, default=20)
    p_upcoming.set_defaults(func=cmd_upcoming)

    # search
    p_search = subparsers.add_parser('search', help='Search events')
    p_search.add_argument('query', help='Search query')
    p_search.add_argument('--days', type=int, default=30)
    p_search.set_defaults(func=cmd_search)

    # create
    p_create = subparsers.add_parser('create', help='Create event')
    p_create.add_argument('summary', help='Event title')
    p_create.add_argument('start', help='Start time (ISO format or natural language)')
    p_create.add_argument('end', help='End time (ISO format or natural language)')
    p_create.add_argument('--description', help='Event description')
    p_create.set_defaults(func=cmd_create)

    # free-slots
    p_free = subparsers.add_parser('free-slots', help='Find free time')
    p_free.add_argument('--duration', type=int, required=True, help='Duration in minutes')
    p_free.add_argument('--days', type=int, default=7)
    p_free.set_defaults(func=cmd_free_slots)

    args = parser.parse_args()

    try:
        args.func(args)
    except HttpError as e:
        print(json.dumps({'error': f'Calendar API error: {e.reason}'}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({'error': str(e)}))
        sys.exit(1)


if __name__ == '__main__':
    main()
