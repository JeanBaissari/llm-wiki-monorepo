# Personal Growth Schema

Extends `_shared/base-schema.md`.

## Domain-Specific Page Types

| Type | Directory | Purpose |
|------|-----------|---------|
| goal | wiki/goals/ | A personal objective with target date and progress |
| habit | wiki/habits/ | A tracked behavior with frequency and streak |
| reflection | wiki/reflections/ | Periodic self-assessment entry |
| journal_entry | wiki/journal/ | A dated chronological record |

## Domain-Specific Frontmatter

### goal
```yaml
type: goal
target_date: YYYY-MM-DD
status: not_started | in_progress | completed | abandoned | on_hold
progress: 0            # percentage 0–100
category: health | career | finance | learning | relationship | creative | fitness | spiritual
milestones: []         # optional list of milestone descriptions
```

### habit
```yaml
type: habit
frequency: daily | weekly | monthly | custom
target_count: 0        # target times per frequency (e.g., 3 if "3x/week")
current_streak: 0
longest_streak: 0
status: active | paused | archived | completed
start_date: YYYY-MM-DD
cue: ""                # optional: trigger for the habit
reward: ""             # optional: reward after completing
```

### reflection
```yaml
type: reflection
period: ""             # e.g., "2025-06", "Q2 2025"
focus_areas: []        # slugs of relevant goal pages
rating: 0              # overall rating 1–10 (optional)
gratitude: []          # things you're grateful for (optional)
challenges: []         # obstacles encountered
```

### journal_entry
```yaml
type: journal_entry
date: YYYY-MM-DD
mood: terrible | bad | neutral | good | great
energy_level: 0        # 1–10
tags: []
related_goals: []      # slugs of relevant goals
```

## Extra Directories

See `extra-dirs.json`.
