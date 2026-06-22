import {
  Editor,
  MarkdownFileInfo,
  MarkdownView,
  Notice,
  Plugin,
  TFile,
  normalizePath,
} from "obsidian";
import {
  DEFAULT_SETTINGS,
  LLMWikiAuditSettingTab,
  type LLMWikiAuditSettings,
} from "./settings.js";
import { FeedbackModal } from "./feedback-modal.js";
import { writeAudit } from "./writer.js";
import { fromMarkdown } from "audit-shared";

export default class LLMWikiAuditPlugin extends Plugin {
  settings!: LLMWikiAuditSettings;

  async onload(): Promise<void> {
    await this.loadSettings();

    this.addCommand({
      id: "audit-add-feedback",
      name: "Add feedback on selection",
      hotkeys: [{ modifiers: ["Mod"], key: "'" }],
      editorCallback: async (editor: Editor, ctx: MarkdownView | MarkdownFileInfo) => {
        if (!(ctx instanceof MarkdownView)) {
          new Notice("Audit feedback only works in a markdown editor view");
          return;
        }
        await this.handleAddFeedback(editor, ctx);
      },
    });

    this.addCommand({
      id: "audit-list-feedback-current-file",
      name: "List open feedback for current file",
      callback: async () => {
        await this.handleListFeedbackForCurrentFile();
      },
    });

    this.addCommand({
      id: "audit-open-folder",
      name: "Open audit folder",
      callback: () => {
        const path = this.resolveAuditDir();
        const folder = this.app.vault.getAbstractFileByPath(path);
        if (folder) {
          // @ts-expect-error — revealInFolder exists on the workspace API
          this.app.showInFolder?.(folder.path);
          new Notice(`Audit folder: ${folder.path}`);
        } else {
          new Notice(`Audit folder not found: ${path}`);
        }
      },
    });

    this.addSettingTab(new LLMWikiAuditSettingTab(this.app, this));
  }

  onunload(): void {}

  async loadSettings(): Promise<void> {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
  }

  async saveSettings(): Promise<void> {
    await this.saveData(this.settings);
  }

  private async handleAddFeedback(editor: Editor, view: MarkdownView): Promise<void> {
    const selection = editor.getSelection();
    if (!selection || !selection.trim()) {
      new Notice("Select some text first");
      return;
    }
    const file = view.file;
    if (!file) {
      new Notice("No file open");
      return;
    }

    const fileText = editor.getValue();
    const from = editor.getCursor("from");
    const to = editor.getCursor("to");
    const selStart = editor.posToOffset(from);
    const selEnd = editor.posToOffset(to);
    if (selEnd <= selStart) {
      new Notice("Empty selection");
      return;
    }

    const preview =
      selection.length > 280 ? selection.slice(0, 280) + "…" : selection;
    const modal = new FeedbackModal(this.app, preview);
    const result = await modal.open();
    if (!result) return;

    try {
      await writeAudit(this.app, this.settings, {
        file,
        fileText,
        selStart,
        selEnd,
        severity: result.severity,
        comment: result.comment,
      });
    } catch (err) {
      console.error("[llm-wiki-audit] write failed", err);
    }
  }

  private async handleListFeedbackForCurrentFile(): Promise<void> {
    const view = this.app.workspace.getActiveViewOfType(MarkdownView);
    if (!view || !view.file) {
      new Notice("No markdown file open");
      return;
    }
    const targetRel = this.fileRelToWiki(view.file.path);
    const auditDir = this.resolveAuditDir();

    const folder = this.app.vault.getAbstractFileByPath(auditDir);
    if (!folder) {
      new Notice(`Audit folder not found: ${auditDir}`);
      return;
    }

    const matches: string[] = [];
    const files = this.app.vault.getMarkdownFiles().filter((f: TFile) =>
      f.path.startsWith(auditDir + "/") && !f.path.startsWith(auditDir + "/resolved/"),
    );
    for (const f of files) {
      try {
        const text = await this.app.vault.read(f);
        const entry = fromMarkdown(text);
        if (entry.target === targetRel && entry.status === "open") {
          matches.push(`[${entry.severity}] ${entry.id}`);
        }
      } catch {
        // skip malformed
      }
    }

    if (matches.length === 0) {
      new Notice(`No open audits for ${targetRel}`);
    } else {
      new Notice(
        `${matches.length} open audit(s) for ${targetRel}:\n${matches.join("\n")}`,
        8000,
      );
    }
  }

  private fileRelToWiki(vaultPath: string): string {
    const root = this.settings.wikiRoot;
    if (!root || root === ".") return vaultPath;
    const normalized = root.replace(/\/+$/, "");
    if (vaultPath.startsWith(normalized + "/")) {
      return vaultPath.slice(normalized.length + 1);
    }
    return vaultPath;
  }

  private resolveAuditDir(): string {
    const root = this.settings.wikiRoot;
    const dir = this.settings.auditDir || "audit";
    if (!root || root === ".") return normalizePath(dir);
    return normalizePath(`${root.replace(/\/+$/, "")}/${dir.replace(/^\/+/, "")}`);
  }
}
