import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from './api';
import { Empty, Failure, Feedback, Icon, Label, Loading, formatInstant, useAction, useRemote, type IconName } from './ui';
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

const auditTimezone = 'America/Fortaleza';

function count(value: number, singular: string, plural: string) {
  return `${value} ${value === 1 ? singular : plural}`;
}

function percent(part: number, total: number) {
  return total ? Math.round(part / total * 100) : 0;
}

export function PlatformOverview({member}: {member: Membership}) {
  const result = useRemote<Overview>(member, '/platform/overview');
  if (result.isPending) return <Loading/>;
  if (result.isError) return <Failure error={result.error}/>;
  const values = result.data;
  const tiles: {icon: IconName; label: string; value: number; detail: string; ratio?: number; to: string}[] = [
    {icon:'building', label:'Clínicas', value:values.clinics, detail:`${count(values.active_clinics,'ativa','ativas')} · ${count(values.clinics - values.active_clinics,'inativa','inativas')}`, ratio:percent(values.active_clinics, values.clinics), to:'/admin/clinics'},
    {icon:'team', label:'Usuários', value:values.users, detail:`${count(values.active_users,'ativo','ativos')} · ${count(values.users - values.active_users,'inativo','inativos')}`, ratio:percent(values.active_users, values.users), to:'/admin/users'},
    {icon:'shield', label:'Operadores da plataforma', value:values.operators, detail:'Contas com acesso à administração global', to:'/admin/users'},
  ];
  return <>
    <div className="section-heading"><h2>Indicadores</h2>
      <button className="secondary" onClick={() => downloadCsv('indicadores-da-plataforma.csv',
        [['Indicador', 'Total'], ...metrics.map(([key,label]) => [label, values[key]])])}><Icon name="download" size={16}/>Exportar indicadores</button></div>
    <div className="platform-metrics">
      {tiles.map(tile => <Link className="panel metric-tile" to={tile.to} key={tile.label}>
        <span className="metric-icon" aria-hidden="true"><Icon name={tile.icon} size={20}/></span>
        <span className="metric-label">{tile.label}</span>
        <strong>{tile.value}</strong>
        <span className="metric-detail">{tile.detail}</span>
        {tile.ratio !== undefined && <span className="metric-bar" aria-hidden="true"><span className={`metric-fill fill-${Math.round(tile.ratio / 10)}`}/></span>}
      </Link>)}
    </div>
    <h2 className="overview-subtitle">Tarefas frequentes</h2>
    <div className="quick-links">
      <Link className="panel quick-link" to="/admin/clinics"><Icon name="plus" size={18}/><span><strong>Cadastrar ou editar clínicas</strong><small>Dados, convites e permissões da equipe</small></span><Icon name="arrowRight" size={18}/></Link>
      <Link className="panel quick-link" to="/admin/users"><Icon name="search" size={18}/><span><strong>Encontrar um usuário</strong><small>Busque por nome, e-mail ou instituição</small></span><Icon name="arrowRight" size={18}/></Link>
      <Link className="panel quick-link" to="/admin/audit"><Icon name="audit" size={18}/><span><strong>Consultar auditoria</strong><small>Filtre e exporte eventos em CSV</small></span><Icon name="arrowRight" size={18}/></Link>
    </div>
  </>;
}

export function PlatformAuditReport({member}: {member: Membership}) {
  const [filters, setFilters] = useState('');
  const [cursor, setCursor] = useState('');
  const action = useAction();
  const result = useRemote<Page<AuditEvent>>(member, `/platform/audit?${filters}&cursor=${encodeURIComponent(cursor)}`);
  const clinics = useRemote<Page<{id: string; name: string}>>(member, '/platform/tenants?limit=50');

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
    <form className="panel audit-filters" aria-label="Filtros da auditoria" onSubmit={event => {
      event.preventDefault();
      const params = new URLSearchParams();
      for (const [key, value] of new FormData(event.currentTarget)) {
        if (typeof value === 'string' && value.trim()) params.set(key, value.trim());
      }
      setCursor('');
      setFilters(params.toString());
    }} onReset={() => { setCursor(''); setFilters(''); }}>
      <Label text="De"><input name="start" type="date"/></Label>
      <Label text="Até"><input name="end" type="date"/></Label>
      <Label text="Origem"><select name="scope"><option value="">Todas</option><option value="platform">Plataforma</option><option value="clinic">Clínicas</option></select></Label>
      <Label text="Clínica"><select name="clinic"><option value="">Todas</option>{clinics.data?.items.map(clinic => <option key={clinic.id} value={clinic.id}>{clinic.name}</option>)}</select></Label>
      <Label text="Ação"><input name="action" maxLength={80} placeholder="ex.: tenant.created"/></Label>
      <div className="form-actions audit-filter-actions">
        <button type="reset" className="ghost">Limpar</button>
        <button><Icon name="filter" size={16}/>Filtrar</button>
      </div>
    </form>
    <Feedback action={action}/>
    <section className="panel">
      <div className="section-heading"><h2>Eventos</h2>
        <button type="button" className="secondary" disabled={action.busy} onClick={() => void action.run(exportReport)}><Icon name="download" size={16}/>{action.busy ? 'Exportando…' : 'Exportar CSV'}</button></div>
      {result.isPending ? <Loading/> : result.isError ? <Failure error={result.error}/> : !result.data.items.length ? <Empty icon="audit">Nenhum evento encontrado para os filtros escolhidos.</Empty> :
        <div className="table-scroll" tabIndex={0} role="region" aria-label="Eventos de auditoria">
          <table className="audit-table"><thead><tr><th>Data e hora <small>(Fortaleza)</small></th><th>Origem</th><th>Ação</th><th>Usuário</th><th>Identificadores</th></tr></thead>
            <tbody>{result.data.items.map(event => <tr key={`${event.scope}:${event.id}`}>
              <td className="nowrap">{formatInstant(event.created_at, auditTimezone)}</td>
              <td><span className={`badge ${event.scope==='platform'?'status-scheduled':''}`}>{event.scope==='platform'?'Plataforma':'Clínica'}</span>{event.clinic&&<div className="muted cell-detail">{event.clinic}</div>}</td>
              <td><code className="tag">{event.action}</code></td>
              <td className="cell-wrap">{event.actor}</td>
              <td><details className="id-details"><summary>Ver</summary><dl>
                <dt>Evento</dt><dd><code>{event.id}</code></dd><dt>Usuário</dt><dd><code>{event.actor_id}</code></dd>
                {event.tenant_id&&<><dt>Clínica</dt><dd><code>{event.tenant_id}</code></dd></>}
                {event.resource_id&&<><dt>Recurso</dt><dd><code>{event.resource_id}</code></dd></>}
                <dt>Correlação</dt><dd><code>{event.correlation_id}</code></dd></dl></details></td>
            </tr>)}</tbody>
          </table>
        </div>}
      <div className="form-actions">
        {cursor&&<button className="secondary" onClick={() => setCursor('')}>Primeira página</button>}
        {result.data?.next_cursor&&<button className="secondary" onClick={() => setCursor(result.data.next_cursor??'')}>Próxima página<Icon name="right" size={16}/></button>}
      </div>
    </section>
  </>;
}
