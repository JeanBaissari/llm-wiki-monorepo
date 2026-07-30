/**
 * TypeScript OperationContext mirroring Python src/llm_wiki/operation.py.
 * Used by MCP server tools and web viewer to track operation metadata.
 */
import { randomUUID } from "node:crypto";

export interface OperationInput {
  key: string;
  value: unknown;
}

export interface OperationManifest {
  operation_id: string;
  run_id: string;
  command: string;
  started: string;
  finished: string;
  inputs: Record<string, unknown>;
  touched_paths: string[];
  status: "completed" | "failed";
}

export class OperationContext {
  readonly operation_id: string;
  readonly run_id: string;
  readonly command: string;
  readonly started: string;
  readonly wiki_root: string;
  private _inputs: Map<string, unknown> = new Map();
  private _touched: Set<string> = new Set();
  private _finished: string | null = null;

  constructor(command: string, wiki_root: string) {
    this.operation_id = randomUUID();
    this.run_id = randomUUID();
    this.command = command;
    this.wiki_root = wiki_root;
    this.started = new Date().toISOString();
  }

  input(key: string, value: unknown): void {
    this._inputs.set(key, value);
  }

  touch(path: string): void {
    this._touched.add(path);
  }

  finish(): OperationManifest {
    this._finished = new Date().toISOString();
    return this.toManifest();
  }

  toManifest(): OperationManifest {
    return {
      operation_id: this.operation_id,
      run_id: this.run_id,
      command: this.command,
      started: this.started,
      finished: this._finished ?? new Date().toISOString(),
      inputs: Object.fromEntries(this._inputs),
      touched_paths: [...this._touched],
      status: "completed",
    };
  }
}
