const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

export type DocumentItem = {
  id: string;
  filename: string;
  content_type: string;
  file_size: number;
  status: "pending" | "processing" | "ready" | "failed" | string;
  error_message?: string | null;
  created_at: string;
};

export type HistoryItem = {
  id: string;
  question: string;
  answer: string;
  document_ids: string[];
  session_id?: string | null;
  created_at: string;
};

function authHeaders(token?: string | null): HeadersInit {
  const headers: HeadersInit = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join(", ");
    }
    return JSON.stringify(data);
  } catch {
    return res.statusText || "Request failed";
  }
}

export async function apiSignup(full_name: string, email: string, password: string): Promise<TokenPair> {
  const res = await fetch(`${API_URL}/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ full_name, email, password }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiLogin(email: string, password: string): Promise<TokenPair> {
  const res = await fetch(`${API_URL}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiDocuments(token: string): Promise<DocumentItem[]> {
  const res = await fetch(`${API_URL}/documents`, { headers: authHeaders(token) });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiUpload(token: string, file: File): Promise<DocumentItem> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_URL}/upload`, {
    method: "POST",
    headers: authHeaders(token),
    body: form,
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiDeleteDocument(token: string, id: string): Promise<void> {
  const res = await fetch(`${API_URL}/documents/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(await parseError(res));
}

export async function apiHistory(token: string): Promise<{ items: HistoryItem[]; total: number }> {
  const res = await fetch(`${API_URL}/history`, { headers: authHeaders(token) });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiAsk(
  token: string,
  question: string,
  documentIds: string[],
): Promise<{ answer: string; sources: string[]; history_id: string }> {
  const res = await fetch(`${API_URL}/ask`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ question, document_ids: documentIds.length ? documentIds : null, stream: false }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiAskStream(
  token: string,
  question: string,
  documentIds: string[],
  onToken: (token: string) => void,
): Promise<{ answer: string; history_id?: string }> {
  const res = await fetch(`${API_URL}/ask`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ question, document_ids: documentIds.length ? documentIds : null, stream: true }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  if (!res.body) throw new Error("No response stream");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let answer = "";
  let historyId: string | undefined;
  let eventName = "message";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const part of parts) {
      const lines = part.split("\n");
      let dataLine = "";
      for (const line of lines) {
        if (line.startsWith("event:")) eventName = line.slice(6).trim();
        if (line.startsWith("data:")) dataLine += line.slice(5).trim();
      }
      if (!dataLine) continue;
      try {
        const payload = JSON.parse(dataLine);
        if (eventName === "token" && payload.token) {
          answer += payload.token;
          onToken(payload.token);
        }
        if (eventName === "done") {
          answer = payload.answer || answer;
          historyId = payload.history_id;
        }
        if (eventName === "error") {
          throw new Error(payload.detail || "Stream error");
        }
      } catch (err) {
        if (err instanceof Error && err.message !== "Stream error" && !String(err.message).includes("JSON")) {
          throw err;
        }
        if (err instanceof SyntaxError) continue;
        throw err;
      }
    }
  }

  return { answer, history_id: historyId };
}

export { API_URL };
