import type { AskResult, Device } from "./types";

async function json<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}
export const searchDevices = (q: string, code: string) =>
  fetch(`/api/devices?${new URLSearchParams({ q, ...(code ? { product_code: code } : {}), limit: "15" })}`).then(json<Device[]>);
export const ask = (question: string) =>
  fetch("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question }) })
    .then(json<AskResult>);
export const report = (k: string) => fetch(`/api/report/${encodeURIComponent(k)}`).then((r) => r.text());
