// MCP Server — FTS5 Search Adapter
//
// Thin adapter wrapping the SQLite FTS5 search implementation.
// Re-exports the search function from search.ts for use by MCP tools.
// The adapter lives in mcp-server/src/ since search is an MCP concern (Q6).
//
// LWM_05 provides the index; this adapter provides the query interface
// used by the MCP server's llm_wiki_search tool handler.

export { search, buildIndex, clearIndex, IndexBuildingError } from "../search.js";
