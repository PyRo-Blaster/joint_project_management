import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// jsdom does not implement matchMedia; the theme provider reads it. Provide a stable stub.
if (!window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

// Radix UI primitives (Popover, Select, DropdownMenu) use Pointer Capture and scrollIntoView,
// which jsdom does not implement — without these stubs their overlays never open under test.
if (!Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = vi.fn(() => false) as never;
  Element.prototype.setPointerCapture = vi.fn() as never;
  Element.prototype.releasePointerCapture = vi.fn() as never;
}
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = vi.fn() as never;
}

// Radix's Popper (Popover/Select/DropdownMenu) needs ResizeObserver, absent in jsdom.
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as never;
}

// jsdom has no PointerEvent constructor; Radix opens overlays on pointer events, so userEvent
// clicks are dropped without this. Minimal polyfill carrying the fields Radix reads.
if (typeof window.PointerEvent === "undefined") {
  class MockPointerEvent extends MouseEvent {
    public pointerId: number;
    public pointerType: string;
    constructor(type: string, params: PointerEventInit = {}) {
      super(type, params);
      this.pointerId = params.pointerId ?? 1;
      this.pointerType = params.pointerType ?? "mouse";
    }
  }
  window.PointerEvent = MockPointerEvent as never;
}
