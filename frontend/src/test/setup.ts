import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { tokenStore } from '@/api/client';
import { server, signInAs } from './server';

// jsdom lacks these browser APIs; minimal stand-ins so components can mount.
HTMLDialogElement.prototype.showModal ??= function (this: HTMLDialogElement) {
  this.setAttribute('open', '');
};
HTMLDialogElement.prototype.close ??= function (this: HTMLDialogElement) {
  this.removeAttribute('open');
};
window.matchMedia ??= (query: string) =>
  ({
    matches: false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }) as unknown as MediaQueryList;
window.scrollTo = () => {};
Element.prototype.scrollIntoView ??= () => {};
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Every request must be handled: a forgotten handler fails the test loudly.
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
afterEach(() => {
  cleanup();
  server.resetHandlers(); // drop per-test overrides
  signInAs(null);
  tokenStore.set(null);
});
afterAll(() => server.close());
