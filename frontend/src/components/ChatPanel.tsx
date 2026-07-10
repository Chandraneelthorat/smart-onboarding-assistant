import { useEffect, useState } from "react";
import { apiGet, apiPost, CHAT_CONVERSATION_KEY } from "../api/client";

type Role = "user" | "assistant";

type Msg = { role: Role; content: string };

export function ChatPanel() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const cid = sessionStorage.getItem(CHAT_CONVERSATION_KEY);
    if (!cid) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await apiGet<{ conversation_id: string; messages: Msg[] }>(
          `/api/chat/conversation/${encodeURIComponent(cid)}`
        );
        if (!cancelled && data.messages?.length) {
          setMessages(data.messages);
        }
      } catch {
        sessionStorage.removeItem(CHAT_CONVERSATION_KEY);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function send() {
    const text = input.trim();
    if (!text || loading) return;
    setError(null);
    const prev = messages;
    const next: Msg[] = [...prev, { role: "user", content: text }];
    setMessages(next);
    setInput("");
    setLoading(true);
    const existingId = sessionStorage.getItem(CHAT_CONVERSATION_KEY);
    try {
      const payload: {
        messages: Msg[];
        conversation_id?: string;
      } = { messages: next };
      if (existingId) payload.conversation_id = existingId;

      const data = await apiPost<{ reply: string; conversation_id: string }>(
        "/api/chat",
        payload
      );
      sessionStorage.setItem(CHAT_CONVERSATION_KEY, data.conversation_id);
      setMessages([...next, { role: "assistant", content: data.reply }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Chat failed");
      setMessages(prev);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto flex h-[min(70vh,560px)] flex-col gap-4">
      <div className="flex-1 space-y-3 overflow-y-auto rounded-lg border border-slate-700 bg-slate-900/80 p-4 text-left">
        {messages.length === 0 && (
          <p className="text-sm text-slate-500">No messages yet.</p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={
              m.role === "user"
                ? "ml-8 rounded-lg bg-violet-600/25 px-3 py-2 text-slate-100 ring-1 ring-violet-500/30"
                : "mr-8 whitespace-pre-wrap rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-200"
            }
          >
            {m.content}
          </div>
        ))}
        {loading && (
          <p className="text-sm text-slate-500">Thinking…</p>
        )}
      </div>
      {error && <p className="text-sm text-red-300">{error}</p>}
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          className="text-sm text-slate-400 underline hover:text-slate-200"
          onClick={() => {
            sessionStorage.removeItem(CHAT_CONVERSATION_KEY);
            setMessages([]);
            setError(null);
          }}
        >
          New chat
        </button>
      </div>
      <div className="flex gap-2">
        <input
          className="flex-1 rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-slate-100"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), send())}
          placeholder="Type a message…"
        />
        <button
          type="button"
          disabled={loading || !input.trim()}
          onClick={send}
          className="rounded-lg bg-violet-600 px-4 py-2 text-white font-medium disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  );
}
