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
  function clearError() { setError(undefined); }
  return { busy, error, notice, run, send, setNotice, clearError };
}

/* Ícones em SVG inline: consistentes entre sistemas e compatíveis com a CSP (sem imagens externas). */
const icons: Record<string, ReactNode> = {
  calendar: <><rect x="3" y="4.5" width="18" height="16" rx="2.5"/><path d="M3 9.5h18M8 2.5v4M16 2.5v4"/></>,
  inbox: <><path d="M4 13.5 6.2 5.6A2 2 0 0 1 8.1 4h7.8a2 2 0 0 1 1.9 1.6L20 13.5V18a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z"/><path d="M4 13.5h4.5l1.5 2.5h4l1.5-2.5H20"/></>,
  clock: <><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></>,
  services: <><path d="M9 3.5h6M12 3.5v4"/><rect x="4" y="7.5" width="16" height="13" rx="2.5"/><path d="M12 11v6M9 14h6"/></>,
  team: <><circle cx="9" cy="8.5" r="3.2"/><path d="M3.5 19.5c.6-3.2 2.8-5 5.5-5s4.9 1.8 5.5 5"/><circle cx="17" cy="9.5" r="2.4"/><path d="M16.5 14.6c2.2.1 3.6 1.7 4 4.4"/></>,
  settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3h0a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8v0a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/></>,
  plug: <><path d="M9 3v4M15 3v4"/><path d="M6 7h12v3a6 6 0 0 1-12 0z"/><path d="M12 16v5"/></>,
  audit: <><path d="M7 3.5h7l4 4V19a1.5 1.5 0 0 1-1.5 1.5h-9.5A1.5 1.5 0 0 1 5.5 19V5A1.5 1.5 0 0 1 7 3.5z"/><path d="M13.5 3.5V8H18M8.5 12.5h7M8.5 16h5"/></>,
  shield: <><path d="M12 3 4.5 6v5.5c0 4.5 3.2 8.2 7.5 9.5 4.3-1.3 7.5-5 7.5-9.5V6z"/><path d="m9 12 2 2 4-4"/></>,
  building: <><rect x="4.5" y="3.5" width="15" height="17" rx="1.5"/><path d="M9 7.5h1.5M13.5 7.5H15M9 11h1.5M13.5 11H15M9 14.5h1.5M13.5 14.5H15M10.5 20.5v-3h3v3"/></>,
  menu: <path d="M4 6.5h16M4 12h16M4 17.5h16"/>,
  plus: <path d="M12 5v14M5 12h14"/>,
  left: <path d="m14.5 6-6 6 6 6"/>,
  right: <path d="m9.5 6 6 6-6 6"/>,
  close: <path d="M6 6l12 12M18 6 6 18"/>,
  refresh: <><path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3"/><path d="M19.5 4.5v4h-4"/></>,
  logout: <><path d="M14 4.5h3.5A1.5 1.5 0 0 1 19 6v12a1.5 1.5 0 0 1-1.5 1.5H14"/><path d="M10 16.5 5.5 12 10 7.5M5.5 12H15"/></>,
  user: <><circle cx="12" cy="8.5" r="3.8"/><path d="M4.5 20c.9-3.6 3.8-5.7 7.5-5.7s6.6 2.1 7.5 5.7"/></>,
  lock: <><rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"/></>,
  check: <path d="m5 12.5 4.5 4.5L19 7.5"/>,
  alert: <><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5v5.5M12 16.2v.3"/></>,
  info: <><circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5M12 7.8v.3"/></>,
  eye: <><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/></>,
  eyeOff: <><path d="M10 5.7a9.6 9.6 0 0 1 2-.2c6 0 9.5 6.5 9.5 6.5a17 17 0 0 1-2.4 3.2M6.6 6.6C3.9 8.3 2.5 12 2.5 12S6 18.5 12 18.5a9.3 9.3 0 0 0 5.4-1.7"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2M3.5 3.5l17 17"/></>,
  phone: <path d="M5 4.5h3.5l1.5 4-2 1.3a10.5 10.5 0 0 0 6.2 6.2l1.3-2 4 1.5V19a1.5 1.5 0 0 1-1.6 1.5C10.6 20 4 13.4 3.5 6.1A1.5 1.5 0 0 1 5 4.5z"/>,
  chat: <path d="M20 12.5a7.5 7.5 0 0 1-11 6.6L4 20.5l1.4-4.6A7.5 7.5 0 1 1 20 12.5z"/>,
  globe: <><circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.3 2.4 3.4 5.2 3.4 8.5s-1.1 6.1-3.4 8.5c-2.3-2.4-3.4-5.2-3.4-8.5S9.7 5.9 12 3.5z"/></>,
};
export type IconName = keyof typeof icons;
export function Icon({name, size = 18}: {name: IconName; size?: number}) {
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">{icons[name]}</svg>;
}

