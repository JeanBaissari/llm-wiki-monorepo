import { getProjectConfig, textResult, errorResult, ToolResult } from "../projects/config.js";
import { readFile, fileExists } from "../wiki-fs.js";
import { safeJoin, isBinaryExtension } from "../security/path-safety.js";

export async function handleReadFile(args: Record<string, unknown>): Promise<ToolResult> {
  try {
    const { root: wp, layout } = getProjectConfig(args);
    const filePath = args.path as string | undefined;
    if (!filePath) {
      return errorResult("Missing required argument: path");
    }

    // Project-relative path only — safeJoin rejects absolute paths
    const resolved = safeJoin(layout.root, filePath);

    if (isBinaryExtension(resolved)) {
      return errorResult(`Binary files are not readable: "${resolved}". Text files only.`);
    }

    const exists = await fileExists(resolved);
    if (!exists) {
      return errorResult(`File not found: ${resolved}`);
    }

    let content = await readFile(resolved);
    const maxBytes = 120 * 1024;

    if (Buffer.byteLength(content, "utf-8") > maxBytes) {
      const truncated = Buffer.from(content, "utf-8").subarray(0, maxBytes);
      content = truncated.toString("utf-8") + "\n\n_… (truncated at 120KB)_";
    }

    return textResult(content);
  } catch (e) {
    return errorResult(`Failed to read file: ${e}`);
  }
}
