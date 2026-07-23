// MCP Server — Python Sidecar Manager
//
// Manages a long-lived Python child process that communicates via
// JSON-RPC 2.0 over stdio. Spawned once at server startup, reused
// for all Python-backed tool calls. Eliminates per-call subprocess
// spawn overhead.
//
// Lifecycle:
//   1. start() — spawn sidecar, health check, confirm readiness
//   2. call(method, params) — JSON-RPC request, waits for response
//   3. stop() — SIGTERM → wait 5s → SIGKILL, graceful shutdown
//
// Auto-restart: if the sidecar dies mid-session, the next call()
// automatically restarts it (at most one retry).

import { spawn, ChildProcess } from "node:child_process";
import * as path from "node:path";
import * as fs from "node:fs";

// ── JSON-RPC 2.0 Types ──────────────────────────────────────────────────────

interface JsonRpcRequest {
  jsonrpc: "2.0";
  id: number | string;
  method: string;
  params: Record<string, unknown>;
}

interface JsonRpcResponse {
  jsonrpc: "2.0";
  id: number | string | null;
  result?: unknown;
  error?: {
    code: number;
    message: string;
    data?: unknown;
  };
}

interface PendingRequest {
  resolve: (result: unknown) => void;
  reject: (error: Error) => void;
  timer: NodeJS.Timeout;
}

// ── Sidecar Manager ─────────────────────────────────────────────────────────

export class PythonSidecar {
  private process: ChildProcess | null = null;
  private pendingRequests = new Map<number | string, PendingRequest>();
  private nextId = 1;
  private buffer = "";
  private wikiRoot: string;
  private sidecarPath: string;
  private requestTimeout: number;
  private restarting = false;
  private restartPromise: Promise<void> | null = null;

  /**
   * @param wikiRoot  Absolute path to the wiki project root
   * @param monorepoRoot  Absolute path to the monorepo root (for resolving skill/scripts/sidecar.py)
   * @param requestTimeout  Max milliseconds to wait for an RPC response (default: 120_000)
   */
  constructor(
    wikiRoot: string,
    monorepoRoot: string,
    requestTimeout: number = 120_000,
  ) {
    this.wikiRoot = wikiRoot;
    this.sidecarPath = path.resolve(
      monorepoRoot,
      "skill",
      "scripts",
      "sidecar.py",
    );
    this.requestTimeout = requestTimeout;
  }

  // ── Lifecycle ────────────────────────────────────────────────────────────

  /** Spawn the sidecar, wait for readiness, run health check. */
  async start(): Promise<void> {
    if (!fs.existsSync(this.sidecarPath)) {
      throw new Error(
        `Sidecar script not found: ${this.sidecarPath}`,
      );
    }

    this.process = spawn("python3", ["-u", this.sidecarPath], {
      stdio: ["pipe", "pipe", "pipe"],
      env: {
        ...process.env,
        LLM_WIKI_ROOT: this.wikiRoot,
        PYTHONUNBUFFERED: "1",
      },
    });

    // Buffer stdout data line by line (JSON-RPC: one response per line)
    this.process.stdout!.on("data", (chunk: Buffer) => {
      this.buffer += chunk.toString();
      const lines = this.buffer.split("\n");
      // Keep the last incomplete line in the buffer
      this.buffer = lines.pop() ?? "";
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        try {
          const response: JsonRpcResponse = JSON.parse(trimmed);
          this.handleResponse(response);
        } catch {
          // Non-JSON line (e.g., stray print) — ignore
          console.error(`[sidecar] Non-JSON stdout: ${trimmed.slice(0, 200)}`);
        }
      }
    });

    // Forward stderr for debugging
    this.process.stderr!.on("data", (data: Buffer) => {
      const text = data.toString().trim();
      if (text) {
        console.error(`[sidecar] ${text}`);
      }
    });

    // Detect exit
    this.process.on("exit", (code, signal) => {
      console.error(
        `[sidecar] Process exited (code=${code}, signal=${signal})`,
      );
      this.handleExit();
    });

    this.process.on("error", (err) => {
      console.error(`[sidecar] Process error: ${err.message}`);
      this.handleExit();
    });

