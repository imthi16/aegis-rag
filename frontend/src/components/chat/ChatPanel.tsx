import * as Dialog from "@radix-ui/react-dialog";
import { CornerDownLeft, Radar, Search, X } from "lucide-react";
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
  const [evidenceOpen, setEvidenceOpen] = useState(false);
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
    <div className="grid h-[calc(100vh-1px)] grid-cols-1 lg:grid-cols-[1fr_368px]">
      {/* Conversation column */}
      <div className="flex h-full min-h-0 flex-col">
        <div ref={scrollRef} className="scroll-slim flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <div className="mx-auto max-w-3xl space-y-4">
            {empty ? (
              <div className="mx-auto mt-14 max-w-md text-center">
                <div className="mx-auto mb-5 grid h-16 w-16 place-items-center rounded-xl border border-edge/12 bg-slab text-beacon shadow-panel">
                  <Radar className="h-7 w-7" />
                </div>
                <div className="eyebrow mb-2">// Interrogate corpus</div>
                <h2 className="text-xl font-semibold tracking-tight text-fg">
                  Ask, and see the evidence
                </h2>
                <p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed text-fg-dim">
                  Every answer is grounded in your authorized documents, cited to the source span,
                  and graded for faithfulness before you read it.
                </p>
                <div className="mt-6 space-y-2 text-left">
                  {SAMPLES.map((s, i) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => void send(s)}
                      className="group flex w-full items-center gap-3 rounded-md border border-edge/12 bg-slab px-3.5 py-2.5 text-left text-sm text-fg-dim transition-colors hover:border-beacon/30 hover:text-fg"
                    >
                      <span className="font-mono text-[11px] text-fg-faint group-hover:text-beacon">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <span className="flex-1">{s}</span>
                      <Search className="h-3.5 w-3.5 text-fg-faint opacity-0 transition-opacity group-hover:opacity-100" />
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
                  <MessageBubble role="assistant" text={answer || "Retrieving evidence…"} pending />
                )}
                {error && (
                  <div className="rounded-md bg-crimson/10 px-3 py-2 text-sm text-crimson ring-1 ring-inset ring-crimson/25">
                    {error}
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Evidence access below lg, where the rail is hidden. The grading is
            the basis of the answer (§6.18) — it must stay reachable, not just
            disappear at narrow widths. */}
        {response && (
          <div className="border-t border-edge/12 bg-slab/50 px-4 py-2 lg:hidden">
            <div className="mx-auto flex max-w-3xl justify-end">
              <Dialog.Root open={evidenceOpen} onOpenChange={setEvidenceOpen}>
                <Dialog.Trigger asChild>
                  <button
                    type="button"
                    className="inline-flex items-center gap-2 rounded-md px-2 py-1 font-mono text-[10px] uppercase tracking-eyebrow text-fg-dim transition-colors hover:bg-raise hover:text-fg"
                  >
                    <Search className="h-3.5 w-3.5" />
                    Evidence
                    <span className="text-fg-faint">
                      {response.retrieved_chunks.length} spans ·{" "}
                      {response.faithfulness_score.toFixed(2)}
                    </span>
                  </button>
                </Dialog.Trigger>
                <Dialog.Portal>
                  <Dialog.Overlay className="fixed inset-0 z-40 animate-fade-in bg-ink/70 backdrop-blur-sm lg:hidden" />
                  <Dialog.Content
                    aria-describedby={undefined}
                    className="fixed inset-y-0 right-0 z-50 flex w-[22rem] max-w-[92vw] animate-slide-up flex-col border-l border-edge/12 bg-slab shadow-lift focus:outline-none lg:hidden"
                  >
                    <div className="flex items-center justify-between border-b border-edge/12 px-5 py-3.5">
                      <Dialog.Title asChild>
                        <div className="eyebrow">// Evidence</div>
                      </Dialog.Title>
                      <Dialog.Close
                        aria-label="Close evidence"
                        className="grid h-8 w-8 place-items-center rounded-md text-fg-faint hover:bg-raise hover:text-fg"
                      >
                        <X className="h-4 w-4" />
                      </Dialog.Close>
                    </div>
                    <div className="scroll-slim flex-1 overflow-y-auto p-5">
                      <EvidencePanel response={response} />
                    </div>
                  </Dialog.Content>
                </Dialog.Portal>
              </Dialog.Root>
            </div>
          </div>
        )}

        {/* Command bar */}
        <div className="border-t border-edge/12 bg-slab/70 px-4 py-3.5 backdrop-blur md:px-8">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void send(input);
            }}
            className="mx-auto flex max-w-3xl items-center gap-2"
          >
            <span className="hidden font-mono text-sm text-beacon sm:inline">›</span>
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Query the corpus…"
              className="h-11 font-mono text-[13px]"
            />
            <Button type="submit" size="lg" disabled={loading || !input.trim()}>
              <span className="hidden sm:inline">Ask</span>
              <CornerDownLeft className="h-4 w-4" />
            </Button>
          </form>
        </div>
      </div>

      {/* Evidence rail */}
      <aside className="hidden border-l border-edge/12 bg-slab/40 lg:block">
        <div className="scroll-slim h-screen overflow-y-auto p-5">
          <div className="eyebrow mb-4">// Evidence</div>
          {response ? (
            <EvidencePanel response={response} />
          ) : (
            <div className="rounded-md border border-dashed border-edge/15 p-4 text-sm leading-relaxed text-fg-faint">
              Retrieval evidence — grades, faithfulness, and source spans — appears here once you
              ask.
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
