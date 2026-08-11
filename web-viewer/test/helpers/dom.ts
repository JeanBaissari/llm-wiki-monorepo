/**
 * Minimal SVG DOM shim sufficient for d3-selection / d3-drag / d3-zoom in
 * Node (vitest default environment is "node"). Real browsers are not assumed:
 * jsdom/happy-dom are not dependencies, so this thin fake stands in for the
 * handful of DOM APIs d3 touches when rendering the graph SVG.
 */

const SVG_NS = "http://www.w3.org/2000/svg";

export interface FakeListener {
  type: string;
  listener: (...args: unknown[]) => void;
}

export class FakeClassList {
  private set = new Set<string>();
  add(...names: string[]): void {
    for (const n of names) this.set.add(n);
  }
  remove(...names: string[]): void {
    for (const n of names) this.set.delete(n);
  }
  contains(name: string): boolean {
    return this.set.has(name);
  }
  toggle(name: string, force?: boolean): boolean {
    if (force === undefined) {
      if (this.set.has(name)) {
        this.set.delete(name);
        return false;
      }
      this.set.add(name);
      return true;
    }
    if (force) this.set.add(name);
    else this.set.delete(name);
    return force;
  }
  toString(): string {
    return Array.from(this.set).join(" ");
  }
}

export class FakeElement {
  nodeName: string;
  namespaceURI = SVG_NS;
  ownerDocument!: FakeDocument;
  parentNode: FakeElement | null = null;
  childNodes: FakeElement[] = [];
  attributes = new Map<string, string>();
  listeners: FakeListener[] = [];
  textContent = "";
  clientWidth = 1200;
  clientHeight = 800;
  classList = new FakeClassList();
  style = {
    setProperty: () => {},
    getPropertyValue: () => "",
  };
  [key: string]: unknown;

  constructor(nodeName: string) {
    this.nodeName = nodeName.toUpperCase();
  }

  setAttribute(name: string, value: string): void {
    this.attributes.set(name, String(value));
    if (name === "class") {
      this.classList = new FakeClassList();
      for (const c of String(value).split(/\s+/).filter(Boolean)) this.classList.add(c);
    }
  }
  getAttribute(name: string): string | null {
    return this.attributes.get(name) ?? null;
  }
  removeAttribute(name: string): void {
    this.attributes.delete(name);
  }
  setAttributeNS(_ns: string, name: string, value: string): void {
    this.setAttribute(name, value);
  }
  getAttributeNS(_ns: string, name: string): string | null {
    return this.getAttribute(name);
  }

  appendChild<T extends FakeElement>(child: T): T {
    this.insertBefore(child, null);
    return child;
  }
  insertBefore<T extends FakeElement>(child: T, before: FakeElement | null): T {
    child.parentNode = this;
    if (before == null) {
      this.childNodes.push(child);
    } else {
      const i = this.childNodes.indexOf(before);
      if (i >= 0) this.childNodes.splice(i, 0, child);
      else this.childNodes.push(child);
    }
    return child;
  }
  removeChild<T extends FakeElement>(child: T): T {
    const i = this.childNodes.indexOf(child);
    if (i >= 0) this.childNodes.splice(i, 1);
    child.parentNode = null;
    return child;
  }

  addEventListener(type: string, listener: (...args: unknown[]) => void): void {
    this.listeners.push({ type, listener });
  }
  removeEventListener(type: string, listener: (...args: unknown[]) => void): void {
    const i = this.listeners.findIndex((l) => l.type === type && l.listener === listener);
    if (i >= 0) this.listeners.splice(i, 1);
  }

  querySelectorAll(selector: string): FakeElement[] {
    return descendants(this).filter((el) => matches(el, selector));
  }
}

export class FakeDocument {
  documentElement = new FakeElement("html");
  createElementNS(ns: string, name: string): FakeElement {
    const el = new FakeElement(name);
    el.namespaceURI = ns;
    el.ownerDocument = this;
    return el;
  }
}

function descendants(root: FakeElement): FakeElement[] {
  const out: FakeElement[] = [];
  const walk = (el: FakeElement) => {
    for (const c of el.childNodes) {
      out.push(c);
      walk(c);
    }
  };
  walk(root);
  return out;
}

function matches(el: FakeElement, selector: string): boolean {
  const sel = selector.trim();
  if (sel === "*") return true;
  // Supports "tag.class" compound selectors only (all this codebase uses).
  const [tagPart, ...classParts] = sel.split(".");
  if (tagPart) {
    if (el.nodeName !== tagPart.toUpperCase()) return false;
  }
  for (const cls of classParts) {
    if (!el.classList.contains(cls)) return false;
  }
  return true;
}

export function createSvg(): FakeElement {
  const doc = new FakeDocument();
  const svg = doc.createElementNS(SVG_NS, "svg");
  svg.ownerDocument = doc;
  svg.clientWidth = 1200;
  svg.clientHeight = 800;
  return svg;
}

/** Deterministic serialization of the element tree (structure + attributes). */
export function serialize(el: FakeElement): string {
  const attrs = Array.from(el.attributes.entries())
    .map(([k, v]) => ` ${k}="${v}"`)
    .join("");
  const kids = el.childNodes.map(serialize).join("");
  if (kids) return `<${el.nodeName}${attrs}>${kids}</${el.nodeName}>`;
  return `<${el.nodeName}${attrs}/>`;
}
