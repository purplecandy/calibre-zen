import { useEffect, useLayoutEffect, useRef } from 'react'

type Events<T> = T extends Window
  ? WindowEventMap
  : T extends Document
    ? DocumentEventMap
    : HTMLElementEventMap

/**
 * Listen to `type` on `target` for as long as the component is there. A
 * null target listens to nothing, for a listener that is only sometimes
 * wanted. The handler can change on every render without listening again.
 */
export function useEventListener<
  T extends Window | Document | HTMLElement,
  K extends keyof Events<T> & string,
>(target: T | null, type: K, handler: (e: Events<T>[K]) => void): void {
  const latest = useRef(handler)
  useLayoutEffect(() => {
    latest.current = handler
  })
  useEffect(() => {
    if (!target) return
    const listener = (e: Event) => latest.current(e as Events<T>[K])
    target.addEventListener(type, listener)
    return () => target.removeEventListener(type, listener)
  }, [target, type])
}
