// Generic wrapper around fetch for /api/admin/models
const API_BASE = '/admin/models';

async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    ...options,
  });
  if (!res.ok) throw new Error(`API error: ${res.statusText}`);
  return res.json();
}

export async function listModels(): Promise<string[]> {
  return request<string[]>(`${API_BASE}`);
}

export async function getSchema(name: string): Promise<any> {
  return request<any>(`${API_BASE}/${name}/schema`);
}

export async function listResources(name: string, page = 1, perPage = 25): Promise<{ items: any[]; total: number }> {
  const params = new URLSearchParams({ page: String(page), per_page: String(perPage) });
  return request<{ items: any[]; total: number }>(`${API_BASE}/${name}?${params}`);
}

export async function deleteResource(name: string, id: string | number): Promise<void> {
  await request<void>(`${API_BASE}/${name}/${id}`, { method: 'DELETE' });
}

// add createResource, updateResource as needed...
