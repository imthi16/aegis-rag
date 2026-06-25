// Streaming query hook (CLAUDE.md §6.18): consumes the SSE /query/stream,
// revealing answer tokens live, then captures the final QueryResponse.

import { useCallback, useState } from "react";

import { BASE_URL } from "@/api/client";
import { useAuthStore } from "@/store/authStore";
import type { QueryResponse } from "@/types/api";

interface QueryStreamState {
  answer: string;
  response: QueryResponse | null;
  loading: boolean;
  error: string | null;
  ask: (query: string) => Promise<void>;
}

export function useQueryStream(): QueryStreamState {
  const [answer, setAnswer] = useState("");
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ask = useCallback(async (query: string): Promise<void> => {
    setLoading(true);
    setError(null);
    setAnswer("");
    setResponse(null);

    const token = useAuthStore.getState().accessToken;
    try {
      const resp = await fetch(`${BASE_URL}/query/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ query }),
      });
      if (!resp.ok || !resp.body) {
        setError(`Query failed (${resp.status}).`);
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let streamed = "";

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";
        for (const evt of events) {
          const isDone = evt.includes("event: done");
          const dataLines = evt
            .split("\n")
            .filter((l) => l.startsWith("data:"))
            .map((l) => l.slice(5));
          const data = dataLines.join("\n").replace(/^ /, "");
          if (isDone) {
            try {
              setResponse(JSON.parse(data) as QueryResponse);
            } catch {
              // ignore malformed final frame
            }
          } else if (data) {
            streamed += data;
            setAnswer(streamed);
          }
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Query failed.");
    } finally {
      setLoading(false);
    }
  }, []);

  return { answer, response, loading, error, ask };
}
