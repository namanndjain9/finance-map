export type NodeInfo = {
  id: string;
  label: string;
  type: string;
  description: string;
  aliases: string[];
  landmark?: string | null;
};
export type EdgeInfo = { source: string; target: string; type: string };
export type Step = {
  node: string;
  type: string;
  label: string;
  description: string;
  via_edge: string | null;
  direction: "forward" | "backward" | null;
  practice_builds: string[];
};
export type Roadmap = {
  start: string;
  goal: string;
  steps: Step[];
  directed: boolean;
  regulated_nearby: string[];
};
export type Resolution = {
  start: string | null;
  goal: string | null;
  method: "rule" | "alias" | "embedding" | "llm";
  confidence: string;
  direction: string;
  start_defaulted: boolean;
  out_of_scope: boolean;
  reason: string;
  start_label: string | null;
  goal_label: string | null;
};
export type Status = { embeddings: boolean; llm: boolean; model: string };

export type StageId = "rule" | "tier1" | "tier2" | "tier3" | "roadmap" | "narrative";
export type StageStatus = "running" | "done" | "passed" | "skipped" | "failed";
export type StageState = { status: StageStatus; detail: string; ms: number };
export type Stages = Partial<Record<StageId, StageState>>;

export type StreamEvent =
  | { event: "progress"; stage: StageId; status: StageStatus; detail: string; ms: number }
  | { event: "resolution"; resolution: Resolution }
  | { event: "roadmap"; roadmap: Roadmap }
  | { event: "narrative"; text: string }
  | { event: "regulated"; activity: string; regulatory_items: string[]; study_alternatives: string[] }
  | { event: "out_of_scope"; message: string; reason: string }
  | { event: "error"; code: string; message: string }
  | { event: "done" };

export async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path} failed (${res.status})`);
  return res.json() as Promise<T>;
}

/** POST and read a server-sent-event stream (EventSource cannot POST). */
export async function streamPost(
  path: string,
  body: unknown,
  onEvent: (e: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    let detail = `${res.status}`;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* body was not JSON */
    }
    throw new Error(`Request failed: ${detail}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let cut: number;
    while ((cut = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      const data = frame
        .split("\n")
        .filter((l) => l.startsWith("data: "))
        .map((l) => l.slice(6))
        .join("\n");
      if (data) onEvent(JSON.parse(data) as StreamEvent);
    }
  }
}
