import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from './api';
import { pt } from './locales';
import type { Membership, RecordData } from './types';

export function useRemote<T>(member: Membership, path: string | null) {
  return useQuery({ queryKey: ['clinic', member.id, path], queryFn: ({signal}) => api<T>(path!, undefined, 'GET', signal), enabled: path !== null, retry: false });
}

export function errorText(error: unknown): string {
  return error instanceof ApiError ? pt.errors[error.code] ?? pt.error : pt.error;
}

export function useAction(member?: Membership) {
  const client = useQueryClient();
  const keys = useRef(new Map<string, string>());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState('');
  async function run<T>(work: () => Promise<T>, message = ''): Promise<T | undefined> {
    setBusy(true); setError(undefined); setNotice('');
    try {
      const result = await work();
      if (member) await client.invalidateQueries({ queryKey: ['clinic', member.id] });
      setNotice(message); return result;
    } catch (caught) { setError(caught); return undefined; } finally { setBusy(false); }
  }
  async function send<T>(path: string, body: RecordData, method = 'POST'): Promise<T> {
    const bytes = new TextEncoder().encode(JSON.stringify(body));
    const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))).map(value => value.toString(16).padStart(2, '0')).join('');
    const fingerprint = `${method}:${path}:${hash}`;
    const key = keys.current.get(fingerprint) ?? crypto.randomUUID();
    keys.current.set(fingerprint, key);
    const result = await api<T>(path, { ...body, idempotency_key: key }, method);
    keys.current.delete(fingerprint);
    return result;
  }
  return { busy, error, notice, run, send, setNotice };
}

export function Feedback({ action }: { action: ReturnType<typeof useAction> }) {
  return <>{action.error !== undefined && <p role="alert" className="feedback error">{errorText(action.error)}</p>}{action.notice && <p role="status" className="feedback success">{action.notice}</p>}</>;
}
export function Loading() { return <p role="status" className="empty">{pt.loading}</p>; }
export function Empty({ children = pt.noRecords }: {children?: ReactNode}) { return <div className="empty"><span aria-hidden="true">◇</span><p>{children}</p></div>; }
export function Failure({ error }: { error: unknown }) { return <p role="alert" className="feedback error">{errorText(error)}</p>; }
export function PageHeader({title, description, children}: {title: string; description?: string; children?: ReactNode}) {
  return <header className="page-header"><div><p className="eyebrow">{pt.workspace}</p><h1 id="page-title" tabIndex={-1}>{title}</h1>{description && <p>{description}</p>}</div>{children}</header>;
}
export function Status({value}: {value: string}) { return <span className={`badge status-${value}`}>{pt.statuses[value] ?? value}</span>; }
export function Label({text, children}: {text: string; children: ReactNode}) { return <label className="field"><span>{text}</span>{children}</label>; }

export function Modal({title, children, onClose}: {title: string; children: ReactNode; onClose: () => void}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { const element = dialog.current; element?.showModal(); return () => element?.close(); }, []);
  return <dialog ref={dialog} aria-labelledby="dialog-title" onCancel={(event) => {event.preventDefault(); onClose();}}><div className="dialog-header"><h2 id="dialog-title">{title}</h2><button type="button" className="icon-button secondary" onClick={onClose} aria-label={pt.close}>×</button></div>{children}</dialog>;
}

export function localDay(timezone = 'America/Sao_Paulo'): string {
  const parts = new Intl.DateTimeFormat('en-CA', {timeZone: timezone, year:'numeric', month:'2-digit', day:'2-digit'}).formatToParts(new Date());
  return ['year','month','day'].map(type => parts.find(part => part.type === type)?.value ?? '').join('-');
}
export function shiftDay(day: string, count: number): string { const date = new Date(`${day}T12:00:00Z`); date.setUTCDate(date.getUTCDate()+count); return date.toISOString().slice(0,10); }
export function formatDay(day: string): string { return new Intl.DateTimeFormat('pt-BR', {day:'2-digit',month:'short',timeZone:'UTC'}).format(new Date(`${day}T12:00:00Z`)); }
export function minutes(value: number): string { return `${String(Math.floor(value/60)).padStart(2,'0')}:${String(value%60).padStart(2,'0')}`; }
