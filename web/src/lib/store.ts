// A value outside React that components follow: the address, settings, an
// open dialog. Every module-level store in the app is one of these.
import { useSyncExternalStore } from 'react'

export interface Store<T> {
  get(): T
  /** Replace the value. Everyone following it hears, even when it is the same. */
  set(next: T | ((current: T) => T)): void
  /** Call `f` after every change. Returns a function to stop. */
  subscribe(f: () => void): () => void
  /** The value, or the part `select` picks, kept up to date in a component. */
  use(): T
  use<S>(select: (value: T) => S): S
}

export function createStore<T>(initial: T): Store<T> {
  let value = initial
  const listeners = new Set<() => void>()
  const subscribe = (f: () => void) => {
    listeners.add(f)
    return () => {
      listeners.delete(f)
    }
  }
  function use(): T
  function use<S>(select: (value: T) => S): S
  function use<S>(select?: (value: T) => S): T | S {
    return useSyncExternalStore(subscribe, () =>
      select ? select(value) : value,
    )
  }
  return {
    get: () => value,
    set(next) {
      value = typeof next === 'function' ? (next as (c: T) => T)(value) : next
      listeners.forEach((f) => f())
    },
    subscribe,
    use,
  }
}
