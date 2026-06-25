import { ChatPanel } from "@/components/chat/ChatPanel";

export function ChatPage(): JSX.Element {
  return (
    <div className="mx-auto h-[calc(100vh-8rem)] max-w-6xl p-4">
      <ChatPanel />
    </div>
  );
}
