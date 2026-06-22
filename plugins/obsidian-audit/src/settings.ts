import { App, PluginSettingTab, Setting } from "obsidian";
import type LLMWikiAuditPlugin from "./main.js";

export interface LLMWikiAuditSettings {
  /** Path of the wiki root relative to the vault root. `.` means the vault itself is the wiki. */
  wikiRoot: string;
  /** Path of the audit directory relative to the wiki root. */
  auditDir: string;
  /** Free-form author name written into every audit file. */
  author: string;
}

export const DEFAULT_SETTINGS: LLMWikiAuditSettings = {
  wikiRoot: ".",
  auditDir: "audit",
  author: "me",
};

export class LLMWikiAuditSettingTab extends PluginSettingTab {
  plugin: LLMWikiAuditPlugin;

  constructor(app: App, plugin: LLMWikiAuditPlugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();
    containerEl.createEl("h2", { text: "LLM Wiki Audit — settings" });

    new Setting(containerEl)
      .setName("Wiki root")
      .setDesc(
        "Path relative to the vault root. If the vault is the wiki, leave this as `.`.",
      )
      .addText((text) =>
        text
          .setPlaceholder(".")
          .setValue(this.plugin.settings.wikiRoot)
          .onChange(async (value) => {
            this.plugin.settings.wikiRoot = value.trim() || ".";
            await this.plugin.saveSettings();
          }),
      );

    new Setting(containerEl)
      .setName("Audit directory")
      .setDesc("Path relative to the wiki root where audit files are written.")
      .addText((text) =>
        text
          .setPlaceholder("audit")
          .setValue(this.plugin.settings.auditDir)
          .onChange(async (value) => {
            this.plugin.settings.auditDir = value.trim() || "audit";
            await this.plugin.saveSettings();
          }),
      );

    new Setting(containerEl)
      .setName("Author")
      .setDesc("Written into every audit file's `author` field.")
      .addText((text) =>
        text
          .setPlaceholder("lewis")
          .setValue(this.plugin.settings.author)
          .onChange(async (value) => {
            this.plugin.settings.author = value.trim() || "me";
            await this.plugin.saveSettings();
          }),
      );
  }
}
