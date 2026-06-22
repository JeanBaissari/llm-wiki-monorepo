# Codebase Wiki — Purpose

This template scaffolds a wiki for documenting a software codebase's
architecture, modules, APIs, and design decisions (ADRs).

**What it is for:**

- Living architectural documentation that stays close to the code.
- Recording every Architecture Decision Record (ADR) so context is never
  lost when a new team member joins or a decision is revisited.
- Mapping modules, their responsibilities, and their public APIs.
- Tracking why things are the way they are — not just what they do.

**What it is NOT for:**

- Inline code comments or generated API docs — let Doxygen, rustdoc,
  JSDoc, etc. handle that. This wiki is the high-level narrative.
- Bug tracking or issue management — use your issue tracker for that.
- Deployment or infrastructure documentation — consider the
  `cybersecurity` or `machine-learning` template if relevant.

**Key extensibility pattern:** Each ADR references the modules it
affects. Each module page links to the ADRs that shaped it.
