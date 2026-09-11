import { beforeEach, describe, expect, it } from "vitest";
import { fromMarkdown } from "audit-shared";
import type { App, TFile } from "obsidian";
import { notices } from "./obsidian-runtime-stub.js";
import type { LLMWikiAuditSettings } from "./settings.js";
import { writeAudit } from "./writer.js";

interface CreatedFile {
  path: string;
  name: string;
}

function makeApp() {
  const created: Array<{ path: string; data: string }> = [];
  const folders: string[] = [];
  const existing = new Map<string, unknown>();
  return {
    created,
    folders,
    vault: {
      getAbstractFileByPath: (path: string) => existing.get(path) ?? null,
      createFolder: async (path: string) => {
        folders.push(path);
        existing.set(path, { path });
      },
      create: async (path: string, data: string): Promise<CreatedFile> => {
        const file: CreatedFile = { path, name: path.split("/").pop() ?? path };
        created.push({ path, data });
        existing.set(path, file);
        return file;
      },
    },
  };
}

const WIKI_SETTINGS: LLMWikiAuditSettings = {
  wikiRoot: "wiki",
  auditDir: "audit",
  author: "tester",
};

const FILE_TEXT = "alpha\nbeta gamma\ndelta";

function selection(): { selStart: number; selEnd: number } {
  const selStart = FILE_TEXT.indexOf("beta");
  return { selStart, selEnd: selStart + "beta".length };
}

describe("writeAudit", () => {
  beforeEach(() => {
    notices.length = 0;
  });

  it("writes a schema-valid audit entry anchored to the selection", async () => {
    const app = makeApp();
    const { selStart, selEnd } = selection();

    const createdFile = await writeAudit(app as unknown as App, WIKI_SETTINGS, {
      file: { path: "wiki/notes/foo.md" } as unknown as TFile,
      fileText: FILE_TEXT,
      selStart,
      selEnd,
      severity: "warn",
      comment: "beta looks wrong",
    });

    expect(app.folders).toEqual(["wiki/audit"]);
    expect(app.created).toHaveLength(1);

    const { path, data } = app.created[0]!;
    expect(path).toMatch(
      /^wiki\/audit\/\d{8}-\d{6}-[0-9a-f]{4}-beta-looks-wrong\.md$/,
    );
    expect(createdFile.path).toBe(path);
    expect(notices).toContain(`Audit filed: ${createdFile.name}`);

    const entry = fromMarkdown(data);
    expect(entry.target).toBe("notes/foo.md");
    expect(entry.severity).toBe("warn");
    expect(entry.author).toBe("tester");
    expect(entry.source).toBe("obsidian-plugin");
    expect(entry.status).toBe("open");
    expect(entry.target_lines).toEqual([2, 2]);
    expect(entry.anchor_text).toBe("beta");
    expect(entry.body).toContain("beta looks wrong");
    expect(entry.body).toContain("# Resolution");
  });

  it("keeps vault-relative targets for files outside the wiki root", async () => {
    const app = makeApp();
    const { selStart, selEnd } = selection();

    await writeAudit(app as unknown as App, WIKI_SETTINGS, {
      file: { path: "other/note.md" } as unknown as TFile,
      fileText: FILE_TEXT,
      selStart,
      selEnd,
      severity: "suggest",
      comment: "outside the wiki",
    });

    const entry = fromMarkdown(app.created[0]!.data);
    expect(entry.target).toBe("other/note.md");
    expect(entry.severity).toBe("suggest");
  });

  it("writes to the vault root when the wiki root is '.'", async () => {
    const app = makeApp();
    const { selStart, selEnd } = selection();

    await writeAudit(
      app as unknown as App,
      { wikiRoot: ".", auditDir: "audit", author: "me" },
      {
        file: { path: "notes/foo.md" } as unknown as TFile,
        fileText: FILE_TEXT,
        selStart,
        selEnd,
        severity: "info",
        comment: "root wiki",
      },
    );

    expect(app.created[0]!.path).toMatch(/^audit\//);
    const entry = fromMarkdown(app.created[0]!.data);
    expect(entry.target).toBe("notes/foo.md");
  });
});
