/**
 * Vitest setup — Stream H CI infra + H.1b PR 2a refresh.
 *
 * Loads ``@testing-library/jest-dom`` matchers and ships a minimal
 * ``matchMedia`` polyfill required by Antd 5's responsive observers
 * (jsdom doesn't implement the API by default).
 *
 * The axios stub adapter prevents the shared ``apiClient`` from ever
 * hitting the network during tests: every request resolves to a
 * generic ``success=false`` envelope, which ``unwrap()`` converts to an
 * :class:`ApiError`. AuthContext catches non-401 errors silently and
 * keeps its optimistic identity, so existing tests that seed a JWT
 * still observe the JWT-derived identity. Tests that need richer
 * fixtures can override the adapter per-file via ``apiClient.defaults
 * .adapter = …``.
 */
import "@testing-library/jest-dom/vitest";

import { apiClient } from "../api/client";

if (typeof window !== "undefined" && !window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}

if (typeof globalThis.ResizeObserver === "undefined") {
  class ResizeObserverPolyfill {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  globalThis.ResizeObserver = ResizeObserverPolyfill as unknown as typeof ResizeObserver;
}

apiClient.defaults.adapter = (config) =>
  Promise.resolve({
    data: { success: false, data: null, error: { code: "TEST_STUB", message: "no network in tests" } },
    status: 200,
    statusText: "OK",
    headers: {},
    config,
    request: {},
  });
