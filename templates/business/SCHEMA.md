# Business Schema

Extends `_shared/base-schema.md`.

## Domain-Specific Page Types

| Type | Directory | Purpose |
|------|-----------|---------|
| meeting | wiki/meetings/ | Structured meeting minutes |
| decision | wiki/decisions/ | Recorded decision with rationale |
| project | wiki/projects/ | Project scope, status, and deliverables |
| stakeholder | wiki/stakeholders/ | Individual or group with interest in outcomes |

## Domain-Specific Frontmatter

### meeting
```yaml
type: meeting
date: YYYY-MM-DD
time: ""               # optional: start time
duration: ""           # optional: e.g., "1h"
attendees: []           # names or slugs
absent: []              # invited but not present
project: ""             # slug of related project (optional)
action_items: []        # list of items with owner/deadline (e.g., ["@alice: draft budget by 2025-07-01"])
location: ""            # physical or virtual
recording: ""           # optional: URL
```

### decision
```yaml
type: decision
date: YYYY-MM-DD
status: proposed | accepted | rejected | superseded | deferred
decided_by: ""           # person or body
context: ""              # background / what prompted the decision
alternatives: []         # other options considered
rationale: ""            # why this decision was made
consequences: []         # anticipated and observed effects
superseded_by: ""        # slug of decision that replaced this one
```

### project
```yaml
type: project
status: planning | active | on_hold | completed | cancelled
priority: critical | high | medium | low
start_date: YYYY-MM-DD
target_date: YYYY-MM-DD
owner: ""                # responsible person slug
team: []                 # slugs of team members
stakeholders: []         # slugs of stakeholder pages
milestones: []           # list of milestone descriptions with dates
risks: []                # list of risks with severity
budget: ""               # optional budget info
```

### stakeholder
```yaml
type: stakeholder
category: individual | team | department | organization | regulator | customer | investor | partner
role: ""                 # their role/relationship to the project/org
interest: low | medium | high
influence: low | medium | high
contact: ""              # optional contact info
engagement: ""           # engagement strategy / notes
```

## Extra Directories

See `extra-dirs.json`.
