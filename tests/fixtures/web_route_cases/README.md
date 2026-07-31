# Web Route Fixture Cases

Each case documents a specific API behavior tested in `web-viewer/test/routes.test.ts`.

| Case | Endpoint | Expected |
|------|----------|----------|
| Page read | GET /api/page?path=wiki/index.md | 200, contains title |
| Raw markdown | GET /api/raw?path=wiki/index.md | 200, raw text |
| Search | GET /api/search?q=test | 200, results |
| Graph | GET /api/graph | 200, nodes+edges |
| Path traversal | GET /api/page?path=../../etc/passwd | 400/403 rejected |
| Bad audit payload | POST /api/audit (missing target) | 400 |
