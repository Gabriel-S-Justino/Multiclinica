import { useState } from 'react';
import { api } from './api';
import { Failure, Feedback, Label, Loading, useAction, useRemote } from './ui';
import type { Membership, Page } from './types';

type Overview = {
  clinics: number;
  active_clinics: number;
  users: number;
  active_users: number;
  operators: number;
};
type AuditEvent = {
  id: string;
  created_at: string;
  scope: 'platform' | 'clinic';
  actor: string;
  actor_id: string;
  clinic: string | null;
  tenant_id: string | null;
  action: string;
  resource_id: string | null;
  correlation_id: string;
};
const metrics: [keyof Overview, string][] = [
  ['clinics', 'Clínicas cadastradas'],
  ['active_clinics', 'Clínicas ativas'],
  ['users', 'Usuários cadastrados'],
  ['active_users', 'Usuários ativos'],
  ['operators', 'Operadores da plataforma'],
];
const auditColumns: [keyof AuditEvent, string][] = [
  ['created_at', 'Data e hora'], ['scope', 'Origem'], ['clinic', 'Clínica'],
  ['action', 'Ação'], ['actor', 'Usuário'], ['actor_id', 'ID do usuário'],
  ['tenant_id', 'ID da clínica'], ['resource_id', 'Recurso'], ['correlation_id', 'Correlação'],
  ['id', 'ID do evento'],
];

function downloadCsv(filename: string, rows: (string | number | null)[][]) {
  const content = rows.map(row => row.map(value => {
    const raw = String(value ?? '');
    const safe = /^[\s]*[=+@-]|^[\t\r\n]/.test(raw) ? `'${raw}` : raw;
    return `"${safe.replaceAll('"', '""')}"`;
  }).join(';')).join('\r\n');
  const url = URL.createObjectURL(new Blob(['\ufeff', content], {type: 'text/csv;charset=utf-8'}));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function PlatformOverview({member}: {member: Membership}) {
  const result = useRemote<Overview>(member, '/platform/overview');
  if (result.isPending) return <Loading/>;
  if (result.isError) return <Failure error={result.error}/>;
  const values = result.data;
  return <>
    <div className="platform-metrics">
      {metrics.map(([key,label]) => <section className="panel" key={key}>
        <h2>{label}</h2><strong>{values[key]}</strong>
      </section>)}
    </div>
    <button className="secondary" onClick={() => downloadCsv('indicadores-da-plataforma.csv',
      [['Indicador', 'Total'], ...metrics.map(([key,label]) => [label, values[key]])])}>Exportar indicadores</button>
  </>;
}

export function PlatformAuditReport({member}: {member: Membership}) {
  const [filters, setFilters] = useState('');
  const [cursor, setCursor] = useState('');
  const action = useAction();
  const result = useRemote<Page<AuditEvent>>(member, `/platform/audit?${filters}&cursor=${encodeURIComponent(cursor)}`);

  async function exportReport() {
    const rows: (string | number | null)[][] = [auditColumns.map(([,label]) => label)];
    let next = '';
    do {
      const page: Page<AuditEvent> = await api(`/platform/audit?${filters}&limit=500&cursor=${encodeURIComponent(next)}`);
      rows.push(...page.items.map(event => auditColumns.map(([key]) => event[key])));
      next = page.next_cursor ?? '';
    } while (next);
    downloadCsv('auditoria-da-plataforma.csv', rows);
  }

  return <>
    <form className="panel form-grid" onSubmit={event => {
      event.preventDefault();
      const params = new URLSearchParams();
      for (const [key, value] of new FormData(event.currentTarget)) {
        if (typeof value === 'string' && value.trim()) params.set(key, value.trim());
      }
      setCursor('');
      setFilters(params.toString());
    }}>
      <Label text="De"><input name="start" type="date"/></Label>
      <Label text="Até"><input name="end" type="date"/></Label>
      <Label text="Ação"><input name="action" maxLength={80}/></Label>
      <Label text="Origem"><select name="scope"><option value="">Todas</option><option value="platform">Plataforma</option><option value="clinic">Clínicas</option></select></Label>
      <Label text="ID da clínica"><input name="clinic" maxLength={36}/></Label>
      <div className="form-actions wide">
        <button>Filtrar</button>
        <button type="button" className="secondary" disabled={action.busy} onClick={() => void action.run(exportReport)}>Exportar CSV</button>
      </div>
    </form>
    <Feedback action={action}/>
    {result.isPending ? <Loading/> : result.isError ? <Failure error={result.error}/> :
      <div className="table-scroll" tabIndex={0} role="region" aria-label="Eventos de auditoria">
        <table><thead><tr>{auditColumns.map(([,label]) => <th key={label}>{label}</th>)}</tr></thead>
          <tbody>{result.data.items.map(event => <tr key={`${event.scope}:${event.id}`}>
            {auditColumns.map(([key]) => <td key={key}>{key==='created_at'
              ? new Date(event.created_at).toLocaleString('pt-BR', {timeZone:'America/Fortaleza'})
              : key==='scope' ? (event.scope==='platform'?'Plataforma':'Clínica') : event[key]}</td>)}
          </tr>)}</tbody>
        </table>
        {!result.data.items.length&&<p>Nenhum evento encontrado.</p>}
      </div>}
    <div className="form-actions">
      {cursor&&<button className="secondary" onClick={() => setCursor('')}>Primeira página</button>}
      {result.data?.next_cursor&&<button className="secondary" onClick={() => setCursor(result.data.next_cursor??'')}>Próxima página</button>}
    </div>
  </>;
}
