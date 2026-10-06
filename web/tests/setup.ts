import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => { cleanup(); localStorage.clear(); });
Object.defineProperty(window, "matchMedia", { writable: true, value: vi.fn(() => ({
  matches: false, media: "", onchange: null, addEventListener: vi.fn(), removeEventListener: vi.fn(),
  addListener: vi.fn(), removeListener: vi.fn(), dispatchEvent: vi.fn(),
})) });
window.HTMLElement.prototype.scrollIntoView = vi.fn();
