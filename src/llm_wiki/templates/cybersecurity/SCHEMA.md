# Cybersecurity Domain Schema

Extends the base schema with cybersecurity-specific page types,
directories, and frontmatter conventions.

## Extra Directories

| Directory | Purpose |
|-----------|---------|
| `wiki/vulnerabilities/` | Vulnerability entries (CVE-style) |
| `wiki/exploits/` | Exploit details and proof-of-concept notes |
| `wiki/tools/` | Security tool documentation |
| `wiki/advisories/` | Security advisories and bulletins |

## Domain Page Types

| Type | Directory | Purpose | Frontmatter Fields |
|------|-----------|---------|--------------------|
| `vulnerability` | `wiki/vulnerabilities/` | A security vulnerability (CVE-style entry) | `cve_id: "CVE-YYYY-XXXXX"`, `severity: critical \| high \| medium \| low \| informational`, `cvss_score: 0.0-10.0`, `status: open \| reviewing \| patched \| mitigated \| false_positive \| accepted_risk`, `affected_systems: []`, `discovered: YYYY-MM-DD` |
| `exploit` | `wiki/exploits/` | An exploit or proof-of-concept | `type: remote \| local \| dos \| mitm`, `target: []`, `complexity: low \| medium \| high`, `mitigation: ""` |
| `tool` | `wiki/tools/` | A security tool | `category: scanner \| framework \| monitor \| forensic \| defensive \| offensive`, `language`, `license`, `url` |
| `advisory` | `wiki/advisories/` | A security advisory or bulletin | `source: vendor \| researcher \| feed`, `date: YYYY-MM-DD`, `severity: critical \| high \| medium \| low`, `vulnerabilities: []` |

## Naming Conventions

- **Vulnerabilities:** `cve-YYYY-XXXXX.md` (e.g., `cve-2024-12345.md`)
- **Exploits:** `brief-exploit-name.md` (e.g., `log4j-rce.md`)
- **Tools:** `tool-name.md` (e.g., `nmap.md`, `burp-suite.md`)
- **Advisories:** `source-YYYY-MM-DD.md` (e.g., `msrc-2024-03-15.md`)

## Frontmatter Template

```yaml
---
type: vulnerability | exploit | tool | advisory
title: Human-readable title
tags: []
related: []
sources: []
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

### Vulnerability-specific
```yaml
type: vulnerability
cve_id: "CVE-2024-12345"
severity: critical | high | medium | low | informational
cvss_score: 9.8
status: open | reviewing | patched | mitigated | false_positive | accepted_risk
affected_systems:
  - "system-name"
discovered: 2024-01-15
```

### Exploit-specific
```yaml
type: exploit
exploit_type: remote | local | dos | mitm
target:
  - vulnerability-slug
complexity: low | medium | high
mitigation: "Upgrade to version X.Y.Z"
```

### Tool-specific
```yaml
type: tool
category: scanner | framework | monitor | forensic | defensive | offensive
language: "Python"
license: "MIT"
url: "https://github.com/..."
```

### Advisory-specific
```yaml
type: advisory
source: vendor | researcher | feed
date: 2024-01-15
severity: critical | high | medium | low
vulnerabilities:
  - vulnerability-slug
```

## Conventions

1. Every vulnerability entry should include a brief description, impact
   assessment, and remediation steps.
2. CVSS scores should follow CVSS v3.1 vector notation.
3. Exploit pages should link to the vulnerability(ies) they target and
   describe the mitigation.
4. Tool pages should document installation, basic usage, and how they
   integrate into a broader security workflow.
5. When a vulnerability's status changes, update the `status` field and
   add a note in the body with the date of the change.
