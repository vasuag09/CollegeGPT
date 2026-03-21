import "@testing-library/jest-dom";

// Provide a fake API URL for all tests
process.env.NEXT_PUBLIC_API_URL = "http://localhost:8000";

// Suppress framer-motion animation warnings in jsdom
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

// Suppress scrollIntoView not implemented
Element.prototype.scrollIntoView = () => {};