export function Feedback({ action, errorsOnly = false }: { action: ReturnType<typeof useAction>; errorsOnly?: boolean }) {
  return <>
    {action.error !== undefined && <p role="alert" className="feedback error"><Icon name="alert"/><span>{errorText(action.error)}</span></p>}
    {!errorsOnly && action.notice && <p role="status" className="feedback success"><Icon name="check"/><span>{action.notice}</span><button type="button" className="feedback-dismiss" aria-label={pt.dismiss} onClick={() => action.setNotice('')}><Icon name="close" size={16}/></button></p>}
  </>;
}
export function Loading({label = pt.loading}: {label?: string}) { return <p role="status" className="loading"><span className="spinner" aria-hidden="true"/>{label}</p>; }
export function Empty({ children = pt.noRecords, icon = 'info', compact = false }: {children?: ReactNode; icon?: IconName; compact?: boolean}) {
  return <div className={compact ? 'empty compact' : 'empty'}>{!compact && <span className="empty-icon"><Icon name={icon} size={22}/></span>}<p>{children}</p></div>;
}
export function Failure({ error }: { error: unknown }) { return <p role="alert" className="feedback error"><Icon name="alert"/><span>{errorText(error)}</span></p>; }
export function PageHeader({title, description, children}: {title: string; description?: string; children?: ReactNode}) {
  useEffect(() => { document.title = `${title} · ${pt.title}`; }, [title]);
  return <header className="page-header"><div className="page-heading"><h1 id="page-title" tabIndex={-1}>{title}</h1>{description && <p>{description}</p>}</div>{children && <div className="page-actions">{children}</div>}</header>;
}
export function Status({value}: {value: string}) { return <span className={`badge status-${value}`}>{pt.statuses[value] ?? value}</span>; }
export function Label({text, hint, children}: {text: string; hint?: string; children: ReactNode}) { return <label className="field"><span>{text}</span>{children}{hint && <small className="field-hint">{hint}</small>}</label>; }

export function Modal({title, children, onClose, size}: {title: string; children: ReactNode; onClose: () => void; size?: 'wide' | 'narrow'}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { const element = dialog.current; element?.showModal(); return () => element?.close(); }, []);
  return <dialog ref={dialog} className={size ? `dialog-${size}` : undefined} aria-labelledby="dialog-title" onCancel={(event) => {event.preventDefault(); onClose();}}><div className="dialog-header"><h2 id="dialog-title">{title}</h2><button type="button" className="icon-button ghost" onClick={onClose} aria-label={pt.close}><Icon name="close"/></button></div><div className="dialog-body">{children}</div></dialog>;
}

/** Botão que pede confirmação explícita antes de uma ação destrutiva. */
export function ConfirmButton({label, title, message, confirmLabel, busy, onConfirm, className = 'text-button danger'}: {label: string; title: string; message: string; confirmLabel?: string; busy?: boolean; onConfirm: () => Promise<unknown> | void; className?: string}) {
  const [open, setOpen] = useState(false);
  return <>
    <button type="button" className={className} disabled={busy} onClick={() => setOpen(true)}>{label}</button>
    {open && <Modal title={title} size="narrow" onClose={() => setOpen(false)}>
      <p>{message}</p>
      <div className="form-actions"><button type="button" className="secondary" onClick={() => setOpen(false)}>{pt.cancel}</button>
        <button type="button" className="danger" disabled={busy} onClick={() => { setOpen(false); void onConfirm(); }}>{confirmLabel ?? label}</button></div>
    </Modal>}
  </>;
}

