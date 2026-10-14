// Route relative /api calls to the real backend, and stub browser APIs jsdom lacks.
const BACKEND = process.env.BACKEND_URL || 'http://127.0.0.1:8000'
const realFetch = globalThis.fetch
globalThis.fetch = (url, opts) => realFetch(typeof url === 'string' && url.startsWith('/') ? BACKEND + url : url, opts)
globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia = window.matchMedia || (() => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} }))
window.scrollTo = () => {}
window.confirm = () => true
class FakeWS { constructor() { this.readyState = 0; setTimeout(() => this.onclose && this.onclose(), 10) } send() {} close() {} }
globalThis.WebSocket = FakeWS
