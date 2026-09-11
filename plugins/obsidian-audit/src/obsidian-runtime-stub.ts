/**
 * Minimal runtime stand-in for the types-only `obsidian` package.
 *
 * The npm `obsidian` package ships only `obsidian.d.ts` (its package.json
 * `main` is empty), so Vitest/Vite cannot load it as a real module. Unit
 * tests alias the specifier to this file via `vitest.config.ts`; it exposes
 * just the runtime surface the plugin code touches.
 */
export const notices: string[] = [];

export class Notice {
  constructor(message: string) {
    notices.push(message);
  }
}

export class App {}
export class TFile {}
export class Modal {}
export class ButtonComponent {}
export class Plugin {}
export class PluginSettingTab {}
export class Setting {}

export function normalizePath(path: string): string {
  return path.replace(/\\/g, "/").replace(/\/+/g, "/");
}
