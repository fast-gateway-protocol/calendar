# Calendar Workflow

Fast Google Calendar operations via FGP daemon. 10x faster than MCP-based tools.

## Available Methods

| Method | Description |
|--------|-------------|
| `calendar.today` | Get today's events |
| `calendar.upcoming` | Get upcoming events |
| `calendar.search` | Search events by query |
| `calendar.create` | Create a new event |
| `calendar.free_slots` | Find available time slots |

## Commands

### calendar.today - Today's Events

No parameters. Returns all events for today.

```bash
fgp call calendar.today
```

**Response:**
```json
{
  "date": "2026-01-13",
  "events": [{"summary": "...", "start": "...", "end": "..."}],
  "count": 5
}
```

---

### calendar.upcoming - Upcoming Events

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `days` | integer | No | 7 | Days to look ahead |
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
fgp call calendar.create -p '{"summary": "Meeting", "start": "2026-01-15T14:00:00Z", "end": "2026-01-15T15:00:00Z"}'
```

**Response:**
```json
{
  "created": true,
  "event_id": "abc123",
  "html_link": "https://calendar.google.com/..."
}
```

---

### calendar.free_slots - Find Free Time

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `duration_minutes` | integer | Yes | - | Required slot duration |
| `days` | integer | No | 7 | Days to search |

```bash
fgp call calendar.free_slots -p '{"duration_minutes": 30}'
```

**Response:**
```json
{
  "duration_minutes": 30,
  "free_slots": [
    {"start": "2026-01-13T10:00:00Z", "end": "2026-01-13T10:30:00Z"}
  ],
  "count": 20
}
```

Note: Returns working hours (9am-5pm) on weekdays only.

## Workflow Steps

1. **User requests calendar action**
2. **Run appropriate `fgp call calendar.*` command**
3. **Parse JSON response**
4. **Present results to user**

## Troubleshooting

| Issue | Check | Fix |
|-------|-------|-----|
| Daemon not running | `fgp status calendar` | `fgp start calendar` |
| OAuth expired | Token age | Delete token, restart |
| No credentials | `~/.fgp/auth/google/` | Add credentials.json |

## Performance

- Cold start: ~50ms
- Warm call: ~10-30ms (10x faster than MCP)
