import { App, ButtonComponent, Modal, Notice } from "obsidian";
import type { Severity } from "audit-shared";

export interface FeedbackModalResult {
  severity: Severity;
  comment: string;
}

const SEVERITIES: Severity[] = ["info", "suggest", "warn", "error"];

/**
 * Chip-style severity picker + comment textarea. Matches the web viewer
 * dialog visually so users get a coherent experience across both tools.
 */
export class FeedbackModal extends Modal {
  private severity: Severity = "warn";
  private comment = "";
  private previewText: string;
  private resolver: ((value: FeedbackModalResult | null) => void) | null = null;

  constructor(app: App, previewText: string) {
    super(app);
    this.previewText = previewText;
  }

  open(): Promise<FeedbackModalResult | null> {
    return new Promise<FeedbackModalResult | null>((resolve) => {
      this.resolver = resolve;
      super.open();
    });
  }

  onOpen(): void {
    const { contentEl, modalEl, containerEl } = this;
    containerEl.addClass("llm-wiki-audit-modal");
    modalEl.addClass("llm-wiki-audit-modal");
    contentEl.empty();

    // Header
    const header = contentEl.createDiv({ cls: "audit-header" });
    header.createDiv({ cls: "audit-dot" });
    header.createEl("h3", { text: "New audit feedback" });

    // Selected text preview
    const previewField = contentEl.createDiv({ cls: "audit-field" });
    previewField.createEl("label", { cls: "audit-field-label", text: "Selected text" });
    const preview = previewField.createEl("pre", { cls: "audit-preview" });
    preview.setText(this.previewText);

    // Severity chips
    const sevField = contentEl.createDiv({ cls: "audit-field" });
    sevField.createEl("label", { cls: "audit-field-label", text: "Severity" });
    const sevRow = sevField.createDiv({ cls: "audit-severity" });
    for (const sev of SEVERITIES) {
      const label = sevRow.createEl("label");
      label.setAttribute("data-sev", sev);
      const input = label.createEl("input", {
        attr: { type: "radio", name: "audit-severity", value: sev },
      }) as HTMLInputElement;
      if (sev === this.severity) input.checked = true;
      label.createSpan({ cls: "audit-chip", text: sev });
      input.addEventListener("change", () => {
        if (input.checked) this.severity = sev;
      });
    }

    // Comment textarea
    const commentField = contentEl.createDiv({ cls: "audit-field" });
    commentField.createEl("label", {
      cls: "audit-field-label",
      text: "Comment (markdown allowed)",
    });
    const textarea = commentField.createEl("textarea", {
      cls: "audit-comment",
    }) as HTMLTextAreaElement;
    textarea.placeholder = "Explain what's wrong or what should change…";
    textarea.value = this.comment;
    textarea.addEventListener("input", () => {
      this.comment = textarea.value;
    });
    textarea.addEventListener("keydown", (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        this.trySave();
      }
    });
    window.setTimeout(() => textarea.focus(), 40);

    // Buttons
    const buttons = contentEl.createDiv({ cls: "audit-buttons" });

    new ButtonComponent(buttons)
      .setButtonText("Cancel")
      .onClick(() => this.finish(null));

    new ButtonComponent(buttons)
      .setButtonText("Save feedback")
      .setCta()
      .onClick(() => this.trySave());
  }

  onClose(): void {
    this.contentEl.empty();
    if (this.resolver) {
      this.resolver(null);
      this.resolver = null;
    }
  }

  private trySave(): void {
    if (!this.comment.trim()) {
      new Notice("Comment is empty");
      return;
    }
    this.finish({ severity: this.severity, comment: this.comment });
  }

  private finish(result: FeedbackModalResult | null): void {
    const r = this.resolver;
    this.resolver = null;
    this.close();
    if (r) r(result);
  }
}
