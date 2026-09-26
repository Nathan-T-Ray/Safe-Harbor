import type { Catalog, CreateRun, EventPage, Snapshot } from '../../../shared/contracts';
export async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, { method: body === undefined ? 'GET' : 'POST', headers: { 'Content-Type': 'application/json' }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
  if (!response.ok) { const value = await response.text(); throw new Error(`${response.status}: ${value.slice(0, 450)}`); }
  return response.json() as Promise<T>;
}
export const api = {
  catalog: () => request<Catalog>('/catalog'),
  health: () => request<{status:string;read_only?:boolean;default_run_id?:string|null}>('/health'),
  create: (body: CreateRun) => request<{run_id:string}>('/runs', body),
  snapshot: (id:string) => request<Snapshot>(`/runs/${encodeURIComponent(id)}/snapshot`),
  events: (id:string, after:number) => request<EventPage>(`/runs/${encodeURIComponent(id)}/events?after_sequence=${after}`),
  resume: (id:string) => request(`/runs/${encodeURIComponent(id)}/resume`, {}),
  revise: (id:string, fixture_id:string) => request(`/runs/${encodeURIComponent(id)}/evidence-revisions`, { fixture_id }),
};