export function localDay(timezone = 'America/Sao_Paulo'): string {
  const parts = new Intl.DateTimeFormat('en-CA', {timeZone: timezone, year:'numeric', month:'2-digit', day:'2-digit'}).formatToParts(new Date());
  return ['year','month','day'].map(type => parts.find(part => part.type === type)?.value ?? '').join('-');
}
export function shiftDay(day: string, count: number): string { const date = new Date(`${day}T12:00:00Z`); date.setUTCDate(date.getUTCDate()+count); return date.toISOString().slice(0,10); }
/** Segunda-feira da semana que contém o dia (a agenda da clínica usa semana de segunda a domingo). */
export function weekStart(day: string): string { const weekday = (new Date(`${day}T12:00:00Z`).getUTCDay() + 6) % 7; return shiftDay(day, -weekday); }
function utcNoon(day: string) { return new Date(`${day}T12:00:00Z`); }
export function formatDay(day: string): string { return new Intl.DateTimeFormat('pt-BR', {day:'2-digit',month:'short',timeZone:'UTC'}).format(utcNoon(day)); }
export function formatWeekday(day: string): string { return new Intl.DateTimeFormat('pt-BR', {weekday:'short',timeZone:'UTC'}).format(utcNoon(day)).replace('.', ''); }
export function formatLongDay(day: string): string { return new Intl.DateTimeFormat('pt-BR', {weekday:'long',day:'numeric',month:'long',year:'numeric',timeZone:'UTC'}).format(utcNoon(day)); }
export function formatRange(first: string, last: string): string {
  const format = (day: string, options: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat('pt-BR', {...options, timeZone:'UTC'}).format(utcNoon(day));
  if (first === last) return formatLongDay(first);
  const sameMonth = first.slice(0,7) === last.slice(0,7);
  return `${format(first, sameMonth ? {day:'numeric'} : {day:'numeric',month:'short'})} a ${format(last, {day:'numeric',month:'short',year:'numeric'})}`;
}
export function formatInstant(value: string, timezone?: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('pt-BR', {dateStyle:'short', timeStyle:'short', timeZone: timezone}).format(date);
}
export function minutes(value: number): string { return `${String(Math.floor(value/60)).padStart(2,'0')}:${String(value%60).padStart(2,'0')}`; }

/** Converte "AAAA-MM-DDTHH:mm" no fuso da clínica para ISO 8601 com deslocamento explícito. */
export function zonedToIso(local: string, timezone = 'America/Sao_Paulo'): string {
  const [day, time = '00:00'] = local.split('T');
  const [year, month, date] = day.split('-').map(Number);
  const [hour, minute] = time.split(':').map(Number);
  const wall = Date.UTC(year, month - 1, date, hour, minute);
  const offsetAt = (instant: number) => {
    const parts = new Intl.DateTimeFormat('en-US', {timeZone: timezone, hourCycle:'h23', year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit'}).formatToParts(new Date(instant));
    const get = (type: string) => Number(parts.find(part => part.type === type)?.value);
    return (Date.UTC(get('year'), get('month') - 1, get('day'), get('hour'), get('minute')) - instant) / 60000;
  };
  let offset = offsetAt(wall);
  offset = offsetAt(wall - offset * 60000);
  const sign = offset < 0 ? '-' : '+';
  const absolute = Math.abs(offset);
  return `${day}T${time.slice(0,5)}:00${sign}${String(Math.floor(absolute/60)).padStart(2,'0')}:${String(absolute%60).padStart(2,'0')}`;
}
/** Converte um instante ISO para "AAAA-MM-DDTHH:mm" no fuso da clínica (para campos datetime-local). */
export function isoToZoned(value: string, timezone = 'America/Sao_Paulo'): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const parts = new Intl.DateTimeFormat('en-CA', {timeZone: timezone, hourCycle:'h23', year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit'}).formatToParts(date);
  const get = (type: string) => parts.find(part => part.type === type)?.value ?? '';
  return `${get('year')}-${get('month')}-${get('day')}T${get('hour')}:${get('minute')}`;
}
