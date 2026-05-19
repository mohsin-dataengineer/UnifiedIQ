// Minimal SSE reader for `fetch` responses. EventSource is unusable here
// because the chat stream is a POST with a JSON body (Part 3.4).

export interface SSEMessage {
  event: string;
  data: unknown;
}

export async function* readSSE(
  response: Response,
): AsyncGenerator<SSEMessage> {
  if (!response.body) return;

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);

      let event = "message";
      const dataLines: string[] = [];
      for (const line of raw.split("\n")) {
        if (line.startsWith("event:")) {
          event = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          dataLines.push(line.slice(5).trim());
        }
      }
      if (dataLines.length === 0) continue;

      const payload = dataLines.join("\n");
      let data: unknown = payload;
      try {
        data = JSON.parse(payload);
      } catch {
        // leave as raw string if not JSON
      }
      yield { event, data };
    }
  }
}
