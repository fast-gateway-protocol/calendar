#!/usr/bin/env python3
"""
Calendar Daemon - Basic Operations Example

Demonstrates common Google Calendar operations using the FGP Calendar daemon.
Requires: Calendar daemon running (`fgp start calendar`)
"""

import json
import socket
import uuid
from datetime import datetime, timedelta
from pathlib import Path

SOCKET_PATH = Path.home() / ".fgp/services/calendar/daemon.sock"


def call_daemon(method: str, params: dict = None) -> dict:
    """Send a request to the Calendar daemon and return the response."""
    request = {
        "id": str(uuid.uuid4()),
        "v": 1,
        "method": method,
        "params": params or {}
    }

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(str(SOCKET_PATH))
        sock.sendall((json.dumps(request) + "\n").encode())

        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
            if b"\n" in response:
                break

        return json.loads(response.decode().strip())


def get_today_events():
    """Get all events for today."""
    print("\n📅 Today's Events")
    print("-" * 30)

    result = call_daemon("calendar.today", {})

    if result.get("ok"):
        events = result["result"].get("events", [])
        if not events:
            print("  No events scheduled for today")
        for event in events:
            start = event.get("start", {}).get("dateTime", "All day")
            print(f"  • {event.get('summary', '(no title)')}")
            print(f"    Time: {start}")
            if event.get("location"):
                print(f"    Location: {event['location']}")
            print()
    else:
        print(f"  ❌ Error: {result.get('error')}")


def get_upcoming_events(days: int = 7):
    """Get upcoming events for the next N days."""
    print(f"\n📆 Upcoming Events (next {days} days)")
    print("-" * 30)

    result = call_daemon("calendar.upcoming", {"days": days})

    if result.get("ok"):
        events = result["result"].get("events", [])
        if not events:
            print(f"  No events in the next {days} days")
        for event in events:
            start = event.get("start", {}).get("dateTime", event.get("start", {}).get("date", "Unknown"))
            print(f"  • {event.get('summary', '(no title)')}")
            print(f"    When: {start}")
            print()
    else:
        print(f"  ❌ Error: {result.get('error')}")


def search_events(query: str):
    """Search for events by keyword."""
    print(f"\n🔍 Searching for: {query}")
    print("-" * 30)

    result = call_daemon("calendar.search", {"query": query})

    if result.get("ok"):
        events = result["result"].get("events", [])
        print(f"  Found {len(events)} matching events")
        for event in events:
            print(f"  • {event.get('summary', '(no title)')}")
    else:
        print(f"  ❌ Error: {result.get('error')}")


def find_free_slots(duration_minutes: int = 60, days_ahead: int = 3):
    """Find available time slots."""
    print(f"\n⏰ Finding {duration_minutes}-minute free slots (next {days_ahead} days)")
    print("-" * 30)

    result = call_daemon("calendar.free_slots", {
        "duration_minutes": duration_minutes,
        "days_ahead": days_ahead
    })

    if result.get("ok"):
        slots = result["result"].get("slots", [])
        if not slots:
            print("  No free slots found")
        for slot in slots[:5]:  # Show first 5
            print(f"  • {slot.get('start')} - {slot.get('end')}")
    else:
        print(f"  ❌ Error: {result.get('error')}")


def create_event(summary: str, start_time: str, end_time: str, description: str = None):
    """Create a new calendar event.

    Args:
        summary: Event title
        start_time: ISO format datetime (e.g., "2025-01-15T10:00:00")
        end_time: ISO format datetime
        description: Optional event description
    """
    print(f"\n➕ Creating event: {summary}")

    params = {
        "summary": summary,
        "start": start_time,
        "end": end_time
    }
    if description:
        params["description"] = description

    result = call_daemon("calendar.create", params)

    if result.get("ok"):
        event_id = result["result"].get("id")
        print(f"  ✅ Event created! ID: {event_id}")
    else:
        print(f"  ❌ Error: {result.get('error')}")


if __name__ == "__main__":
    print("Calendar Daemon Examples")
    print("=" * 40)

    # Check daemon health first
    health = call_daemon("health")
    if not health.get("ok"):
        print("❌ Calendar daemon not running. Start with: fgp start calendar")
        exit(1)

    print("✅ Calendar daemon is healthy")

    # Run examples
    get_today_events()
    get_upcoming_events(days=7)
    find_free_slots(duration_minutes=30)
    search_events("meeting")

    # Uncomment to create a test event:
    # tomorrow = (datetime.now() + timedelta(days=1)).replace(hour=14, minute=0, second=0)
    # create_event(
    #     summary="Test Event from FGP",
    #     start_time=tomorrow.isoformat(),
    #     end_time=(tomorrow + timedelta(hours=1)).isoformat(),
    #     description="Created via FGP Calendar daemon"
    # )
