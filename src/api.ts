export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, { ...options, headers: options?.body instanceof FormData ? options.headers : { 'Content-Type': 'application/json', ...options?.headers } });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body.detail || body.message;
    throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((e: {msg: string}) => e.msg).join('; ') : 'Não foi possível concluir a operação. Tente novamente.');
  }
  return response.json() as Promise<T>;
}
export function upload<T>(path: string, file: File, extra?: Record<string, string>) {
  const form = new FormData(); form.append('file', file);
  Object.entries(extra || {}).forEach(([key, value]) => form.append(key, value));
  return api<T>(path, { method: 'POST', body: form });
}
export const post = <T,>(path: string, body: unknown = {}) => api<T>(path, { method: 'POST', body: JSON.stringify(body) });
export const number = (n: number, digits = 0) => new Intl.NumberFormat('pt-BR', { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(n);
export const percent = (n: number) => `${number(n, 1)}%`;
export const date = (value: string, time = false) => new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T12:00:00Z` : value).toLocaleDateString('pt-BR', { timeZone: 'America/Sao_Paulo', day: '2-digit', month: '2-digit', year: 'numeric', ...(time ? { hour: '2-digit', minute: '2-digit' } : {}) });
export const areas = ['Programação', 'Análise', 'Dados', 'Suporte', 'Infraestrutura', 'Outra'];
export const statusLabel = { covered: 'Coberta', partial: 'Parcial', gap: 'Lacuna' };
