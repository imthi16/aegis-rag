import { CitationChip } from "@/components/citations/CitationChip";
import type { Citation } from "@/types/api";

interface MessageBubbleProps {
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
  insufficientEvidence?: boolean;
  faithful?: boolean;
}

export function MessageBubble({
  role,
  text,
  citations = [],
  insufficientEvidence = false,
  faithful = true,
}: MessageBubbleProps): JSX.Element {
  const isUser = role === "user";
  return (
    <div className={isUser ? "flex justify-end" : "flex justify-start"}>
      <div
        className={
          isUser
            ? "max-w-[75%] rounded-lg bg-slate-800 px-3 py-2 text-white"
            : "max-w-[75%] rounded-lg bg-white px-3 py-2 text-slate-800 shadow"
        }
      >
        {!isUser && insufficientEvidence && (
          <div className="mb-1 rounded bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">
            Insufficient evidence
          </div>
        )}
        {!isUser && !insufficientEvidence && !faithful && (
          <div className="mb-1 rounded bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-800">
            Low faithfulness — not verified
          </div>
        )}
        <p className="whitespace-pre-wrap">{text}</p>
        {citations.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {citations.map((c) => (
              <CitationChip key={`${c.marker}-${c.chunk_id}`} citation={c} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
