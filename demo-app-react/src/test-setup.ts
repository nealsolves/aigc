import '@testing-library/jest-dom'

// Node.js 25 exposes a built-in `localStorage` that is non-functional without
// `--localstorage-file`. vitest's jsdom environment does not override it because
// the key already exists on `global`. Use the underlying JSDOM instance
// (stored on global.jsdom by vitest) to retrieve the real Storage objects and
// pin them on globalThis so that tests can call localStorage.clear() etc.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const jsdomInstance = (globalThis as any).jsdom
if (jsdomInstance?.window) {
  const actualWindow = jsdomInstance.window as Window

  function getStorageFromActualWindow(win: Window, key: 'localStorage' | 'sessionStorage') {
    let obj: object | null = win
    while (obj) {
      const desc = Object.getOwnPropertyDescriptor(obj, key)
      if (desc) {
        return desc.get ? desc.get.call(win) : desc.value
      }
      obj = Object.getPrototypeOf(obj)
    }
    return undefined
  }

  const jsdomLocal = getStorageFromActualWindow(actualWindow, 'localStorage')
  const jsdomSession = getStorageFromActualWindow(actualWindow, 'sessionStorage')

  if (jsdomLocal) {
    Object.defineProperty(globalThis, 'localStorage', {
      value: jsdomLocal,
      writable: true,
      configurable: true,
    })
  }
  if (jsdomSession) {
    Object.defineProperty(globalThis, 'sessionStorage', {
      value: jsdomSession,
      writable: true,
      configurable: true,
    })
  }
}
