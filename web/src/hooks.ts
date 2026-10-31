import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Progress } from "./api";

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let live = true;
    setLoading(true);
    setError(null);
    fn()
      .then((d) => live && setData(d))
      .catch((e: Error) => live && setError(e.message))
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
  }, [...deps, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, loading, reload, setData };
}

export function useCollectionProgress(
  collectionId: string,
  active: boolean,
  onFinish: () => void,
): Progress | null {
  const [progress, setProgress] = useState<Progress | null>(null);
  const finish = useRef(onFinish);
  finish.current = onFinish;

  useEffect(() => {
    if (!active) return;
    const source = new EventSource(api.eventsUrl(collectionId));
    // el primer evento ya puede llegar en idle si el indexado terminó antes de conectar
    let pending = true;
    source.addEventListener("progress", (e) => {
      try {
        const p = JSON.parse((e as MessageEvent).data) as Progress;
        setProgress(p);
        if (p.state === "indexing") pending = true;
        else if (pending) {
          pending = false;
          finish.current();
        }
      } catch {
        // frame roto, el siguiente corrige el estado
      }
    });
    return () => source.close();
  }, [collectionId, active]);

  return active ? progress : null;
}

export function useStoredState<T extends string>(key: string, initial: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      return (localStorage.getItem(key) as T) || initial;
    } catch {
      return initial;
    }
  });
  const set = useCallback(
    (v: T) => {
      setValue(v);
      try {
        localStorage.setItem(key, v);
      } catch {
        // sin storage (modo privado), se queda solo en memoria
      }
    },
    [key],
  );
  return [value, set] as const;
}

export function useHotkey(match: (e: KeyboardEvent) => boolean, handler: () => void) {
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (match(e)) {
        e.preventDefault();
        ref.current();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
