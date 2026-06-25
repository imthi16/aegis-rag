import { useState } from "react";

import { EvidencePanel } from "@/components/chat/EvidencePanel";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { useQueryStream } from "@/hooks/useQueryStream";
import type { Citation } from "@/types/api";

interface Turn {
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
  insufficientEvidence?: boolean;
  faithful?: boolean;
}

export function ChatPanel(): JSX.Element {
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const { answer, response, loading, error, ask } = useQueryStream();

  const submit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    const q = input.trim();
    if (!q || loading) return;
    setTurns((t) => [...t, { role: "user", text: q }]);
    setInput("");
    await ask(q);
  };

  // Compose the assistant's settled turn once a response arrives.
  const liveAssistant: Turn | null = response
    ? {
        role: "assistant",
        text: response.answer,
        citations: response.citations,
        insufficientEvidence: response.insufficient_evidence,
        faithful: response.faithful,
      }
    : answer
      ? { role: "assistant", text: answer }
      : null;

  return (
    <div className="grid h-full grid-cols-3 gap-4">
      <div className="col-span-2 flex flex-col">
        <div className="flex-1 space-y-3 overflow-y-auto rounded bg-slate-100 p-4">
          {turns.map((t, i) => (
            <MessageBubble key={i} {...t} />
          ))}
          {liveAssistant && <MessageBubble {...liveAssistant} />}
          {error && <div className="text-sm text-red-600">{error}</div>}
        </div>
        <form onSubmit={submit} className="mt-3 flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question over your corpus…"
            className="flex-1 rounded border border-slate-300 px-3 py-2"
          />
          <button
            type="submit"
            disabled={loading}
            className="rounded bg-slate-800 px-4 py-2 text-white disabled:opacity-50"
          >
            {loading ? "…" : "Ask"}
          </button>
        </form>
      </div>
      <aside className="overflow-y-auto rounded border border-slate-200 bg-white p-3">
        <h2 className="mb-2 font-semibold text-slate-700">Evidence</h2>
        {response ? (
          <EvidencePanel response={response} />
        ) : (
          <p className="text-sm text-slate-400">Ask a question to see retrieval evidence.</p>
        )}
      </aside>
    </div>
  );
}
