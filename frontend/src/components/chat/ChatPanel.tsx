import { MessagesSquare, Send, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { EvidencePanel } from "@/components/chat/EvidencePanel";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useQueryStream } from "@/hooks/useQueryStream";
import type { Citation } from "@/types/api";

interface Turn {
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
  insufficientEvidence?: boolean;
  faithful?: boolean;
}

const SAMPLES = [
  "Summarize our data-retention policy",
  "What controls satisfy HIPAA audit requirements?",
  "Which documents mention incident response?",
];

export function ChatPanel(): JSX.Element {
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const { answer, response, loading, error, ask } = useQueryStream();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, answer, response]);

  const send = async (q: string): Promise<void> => {
    const query = q.trim();
    if (!query || loading) return;
    setTurns((t) => [...t, { role: "user", text: query }]);
    setInput("");
    await ask(query);
  };

  const liveAssistant: Turn | null = response
    ? {
        role: "assistant",
        text: response.answer,
        citations: response.citations,
        insufficientEvidence: response.insufficient_evidence,
        faithful: response.faithful,
      }
    : null;

  const empty = turns.length === 0 && !loading;

  return (
    <div className="grid h-[calc(100vh-1px)] grid-cols-1 lg:grid-cols-[1fr_360px]">
      {/* Conversation column */}
      <div className="flex h-full min-h-0 flex-col">
        <div ref={scrollRef} className="scroll-slim flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <div className="mx-auto max-w-3xl space-y-4">
            {empty ? (
              <div className="mx-auto mt-16 max-w-md text-center">
                <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-indigo-600/10 ring-1 ring-indigo-600/20">
                  <MessagesSquare className="h-7 w-7 text-indigo-600" />
                </div>
                <h2 className="text-lg font-semibold text-slate-800">Ask your corpus</h2>
                <p className="mt-1 text-sm text-slate-500">
                  Answers are grounded in your documents, cited, and faithfulness-graded.
                </p>
                <div className="mt-5 flex flex-col gap-2">
                  {SAMPLES.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => void send(s)}
                      className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-left text-sm text-slate-600 shadow-soft transition-colors hover:border-indigo-200 hover:bg-indigo-50/40"
                    >
                      <Sparkles className="h-4 w-4 text-indigo-400" />
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <>
                {turns.map((t, i) => (
                  <MessageBubble key={i} {...t} />
                ))}
                {liveAssistant && <MessageBubble {...liveAssistant} />}
                {loading && !response && (
                  <MessageBubble role="assistant" text={answer || "Thinking…"} pending />
                )}
                {error && (
                  <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700 ring-1 ring-inset ring-rose-600/20">
                    {error}
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Composer */}
        <div className="border-t border-slate-200 bg-white/70 px-4 py-3 backdrop-blur md:px-8">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void send(input);
            }}
            className="mx-auto flex max-w-3xl items-center gap-2"
          >
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question over your corpus…"
              className="h-11"
            />
            <Button type="submit" size="lg" disabled={loading || !input.trim()}>
              <Send className="h-4 w-4" />
              <span className="hidden sm:inline">Ask</span>
            </Button>
          </form>
        </div>
      </div>

      {/* Evidence column */}
      <aside className="hidden border-l border-slate-200 bg-white/50 lg:block">
        <div className="scroll-slim h-screen overflow-y-auto p-5">
          <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-700">
            <Sparkles className="h-4 w-4 text-indigo-500" /> Evidence
          </h2>
          {response ? (
            <EvidencePanel response={response} />
          ) : (
            <p className="text-sm text-slate-400">
              Retrieval evidence — grades, faithfulness, and source chunks — appears here after you
              ask.
            </p>
          )}
        </div>
      </aside>
    </div>
  );
}
