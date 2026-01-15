"""
Calendar Module for FGP daemon (PyO3 interface).

This module is loaded by the Rust daemon via PyO3 and keeps the Calendar service warm.
Each method call reuses the warm connection instead of spawning new processes.

CHANGELOG:
01/14/2026 - Added get, delete, update, quick methods; location/attendees support (Claude)
01/13/2026 - Created PyO3-compatible module for warm connections (Claude)
"""

import pickle
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dateutil import parser as date_parser

# Calendar API scopes
SCOPES = ['https://www.googleapis.com/auth/calendar']

# Auth paths
FGP_AUTH_DIR = Path.home() / ".fgp" / "auth" / "google"
LEGACY_AUTH_DIR = Path.home() / ".wolfie-gateway" / "auth" / "google"


class CalendarModule:
    """Calendar service module following FGP PyO3 interface."""

    # Required attributes for FGP
    name = "calendar"
    version = "1.0.0"

    def __init__(self):
        """Initialize Calendar service - this runs ONCE at daemon startup."""
        self.service = None
        self._init_service()

    def _get_credentials(self) -> Credentials:
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
                    f"No credentials found. Place credentials.json in {FGP_AUTH_DIR}"
                )

            # Save refreshed token
            token_file.parent.mkdir(parents=True, exist_ok=True)
            with open(token_file, 'wb') as f:
                pickle.dump(creds, f)

        return creds

    def _init_service(self):
        """Build Calendar API service (runs once at startup)."""
        creds = self._get_credentials()
        self.service = build('calendar', 'v3', credentials=creds, cache_discovery=False)

    def dispatch(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route method calls to handlers.

        This is called by the Rust daemon for each request.
        The service is already warm, so we just execute the method.
        """
        handlers = {
            "calendar.today": self._cmd_today,
            "calendar.upcoming": self._cmd_upcoming,
            "calendar.search": self._cmd_search,
            "calendar.create": self._cmd_create,
            "calendar.free_slots": self._cmd_free_slots,
            "calendar.get": self._cmd_get,
            "calendar.delete": self._cmd_delete,
            "calendar.update": self._cmd_update,
            "calendar.quick": self._cmd_quick,
        }

        handler = handlers.get(method)
        if handler is None:
            raise ValueError(f"Unknown method: {method}")

        return handler(params)

    def method_list(self) -> List[Dict[str, Any]]:
        """Return list of available methods."""
        return [
            {
                "name": "calendar.today",
                "description": "Get today's events",
                "params": []
            },
            {
                "name": "calendar.upcoming",
                "description": "Get upcoming events",
                "params": [
                    {"name": "days", "type": "integer", "required": False, "default": 7},
                    {"name": "limit", "type": "integer", "required": False, "default": 20}
                ]
            },
            {
                "name": "calendar.search",
                "description": "Search events by query",
                "params": [
                    {"name": "query", "type": "string", "required": True},
                    {"name": "days", "type": "integer", "required": False, "default": 30}
                ]
            },
            {
                "name": "calendar.create",
                "description": "Create a new event",
                "params": [
                    {"name": "summary", "type": "string", "required": True},
                    {"name": "start", "type": "string", "required": True},
                    {"name": "end", "type": "string", "required": True},
                    {"name": "description", "type": "string", "required": False},
                    {"name": "location", "type": "string", "required": False},
                    {"name": "attendees", "type": "array", "required": False}
                ]
            },
            {
                "name": "calendar.free_slots",
                "description": "Find available time slots",
                "params": [
                    {"name": "duration_minutes", "type": "integer", "required": True},
                    {"name": "days", "type": "integer", "required": False, "default": 7}
                ]
            },
            {
                "name": "calendar.get",
                "description": "Get a specific event by ID",
                "params": [
                    {"name": "event_id", "type": "string", "required": True}
                ]
            },
            {
                "name": "calendar.delete",
                "description": "Delete an event",
                "params": [
                    {"name": "event_id", "type": "string", "required": True}
                ]
            },
            {
                "name": "calendar.update",
                "description": "Update an existing event",
                "params": [
                    {"name": "event_id", "type": "string", "required": True},
                    {"name": "summary", "type": "string", "required": False},
                    {"name": "start", "type": "string", "required": False},
                    {"name": "end", "type": "string", "required": False},
                    {"name": "description", "type": "string", "required": False},
                    {"name": "location", "type": "string", "required": False}
                ]
            },
            {
                "name": "calendar.quick",
                "description": "Quick add event from natural language",
                "params": [
                    {"name": "text", "type": "string", "required": True}
                ]
            }
        ]

    def on_start(self):
        """Called when daemon starts."""
        # Service already initialized in __init__
        pass

    def on_stop(self):
        """Called when daemon stops."""
        pass

    def health_check(self) -> Dict[str, Any]:
        """Return health status."""
        return {
            "calendar_service": {
                "ok": self.service is not None,
                "message": "Calendar service initialized" if self.service else "Service not initialized"
            }
        }

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _format_event(self, event: Dict) -> Dict[str, Any]:
        """Format an event for output."""
        start = event.get('start', {})
        end = event.get('end', {})

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

    # =========================================================================
    # Method Handlers
    # =========================================================================

    def _cmd_today(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get today's events."""
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        results = self.service.events().list(
            calendarId='primary',
            timeMin=start_of_day.isoformat(),
            timeMax=end_of_day.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = [self._format_event(e) for e in results.get('items', [])]

        return {
            'date': start_of_day.strftime('%Y-%m-%d'),
            'events': events,
            'count': len(events)
        }

    def _cmd_upcoming(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get upcoming events."""
        days = params.get("days", 7)
        limit = params.get("limit", 20)

        now = datetime.now(timezone.utc)
        time_max = now + timedelta(days=days)

        results = self.service.events().list(
            calendarId='primary',
            timeMin=now.isoformat(),
            timeMax=time_max.isoformat(),
            maxResults=limit,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = [self._format_event(e) for e in results.get('items', [])]

        return {
            'days': days,
            'events': events,
            'count': len(events)
        }

    def _cmd_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Search events by query."""
        query = params.get("query")
        if not query:
            raise ValueError("query parameter is required")

        days = params.get("days", 30)

        now = datetime.now(timezone.utc)
        time_max = now + timedelta(days=days)

        results = self.service.events().list(
            calendarId='primary',
            timeMin=now.isoformat(),
            timeMax=time_max.isoformat(),
            q=query,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = [self._format_event(e) for e in results.get('items', [])]

        return {
            'query': query,
            'events': events,
            'count': len(events)
        }

    def _cmd_create(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new event."""
        summary = params.get("summary")
        start = params.get("start")
        end = params.get("end")
        description = params.get("description")
        location = params.get("location")
        attendees = params.get("attendees", [])

        if not all([summary, start, end]):
            raise ValueError("summary, start, and end parameters are required")

        # Parse start/end times
        start_dt = date_parser.parse(start)
        end_dt = date_parser.parse(end)

        event = {
            'summary': summary,
            'start': {
                'dateTime': start_dt.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_dt.isoformat(),
                'timeZone': 'UTC',
            },
        }

        if description:
            event['description'] = description

        if location:
            event['location'] = location

        if attendees:
            event['attendees'] = [{'email': email} for email in attendees]

        created = self.service.events().insert(
            calendarId='primary',
            body=event,
            sendUpdates='all' if attendees else 'none'
        ).execute()

        return {
            'created': True,
            'event_id': created.get('id'),
            'html_link': created.get('htmlLink'),
            'summary': created.get('summary')
        }

    def _cmd_free_slots(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Find available time slots."""
        duration_minutes = params.get("duration_minutes")
        if not duration_minutes:
            raise ValueError("duration_minutes parameter is required")

        days = params.get("days", 7)

        now = datetime.now(timezone.utc)
        time_max = now + timedelta(days=days)
        duration = timedelta(minutes=duration_minutes)

        # Get all events in the time range
        results = self.service.events().list(
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

        return {
            'duration_minutes': duration_minutes,
            'days': days,
            'free_slots': free_slots,
            'count': len(free_slots)
        }

    def _cmd_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get a specific event by ID."""
        event_id = params.get("event_id")
        if not event_id:
            raise ValueError("event_id parameter is required")

        event = self.service.events().get(
            calendarId='primary',
            eventId=event_id
        ).execute()

        return self._format_event(event)

    def _cmd_delete(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete an event."""
        event_id = params.get("event_id")
        if not event_id:
            raise ValueError("event_id parameter is required")

        self.service.events().delete(
            calendarId='primary',
            eventId=event_id
        ).execute()

        return {
            'deleted': True,
            'event_id': event_id
        }

    def _cmd_update(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing event."""
        event_id = params.get("event_id")
        if not event_id:
            raise ValueError("event_id parameter is required")

        # Get current event
        event = self.service.events().get(
            calendarId='primary',
            eventId=event_id
        ).execute()

        # Update fields if provided
        if params.get("summary"):
            event['summary'] = params['summary']

        if params.get("description"):
            event['description'] = params['description']

        if params.get("location"):
            event['location'] = params['location']

        if params.get("start"):
            start_dt = date_parser.parse(params['start'])
            event['start'] = {
                'dateTime': start_dt.isoformat(),
                'timeZone': 'UTC',
            }

        if params.get("end"):
            end_dt = date_parser.parse(params['end'])
            event['end'] = {
                'dateTime': end_dt.isoformat(),
                'timeZone': 'UTC',
            }

        updated = self.service.events().update(
            calendarId='primary',
            eventId=event_id,
            body=event
        ).execute()

        return {
            'updated': True,
            'event_id': updated.get('id'),
            'html_link': updated.get('htmlLink'),
            'summary': updated.get('summary')
        }

    def _cmd_quick(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Quick add event from natural language.

        Uses Google Calendar's quickAdd API which parses natural language like:
        - "Meeting with John tomorrow at 3pm"
        - "Dentist appointment Friday 10am-11am"
        - "Lunch at Cafe 12pm"
        """
        text = params.get("text")
        if not text:
            raise ValueError("text parameter is required")

        created = self.service.events().quickAdd(
            calendarId='primary',
            text=text
        ).execute()

        return {
            'created': True,
            'event_id': created.get('id'),
            'html_link': created.get('htmlLink'),
            'summary': created.get('summary'),
            'start': created.get('start', {}).get('dateTime', created.get('start', {}).get('date')),
            'end': created.get('end', {}).get('dateTime', created.get('end', {}).get('date'))
        }
