import { useEffect, useRef, useState } from 'react';
import { API_BASE_URL } from './api';

export type SseStatus = 'connecting' | 'open' | 'closed' | 'error';

export interface SseMessage<T = unknown> {
  type: string;
  data: T;
  ts: number;
}

export interface UseEventStreamOpts {
  types?: string[];
  project?: string;
  onMessage?: (msg: SseMessage) => void;
  /** Disable connection entirely. */
  enabled?: boolean;
}

/**
 * Opens an EventSource to `${API_BASE_URL}/events`. Subscribes to the
 * requested event types and invokes onMessage for each. Reconnects with
 * exponential backoff capped at 30s.
 *
 * The backend may not be running or the endpoint may be unimplemented; we
 * intentionally degrade silently and surface `status` to callers that care.
 */
export function useEventStream(opts: UseEventStreamOpts = {}) {
  const { types = [], project, onMessage, enabled = true } = opts;
  const [status, setStatus] = useState<SseStatus>('closed');
  const [last, setLast] = useState<SseMessage | null>(null);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  // Stable string key for the type list to make the effect dep happy.
  const typesKey = types.slice().sort().join(',');

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let es: EventSource | null = null;
    let retry = 0;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      if (cancelled) return;
      setStatus('connecting');
      const params = new URLSearchParams();
      if (project) params.set('project', project);
      const url = `${API_BASE_URL}/events${params.toString() ? `?${params.toString()}` : ''}`;
      try {
        es = new EventSource(url);
      } catch {
        scheduleReconnect();
        return;
      }

      es.onopen = () => {
        retry = 0;
        setStatus('open');
      };

      const handle = (evt: MessageEvent, type: string) => {
        let parsed: unknown = evt.data;
        try {
          parsed = JSON.parse(evt.data);
        } catch {
          /* leave as string */
        }
        const msg: SseMessage = { type, data: parsed, ts: Date.now() };
        setLast(msg);
        onMessageRef.current?.(msg);
      };

      // Generic `message` (no event field).
      es.onmessage = (evt) => handle(evt, 'message');

      // Named event listeners — subscribe to requested types.
      const typeList = typesKey ? typesKey.split(',') : [];
      for (const t of typeList) {
        if (!t) continue;
        es.addEventListener(t, (evt) => handle(evt as MessageEvent, t));
      }

      es.onerror = () => {
        setStatus('error');
        es?.close();
        scheduleReconnect();
      };
    };

    const scheduleReconnect = () => {
      if (cancelled) return;
      const delay = Math.min(30_000, 500 * 2 ** retry);
      retry += 1;
      timer = setTimeout(connect, delay);
    };

    connect();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      es?.close();
      setStatus('closed');
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, project, typesKey]);

  return { status, last };
}
