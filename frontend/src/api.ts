export class ApiError extends Error {
  constructor(public status: number, public code = 'request_failed') { super('Falha na solicitação'); }
}

function csrf(): string {
  const entry = document.cookie.split('; ').find((item) => item.startsWith('__Host-clinic_csrf='));
  return entry ? decodeURIComponent(entry.split('=').slice(1).join('=')) : '';
}

export async function api<T>(path: string, body?: unknown, method = body === undefined ? 'GET' : 'POST', signal?: AbortSignal): Promise<T> {
  const key = body && typeof body === 'object' && 'idempotency_key' in body && typeof body.idempotency_key === 'string' ? body.idempotency_key : undefined;
  const response = await fetch(`/v1${path}`, {
    method, credentials: 'same-origin', signal,
    headers: body === undefined ? {} : { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf(), ...(key ? {'Idempotency-Key': key} : {}) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const code = payload && typeof payload === 'object' && 'error' in payload && payload.error && typeof payload.error === 'object' && 'code' in payload.error && typeof payload.error.code === 'string' ? payload.error.code : 'request_failed';
    if (response.status === 401 && !path.startsWith('/auth/')) window.dispatchEvent(new Event('clinic:session-expired'));
    throw new ApiError(response.status, code);
  }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>;
}
