import '@testing-library/jest-dom/vitest'

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

Object.defineProperty(window, 'ResizeObserver', {
  configurable: true,
  value: ResizeObserverMock,
})

function createStorageMock(): Storage {
  let values: Record<string, string> = {}
  return {
    get length() { return Object.keys(values).length },
    clear: () => { values = {} },
    getItem: (key) => values[key] ?? null,
    key: (index) => Object.keys(values)[index] ?? null,
    removeItem: (key) => { delete values[key] },
    setItem: (key, value) => { values[key] = String(value) },
  }
}

if (!globalThis.localStorage) {
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: createStorageMock() })
}

if (!globalThis.sessionStorage) {
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, value: createStorageMock() })
}
