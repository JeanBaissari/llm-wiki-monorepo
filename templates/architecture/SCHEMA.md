# Architecture Schema

Extends the shared base schema (`_shared/base-schema.md`) for the architecture domain. All base page types, frontmatter fields, naming conventions, index format, cross-referencing, and contradiction rules apply unless overridden below.

## Domain Page Types

| Type | Directory | Purpose |
|------|-----------|---------|
| service | architecture/services/ | A service or microservice — owner, SLA, dependencies, tech stack |
| infrastructure | architecture/infrastructure/ | Infrastructure — compute, networking, storage, CI/CD, observability |
| decision | architecture/decisions/ | An Architecture Decision Record (ADR) — context, options, outcome |
| diagram | architecture/diagrams/ | A system diagram — architecture view, data flow, deployment topology |

## Domain File Naming

- Services: `service-name.md` using kebab-case (e.g., `user-auth-service.md`, `payment-gateway.md`)
- Infrastructure: `provider-resource.md` (e.g., `aws-eks-cluster.md`, `terraform-state-backend.md`)
- Decisions: `NNNN-title.md` (e.g., `0001-use-postgresql.md`, `0002-message-queue-choice.md`)
- Diagrams: `view-name.md` (e.g., `system-context.md`, `container-diagram.md`)

## Domain-Specific Frontmatter

All base frontmatter fields (`type`, `title`, `tags`, `related`, `sources`, `created`, `updated`) apply.

### Service pages (with mandatory owner, SLA, dependencies, language, repo)

```yaml
service: string                # Service name
owner: string                  # Team or person responsible
sla: string                    # Service Level Agreement (e.g., "99.9% uptime, <200ms p95 latency")
dependencies: [string]         # Downstream service dependencies
language: string               # Primary programming language
repo: string                   # Repository URL or path
status: string                 # active | deprecated | sunset | planned
domain: string                 # Business domain (bounded context)
api_type: string               # REST | GraphQL | gRPC | async_events
criticality: string            # critical | high | medium | low
runbook: string                # Link to runbook
```

### Infrastructure pages

```yaml
resource: string               # Resource name or identifier
provider: string               # Cloud provider (aws | gcp | azure | on-prem)
type: string                   # Resource type (compute, database, network, storage, cache, queue)
environment: string            # production | staging | development | shared
cost_center: string            # Cost allocation tag
terraform_module: string       # Terraform module path (if applicable)
backup_policy: string          # Backup schedule and retention
```

### Decision pages (ADR format)

```yaml
decision: string               # Short title of the decision
status: string                 # proposed | accepted | deprecated | superseded
date: YYYY-MM-DD               # Decision date
deciders: [string]             # Who made the decision
context: string                # Problem statement and context
options:                       # Options considered
  - name: string
    pros: [string]
    cons: [string]
outcome: string                # What was chosen and why
consequences: [string]         # Resulting consequences (positive and negative)
supersedes: string             # ADR this replaces (if applicable)
superseded_by: string          # ADR that replaces this (if applicable)
```

### Diagram pages

```yaml
diagram: string                # Diagram title
type: string                   # system_context | container | component | sequence | deployment | data_flow
format: string                 # png | svg | drawio | mermaid | plantuml
source: string                 # Path to editable source file
scope: string                  # What system/subsystem this covers
stakeholders: [string]         # Intended audience
```

## Domain Index

`architecture/index.md` lists pages grouped by type (services, infrastructure, decisions, diagrams), plus an "ADR log" in reverse chronological order and a "Service dependency map" reference.
