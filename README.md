# fgp-calendar

Fast Google Calendar daemon for [FGP](https://github.com/fast-gateway-protocol) - the universal package manager for AI agents.

## Features

- **10x faster than MCP** - Persistent daemon with warm connections
- **Multi-agent support** - Works with Claude Code, Cursor, Windsurf, Continue
- **One-command install** - `fgp install calendar`

## Installation

```bash
fgp install calendar
```

This will:
1. Install the daemon to `~/.fgp/services/calendar/`
2. Detect your installed AI agents
3. Install appropriate skill files for each agent
4. Configure OAuth (you'll need to complete the flow once)

## Setup

1. Place Google OAuth credentials in `~/.fgp/auth/google/credentials.json`
2. Start the daemon: `fgp start calendar`
3. Complete OAuth flow when prompted (first time only)

## Usage

### Get Today's Events
```bash
fgp call calendar.today
```

### Get Upcoming Events
```bash
fgp call calendar.upcoming -p '{"days": 7, "limit": 20}'
```

### Search Events
```bash
fgp call calendar.search -p '{"query": "meeting"}'
```

### Create Event
```bash
fgp call calendar.create -p '{"summary": "Team sync", "start": "2026-01-15T14:00:00Z", "end": "2026-01-15T15:00:00Z"}'
```

### Find Free Time
```bash
fgp call calendar.free_slots -p '{"duration_minutes": 30, "days": 7}'
```

## Methods

| Method | Description |
|--------|-------------|
| `calendar.today` | Get today's events |
| `calendar.upcoming` | Get events for next N days |
| `calendar.search` | Search events by query |
| `calendar.create` | Create a new event |
| `calendar.free_slots` | Find available time slots |

## Performance

| Metric | Value |
|--------|-------|
| Cold start | ~50ms |
| Warm call | ~10-30ms |
| MCP baseline | ~300-500ms |

## Requirements

- Python 3.8+
- Google API libraries: `pip install google-api-python-client google-auth-oauthlib python-dateutil`
- Google OAuth credentials (see [Google Calendar API docs](https://developers.google.com/calendar/api/quickstart/python))

## License

MIT