    // Health check: ping the sidecar
    try {
      const result = await this.call("health", {});
      const health = result as { status: string; wiki_root: string };
      if (health.status !== "ok") {
        throw new Error(`Sidecar health check returned: ${JSON.stringify(result)}`);
      }
    } catch (e) {
      // Health check failed — kill and clean up
      this.killProcess();
      this.process = null;
      throw new Error(
        `Sidecar health check failed: ${e instanceof Error ? e.message : String(e)}`,
      );
    }
  }

  /** Graceful shutdown: SIGTERM → wait 5s → SIGKILL */
  async stop(): Promise<void> {
    if (!this.process) return;

    // Reject all pending requests
    for (const [, pending] of this.pendingRequests) {
      clearTimeout(pending.timer);
      pending.reject(new Error("Sidecar is shutting down"));
    }
    this.pendingRequests.clear();

    this.killProcess();
    this.process = null;

    // Small delay to let OS cleanup
    await new Promise((resolve) => setTimeout(resolve, 100));
  }

  // ── RPC Call Interface ──────────────────────────────────────────────────

  /**
   * Call a method on the sidecar, return a promise that resolves with
   * the result or rejects with an error.
   *
   * Supports concurrent calls via request ID matching per JSON-RPC spec.
   * Auto-restarts sidecar if it died (at most one retry).
   */
  async call(
    method: string,
    params: Record<string, unknown>,
  ): Promise<unknown> {
    // If sidecar is dead/restarting, handle restart
    if (!this.process || this.process.killed) {
      if (!this.restarting) {
        await this.restartOnce();
      } else if (this.restartPromise) {
        await this.restartPromise;
      } else {
        throw new Error("Sidecar not running and restart failed");
      }
    }

    const id = this.nextId++;
    const request: JsonRpcRequest = {
      jsonrpc: "2.0",
      id,
      method,
      params,
    };

    return new Promise<unknown>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingRequests.delete(id);
        reject(
          new Error(
            `Sidecar RPC timeout (${this.requestTimeout}ms): ${method}`,
          ),
        );
      }, this.requestTimeout);

      this.pendingRequests.set(id, { resolve, reject, timer });

      try {
        this.process!.stdin!.write(JSON.stringify(request) + "\n");
      } catch (e) {
        clearTimeout(timer);
        this.pendingRequests.delete(id);
        reject(
          new Error(
            `Failed to write to sidecar stdin: ${e instanceof Error ? e.message : String(e)}`,
          ),
        );
      }
    });
  }

  /** Check if sidecar is currently running */
  isRunning(): boolean {
    return this.process !== null && !this.process.killed && this.process.exitCode === null;
  }

  // ── Internal ─────────────────────────────────────────────────────────────

  /** Handle a JSON-RPC response from the sidecar's stdout */
  private handleResponse(response: JsonRpcResponse): void {
    const id = response.id;
    if (id === null || id === undefined) {
      // Notification (no id) — ignore for now
      return;
    }

    const pending = this.pendingRequests.get(id);
    if (!pending) {
      // Response to unknown request — probably timed out
      return;
    }

    clearTimeout(pending.timer);
    this.pendingRequests.delete(id);

    if (response.error) {
      pending.reject(
        new Error(
          `[${response.error.code}] ${response.error.message}` +
            (response.error.data ? `\n${response.error.data}` : ""),
        ),
      );
    } else {
      pending.resolve(response.result);
    }
  }

  /** Handle sidecar process exit — reject all pending, prepare for restart */
  private handleExit(): void {
    for (const [, pending] of this.pendingRequests) {
      clearTimeout(pending.timer);
      pending.reject(new Error("Sidecar process exited unexpectedly"));
    }
    this.pendingRequests.clear();
    this.process = null;
    this.restarting = false;
    this.restartPromise = null;
  }

  /** Kill the sidecar process (SIGTERM → wait → SIGKILL) */
  private killProcess(): void {
    if (!this.process || this.process.killed) return;

    try {
      this.process.stdin?.end(); // close stdin to signal EOF
    } catch {
      // Ignore — stdin may already be closed
    }

    this.process.kill("SIGTERM");

    // Wait up to 5s for clean exit, then force kill
    const forceKill = setTimeout(() => {
      if (this.process && !this.process.killed) {
        this.process.kill("SIGKILL");
      }
    }, 5000);

    // Don't let the timer keep the process alive
    if (forceKill.unref) {
      forceKill.unref();
    }
  }

  /** Attempt one restart of the sidecar */
  private async restartOnce(): Promise<void> {
    if (this.restarting) {
      // Already restarting — wait for it
      if (this.restartPromise) await this.restartPromise;
      return;
    }

    this.restarting = true;
    this.restartPromise = (async () => {
      try {
        // Clean up old process
        if (this.process && !this.process.killed) {
          this.killProcess();
        }
        this.process = null;

        // Small delay to let OS release resources
        await new Promise((resolve) => setTimeout(resolve, 500));

        // Restart
        await this.start();
      } catch (e) {
        this.process = null;
        throw new Error(
          `Sidecar restart failed: ${e instanceof Error ? e.message : String(e)}`,
        );
      } finally {
        this.restarting = false;
        this.restartPromise = null;
      }
    })();

    await this.restartPromise;
  }
}
