---
name: calendar-fgp
description: Fast Google Calendar operations via FGP daemon (10x faster than MCP)
tools: ["Bash"]
triggers:
  - "calendar"
  - "what's on my calendar"
  - "today's events"
  - "upcoming events"
  - "schedule"
  - "find free time"
  - "book a meeting"
---

# Calendar FGP Skill

Fast Google Calendar operations using the FGP daemon protocol. 10-30ms response times via persistent UNIX sockets.

## Prerequisites

1. **Google OAuth configured**: Credentials in `~/.fgp/auth/google/credentials.json`
2. **FGP daemon running**: `fgp start calendar` or daemon auto-starts on first call

## Available Methods

| Method | Description |
|--------|-------------|
| `calendar.today` | Get today's events |
| `calendar.upcoming` | Get events for next N days |
| `calendar.search` | Search events by query |
| `calendar.create` | Create a new event |
| `calendar.free_slots` | Find available time slots |

---

### calendar.today - Today's Events

```bash
fgp call calendar.today
```

**Response:**
```json
{
  "date": "2026-01-13",
  "events": [
    {
      "id": "abc123",
      "summary": "Team standup",
      "start": "2026-01-13T09:00:00Z",
      "end": "2026-01-13T09:30:00Z",
      "location": null,
      "all_day": false
    }
  ],
  "count": 5
}
```

---

### calendar.upcoming - Upcoming Events

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `days` | integer | No | 7 | Number of days to look ahead |
| `limit` | integer | No | 20 | Maximum events to return |

```bash
fgp call calendar.upcoming -p '{"days": 7, "limit": 20}'
```

---

### calendar.search - Search Events

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | - | Search query |
| `days` | integer | No | 30 | Days to search forward |

```bash
fgp call calendar.search -p '{"query": "meeting", "days": 14}'
```

---

### calendar.create - Create Event

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `summary` | string | Yes | Event title |
| `start` | string | Yes | Start time (ISO 8601) |
| `end` | string | Yes | End time (ISO 8601) |
| `description` | string | No | Event description |

```bash
fgp call calendar.create -p '{"summary": "Team sync", "start": "2026-01-15T14:00:00Z", "end": "2026-01-15T15:00:00Z"}'
```

**Response:**
```json
{
  "created": true,
  "event_id": "abc123",
  "html_link": "https://calendar.google.com/calendar/event?eid=...",
  "summary": "Team sync"
}
```

---

### calendar.free_slots - Find Free Time

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `duration_minutes` | integer | Yes | - | Required meeting duration |
| `days` | integer | No | 7 | Days to search |

```bash
fgp call calendar.free_slots -p '{"duration_minutes": 30, "days": 7}'
```

**Response:**
```json
{
  "duration_minutes": 30,
  "free_slots": [
    {"start": "2026-01-13T10:00:00Z", "end": "2026-01-13T10:30:00Z"},
    {"start": "2026-01-13T14:00:00Z", "end": "2026-01-13T14:30:00Z"}
  ],
  "count": 20
}
```

**Note:** Returns slots during working hours (9am-5pm) on weekdays only.

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `Calendar API error: invalid_grant` | OAuth token expired | Re-run OAuth flow |
| `Calendar API error: 403` | Insufficient permissions | Check OAuth scopes |
| `calendar-cli failed` | Python script error | Check Python 3 installed |

## Troubleshooting

| Issue | Check | Fix |
|-------|-------|-----|
| Daemon not running | `fgp status calendar` | `fgp start calendar` |
| OAuth expired | Token age | Delete token, restart |
| No credentials | `~/.fgp/auth/google/` | Add credentials.json |

## Performance

- Cold start: ~50ms
- Warm call: ~10-30ms (10x faster than MCP)
