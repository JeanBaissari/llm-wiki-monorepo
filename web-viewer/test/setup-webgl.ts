/**
 * Vitest setup: stub WebGL constants required by sigma at module-evaluation
 * time (it builds GL-enum lookup tables at import). The stubs are constants
 * only — real rendering still requires a browser WebGL context, which tests
 * never touch (sigma-view tests exercise the pure graph-construction path).
 */

const webgl2Enums: Record<string, number> = {
  DEPTH_BUFFER_BIT: 0x00000100,
  STENCIL_BUFFER_BIT: 0x00000400,
  COLOR_BUFFER_BIT: 0x00004000,
  POINTS: 0x0000,
  LINES: 0x0001,
  LINE_LOOP: 0x0002,
  LINE_STRIP: 0x0003,
  TRIANGLES: 0x0004,
  TRIANGLE_STRIP: 0x0005,
  TRIANGLE_FAN: 0x0006,
  BYTE: 0x1400,
  UNSIGNED_BYTE: 0x1401,
  SHORT: 0x1402,
  UNSIGNED_SHORT: 0x1403,
  INT: 0x1404,
  UNSIGNED_INT: 0x1405,
  FLOAT: 0x1406,
  BOOL: 0x8b56,
  ARRAY_BUFFER: 0x8892,
  ELEMENT_ARRAY_BUFFER: 0x8893,
  STATIC_DRAW: 0x88e4,
  DYNAMIC_DRAW: 0x88e8,
  VERTEX_SHADER: 0x8b31,
  FRAGMENT_SHADER: 0x8b30,
  COMPILE_STATUS: 0x8b81,
  LINK_STATUS: 0x8b82,
};

const webglEnums: Record<string, number> = { ...webgl2Enums };

if (typeof (globalThis as Record<string, unknown>).WebGL2RenderingContext === "undefined") {
  (globalThis as Record<string, unknown>).WebGL2RenderingContext = webgl2Enums;
}
if (typeof (globalThis as Record<string, unknown>).WebGLRenderingContext === "undefined") {
  (globalThis as Record<string, unknown>).WebGLRenderingContext = webglEnums;
}

// d3-drag reads `navigator.maxTouchPoints` when a drag behavior is created
// (renderGraph -> nodeSel.call(dragBehavior)); `navigator` only exists on
// Node 21+, so CI (Node 18) throws ReferenceError without this stub.
if (typeof (globalThis as Record<string, unknown>).navigator === "undefined") {
  (globalThis as Record<string, unknown>).navigator = { maxTouchPoints: 0, userAgent: "vitest" };
}
