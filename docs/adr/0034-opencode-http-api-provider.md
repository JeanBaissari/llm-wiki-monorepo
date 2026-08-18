# ADR 034: opencode HTTP API Provider

- **Status:** accepted
- **Date:** 2026-08-18
- **Supersedes:** ADR-0009 (superseded by ADR-0034)
- **Context:** ADR-0009 (superseded by ADR-0034) introduced a pipe-based IPC mechanism for the opencode provider. This mechanism writes prompts to `/tmp/llm-wiki-opencode/<session>/<request_id>/prompt.json`, signals readiness with a `.ready` marker, and polls for `response.json`. When running inside an opencode agent session, this creates a deadlock: the tool blocks polling for `response.json`, but the only entity that could write it (the opencode agent) is blocked running the tool. No watcher process existed to respond to prompts.
- **Decision:** Replace the filesystem-based IPC with HTTP API calls to the opencode server at `http://localhost:4096` (configurable via `OPENCODE_URL` env var). The provider uses `POST /session/{id}/message` for synchronous LLM calls. Each sidecar gets a dedicated session to avoid blocking the main agent conversation. Fallback chain: HTTP API → `LLM_WIKI_RESPONSE_FILE` → stderr prompt dump.
- **Consequences:** Easier: eliminates deadlock, works from any subprocess, uses standard HTTP. Harder: requires opencode server to be running (`opencode serve`), adds HTTP dependency (stdlib `urllib.request`). The old pipe-based IPC code is fully removed.
