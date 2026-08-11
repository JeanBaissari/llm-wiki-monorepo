// MCP Server — llm_wiki_ask tool (LWM_033 / ADR-0029)
//
// Grounded "ask this wiki": retrieval over the LWM_030 community-summary pages
// + regular pages via the LWM_032 hybrid path + the summary-aware rerank,
// executed by the Python sidecar (invariant 4 — Python canonical, TS consumes).
//
// The sidecar RPC is deterministic and offline (no_llm=True): it returns the
// grounded passages, citation stems, confidence, and faithfulness — the agent
// consumer synthesizes the answer from that context. No sidecar → graceful
// error (there is intentionally no TS-side fallback: the ask retrieval + rerank
// is Python-canonical).

import { getProjectConfig, textResult, errorResult, ToolResult } from "../projects/config.js";
import { getSidecar } from "../registry.js";

/** Deterministic number formatting (1.0 stays "1", 0.9 stays "0.9"). */
function fmtNum(x: unknown, dflt: number): string {
  return String(parseFloat(Number(x ?? dflt).toFixed(2)));
}

export async function handleAsk(args: Record<string, unknown>): Promise<ToolResult> {
  try {
    const { layout } = getProjectConfig(args);
    const question = args.question as string | undefined;
    if (!question || question.trim() === "") {
      return errorResult("Missing required argument: question");
    }

    const topK = Math.min(Math.max((args.top_k as number) ?? 10, 1), 100);

    const sidecar = getSidecar();
    if (!sidecar || !sidecar.isRunning()) {
      return errorResult(
        "Ask requires the Python sidecar (grounded retrieval + rerank is Python-canonical); no sidecar is running.",
      );
    }

    let res: {
      result?: {
        question: string;
        mode: string;
        no_llm: boolean;
        answer?: string | null;
        citations?: string[];
        confidence?: number;
        faithfulness?: number;
        note?: string;
        summary_pages?: number;
        passages?: Array<{
          stem: string;
          title: string;
          path: string;
          type: string;
          matched?: string;
          excerpt?: string;
        }>;
      };
      error?: string;
    };
    try {
      res = (await sidecar.call("ask", {
        wiki_root: layout.root,
        question,
        top_k: topK,
      })) as typeof res;
    } catch (e) {
      return errorResult(`Ask sidecar RPC failed: ${e}`);
    }

    if (res.error) {
      return errorResult(res.error);
    }
    const r = res.result;
    if (!r) {
      return errorResult("Ask sidecar returned no result.");
    }

    const citations = r.citations ?? [];
    const passages = r.passages ?? [];

    const lines: string[] = [
      `# Ask: "${question}" (${passages.length} grounded passages, no_llm)`,
      "",
    ];
    if (r.note) {
      lines.push(`**Note:** ${r.note}`, "");
    }
    if (r.answer) {
      lines.push(`**Answer:** ${r.answer}`, "");
    } else {
      lines.push("**Answer:** (not synthesized — deterministic no_llm retrieval)", "");
    }
    if (citations.length > 0) {
      lines.push(`**Citations:** ${citations.map((c) => `[[${c}]]`).join(", ")}`, "");
    }
    lines.push(
      `**Confidence:** ${fmtNum(r.confidence, 0)}  **Faithfulness:** ${fmtNum(r.faithfulness, 1)}`,
      "",
    );

    for (let i = 0; i < passages.length; i++) {
      const p = passages[i];
      const tag = p.matched ? ` _[${p.matched}]_` : "";
      lines.push(
        `### ${i + 1}. ${p.title} (${p.stem})${tag}`,
        `**Path:** \`${p.path}\``,
        `${p.excerpt || "(no excerpt)"}`,
        "",
      );
    }

    return textResult(lines.join("\n"));
  } catch (e) {
    return errorResult(`Ask failed: ${e}`);
  }
}
