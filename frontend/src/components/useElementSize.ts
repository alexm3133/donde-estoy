import { useEffect, useState } from "react";

/**
 * Live size of an element (used to tell the map what the cards cover).
 *
 * Returns a callback ref rather than taking a ref object, so it also works
 * for elements that mount later (e.g. after data has loaded).
 */
export function useElementSize<T extends HTMLElement>(): [
  (element: T | null) => void,
  { width: number; height: number },
] {
  const [element, setElement] = useState<T | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    if (!element) return;
    const update = () => {
      const { width, height } = element.getBoundingClientRect();
      setSize((current) =>
        current.width === width && current.height === height ? current : { width, height },
      );
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, [element]);
  return [setElement, size];
}
