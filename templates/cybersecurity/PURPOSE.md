# Cybersecurity Wiki — Purpose

This template scaffolds a wiki for tracking vulnerabilities, exploits,
tools, and security advisories.

**What it is for:**

- Maintaining an internal CVE-style knowledge base of vulnerabilities
  relevant to your systems, with severity scoring and remediation status.
- Documenting exploits and proof-of-concept code with mitigations.
- Cataloguing security tools, their capabilities, and usage patterns.
- Tracking security advisories from vendors, researchers, and
  intelligence feeds.

**What it is NOT for:**

- Vulnerability scanning results or SIEM alerting — use dedicated
  security tooling (Nessus, Wazuh, Splunk) for operational monitoring.
- Incident response runbooks — consider a dedicated ops template or
  tool.
- Compliance documentation (SOC 2, ISO 27001) — those require
  structured evidence collection beyond a wiki.

**Key extensibility pattern:** Each vulnerability links to the exploits
that target it and the advisories that disclose it. Tools pages link to
the vulnerabilities they detect or exploit.
