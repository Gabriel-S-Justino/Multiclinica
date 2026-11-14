import { useState, type FormEvent, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { api } from './api';
import { pt } from './locales';
import { Failure, Feedback, Icon, Label, Loading, PageHeader, formatInstant, useAction, useRemote } from './ui';
import type { IntegrationState, Membership, Page, Queue } from './types';

/** Cada "interpretação" da IA reserva até 4.096 tokens; o dono pensa em quantidade, não em tokens. */
const TOKENS_PER_INTERPRETATION = 4096;

function CopyValue({label, value}: {label: string; value: string}) {
  const [copied, setCopied] = useState(false);
  return <Label text={label}>
    <span className="copy-field">
      <input className="code-display" readOnly value={value} onFocus={event => event.target.select()}/>
      <button type="button" className="secondary" onClick={() => void navigator.clipboard.writeText(value).then(() => setCopied(true), () => setCopied(false))}>
        <Icon name={copied ? 'check' : 'copy'} size={16}/>{copied ? pt.copied : pt.copy}
      </button>
    </span>
  </Label>;
}

function Step({index, title, done, current, open = current, children}: {index: number; title: string; done: boolean; current: boolean; open?: boolean; children?: ReactNode}) {
  return <li className={`setup-step${done ? ' done' : ''}${current ? ' current' : ''}`} aria-current={current ? 'step' : undefined}>
    <div className="setup-step-head">
      <span className="step-index" aria-hidden="true">{done ? <Icon name="check" size={14}/> : index}</span>
      <h3>{title}</h3>
      <span className="visually-hidden">{done ? pt.stepDone : pt.stepPending}</span>
    </div>
    {open && children ? <div className="setup-step-body">{children}</div> : null}
  </li>;
}

function StatusBanner({tone, icon, title, children}: {tone: 'ok' | 'warn' | 'info'; icon: Parameters<typeof Icon>[0]['name']; title: string; children?: ReactNode}) {
  return <div className={`status-banner tone-${tone}`} role="status">
    <span className="status-banner-icon" aria-hidden="true"><Icon name={icon} size={20}/></span>
    <div><strong>{title}</strong>{children && <div className="muted">{children}</div>}</div>
  </div>;
}

function WhatsAppSetup({member, row, queues}: {member: Membership; row: IntegrationState; queues: Queue[]}) {
  const action = useAction(member);
  const activeQueues = queues.filter(item => item.active);
  const meta = row.metadata;
  const [values, setValues] = useState<Record<string, string>>(() => ({
    phone_number_id: meta.phone_number_id ?? '', account_id: meta.account_id ?? '', graph_version: meta.graph_version ?? '',
    queue_id: meta.queue_id ?? (activeQueues.length === 1 ? activeQueues[0].id : ''), access_token: '', app_secret: '',
  }));
  const set = (name: string, value: string) => setValues(old => ({...old, [name]: value}));
  const done = Object.fromEntries(row.steps.map(step => [step.code, step.done]));
  const current = row.steps.find(step => !step.done)?.code;
  const health = row.health;
  const linked = Boolean(row.channel_id);
  const locked = row.send_enabled;
  const [editing, setEditing] = useState(false);

  function saveAndVerify(event: FormEvent) {
    event.preventDefault();
    void action.run(async () => {
      const credentials = Object.fromEntries(Object.entries(values).filter(([, value]) => value.trim()).map(([key, value]) => [key, value.trim()]));
      await action.send('/integrations/whatsapp', {version: row.version, credentials}, 'PUT');
      await api('/integrations/whatsapp/verify', {});
    }, pt.whatsappVerified);
  }
  const verify = () => void action.run(() => api('/integrations/whatsapp/verify', {}), pt.whatsappVerified);
  const provision = () => void action.run(() => action.send('/integrations/whatsapp/channel', {version: row.version}), pt.provisionedChannel);
  const delivery = (enabled: boolean) => void action.run(() => action.send('/integrations/whatsapp/delivery', {enabled}), enabled ? pt.deliveryEnabled : pt.deliveryPaused);

  return <section className="panel integration-panel" aria-labelledby="integration-whatsapp">
    <div className="section-heading">
      <div className="integration-title"><span className="integration-icon" aria-hidden="true"><Icon name="chat" size={20}/></span>
        <div><h2 id="integration-whatsapp">{pt.whatsapp}</h2><p className="muted">{pt.whatsappIntro}</p></div></div>
      <span className={`badge ${row.send_enabled ? 'active' : linked ? 'status-pending' : 'inactive'}`}>{row.send_enabled ? pt.whatsappLive : linked ? pt.whatsappPaused : pt.notConfigured}</span>
    </div>
    {health && linked && (health.credentials_rejected
      ? <StatusBanner tone="warn" icon="alert" title={pt.credentialsRejected}>{pt.credentialsRejectedHint}</StatusBanner>
      : !health.worker_online
        ? <StatusBanner tone="warn" icon="alert" title={pt.workerOffline}>{pt.workerOfflineHint}</StatusBanner>
        : row.send_enabled
          ? <StatusBanner tone="ok" icon="check" title={pt.whatsappHealthy}>{health.last_event_at ? `${pt.lastMessageReceived} ${formatInstant(health.last_event_at, member.timezone)}.` : pt.noMessagesYet}{health.failed_deliveries > 0 ? ` ${health.failed_deliveries} ${pt.failedDeliveries}` : ''}</StatusBanner>
          : null)}
    <Feedback action={action}/>
    <ol className="setup-steps">
      <Step index={1} title={pt.stepAccount} done={Boolean(done.fill_credentials && done.verify_credentials)}
        current={current === 'fill_credentials' || current === 'verify_credentials' || current === 'channel_mismatch'}
        open={editing || current === 'fill_credentials' || current === 'verify_credentials' || current === 'channel_mismatch'}>
        {locked ? <p className="note">{pt.pauseToEdit}</p> : <form className="form-grid" onSubmit={saveAndVerify}>
          <p className="wide muted">{pt.metaWhereToFind}</p>
          <Label text={pt.phoneNumberId} hint={pt.phoneNumberIdHint}><input inputMode="numeric" pattern="[0-9]{1,80}" required maxLength={80} value={values.phone_number_id} onChange={event => set('phone_number_id', event.target.value)}/></Label>
          <Label text={pt.accountId} hint={pt.accountIdHint}><input inputMode="numeric" pattern="[0-9]{1,80}" required maxLength={80} value={values.account_id} onChange={event => set('account_id', event.target.value)}/></Label>
          <Label text={pt.accessToken} hint={pt.accessTokenHint}><input type="password" autoComplete="new-password" minLength={12} maxLength={4096} required={!row.configured} placeholder={row.configured ? pt.keepCredential : ''} value={values.access_token} onChange={event => set('access_token', event.target.value)}/></Label>
          <Label text={pt.appSecret} hint={pt.appSecretHint}><input type="password" autoComplete="new-password" minLength={12} maxLength={4096} required={!row.configured} placeholder={row.configured ? pt.keepCredential : ''} value={values.app_secret} onChange={event => set('app_secret', event.target.value)}/></Label>
          {activeQueues.length === 0
            ? <p className="note wide"><Icon name="info" size={16}/><span>{pt.requireQueue} <Link to="/settings">{pt.settings}</Link></span></p>
            : <Label text={pt.defaultQueue} hint={pt.defaultQueueHint}><select required value={values.queue_id} onChange={event => set('queue_id', event.target.value)}><option value="">{pt.selectActiveQueue}</option>{activeQueues.map(queue => <option key={queue.id} value={queue.id}>{queue.name}</option>)}</select></Label>}
          <details className="advanced wide"><summary>{pt.advancedOptions}</summary>
            <Label text={pt.graphVersion} hint={pt.graphVersionHint}><input pattern="v[0-9]{1,3}\.0" maxLength={12} placeholder="v25.0" value={values.graph_version} onChange={event => set('graph_version', event.target.value)}/></Label>
          </details>
          <div className="form-actions wide">
            {editing && <button type="button" className="ghost" disabled={action.busy} onClick={() => setEditing(false)}>{pt.cancel}</button>}
            {row.configured && !done.verify_credentials && <button type="button" className="secondary" disabled={action.busy} onClick={verify}>{pt.verifyAgain}</button>}
            <button disabled={action.busy || activeQueues.length === 0}>{action.busy ? pt.loading : pt.saveAndVerify}</button>
          </div>
        </form>}
      </Step>
      <Step index={2} title={pt.stepLink} done={Boolean(done.provision_channel)} current={current === 'provision_channel'}>
        <p className="muted">{pt.linkHint}</p>
        <div className="form-actions"><button disabled={action.busy || !done.verify_credentials} onClick={provision}>{pt.provisionChannel}</button></div>
      </Step>
      <Step index={3} title={pt.stepWebhook} done={Boolean(done.verify_meta)} current={current === 'verify_meta'}>
        {row.webhook_url && meta.verify_token ? <>
          <p className="muted">{pt.webhookHint}</p>
          <CopyValue label={pt.webhookUrl} value={row.webhook_url}/>
          <CopyValue label={pt.verifyToken} value={meta.verify_token}/>
          <p className="field-hint">{pt.webhookWaiting}</p>
        </> : <p className="muted">{pt.webhookAfterLink}</p>}
      </Step>
      <Step index={4} title={pt.stepDelivery} done={Boolean(done.enable_delivery)} current={current === 'enable_delivery'}>
        <p className="muted">{pt.deliveryHint}</p>
        <div className="form-actions"><button disabled={action.busy || !done.verify_meta} onClick={() => delivery(true)}>{pt.enableDelivery}</button></div>
      </Step>
    </ol>
    <div className="form-actions">
      {done.verify_credentials && !editing && <button className="ghost" disabled={action.busy} onClick={() => setEditing(true)}>{pt.editConnection}</button>}
      {row.send_enabled && <button className="secondary" disabled={action.busy} onClick={() => delivery(false)}><Icon name="lock" size={16}/>{pt.pauseDelivery}</button>}
    </div>
  </section>;
}

function AISetup({member, row}: {member: Membership; row: IntegrationState}) {
  const action = useAction(member);
  const meta = row.metadata;
  const perMonth = Number(meta.monthly_tokens ?? 0) / TOKENS_PER_INTERPRETATION;
  const perPatient = Number(meta.conversation_tokens ?? 0) / TOKENS_PER_INTERPRETATION;
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState(meta.model ?? '');
  const [monthly, setMonthly] = useState(String(perMonth >= 1 ? Math.floor(perMonth) : 500));
  const [patient, setPatient] = useState(String(perPatient >= 1 ? Math.floor(perPatient) : 5));
  const [accepted, setAccepted] = useState(Boolean(meta.data_policy_reference && meta.contract_reference));
  const [policyRef, setPolicyRef] = useState(meta.data_policy_reference ?? '');
  const [contractRef, setContractRef] = useState(meta.contract_reference ?? '');
  const [enabled, setEnabled] = useState(meta.enabled === 'true');
  const [open, setOpen] = useState(row.configured);
  const [openedByUser, setOpenedByUser] = useState(false);
  const invalidLimits = Number(patient) < 1 || Number(monthly) < Number(patient);

  function save(event: FormEvent) {
    event.preventDefault();
    if (invalidLimits) return;
    const today = new Date().toLocaleDateString('pt-BR');
    const credentials: Record<string, string> = {
      provider: 'openai', model: model.trim(), enabled: String(enabled && accepted),
      monthly_tokens: String(Number(monthly) * TOKENS_PER_INTERPRETATION),
      conversation_tokens: String(Number(patient) * TOKENS_PER_INTERPRETATION),
    };
    if (apiKey.trim()) credentials.api_key = apiKey.trim();
    if (accepted) {
      credentials.data_policy_reference = policyRef.trim() || `${pt.policyAcceptedOn} ${today}`;
      credentials.contract_reference = contractRef.trim() || pt.openaiTerms;
    }
    void action.run(async () => {
      await action.send('/integrations/ai', {version: row.version, credentials}, 'PUT');
      await api('/integrations/ai/verify', {});
    }, pt.aiSaved);
  }

  return <section className="panel integration-panel" aria-labelledby="integration-ai">
    <div className="section-heading">
      <div className="integration-title"><span className="integration-icon" aria-hidden="true"><Icon name="settings" size={20}/></span>
        <div><h2 id="integration-ai">{pt.ai} <span className="optional-tag">{pt.optional}</span></h2><p className="muted">{pt.aiIntro}</p></div></div>
      <span className={`badge ${meta.enabled === 'true' ? 'active' : 'inactive'}`}>{meta.enabled === 'true' ? pt.aiOn : pt.aiOff}</span>
    </div>
    <Feedback action={action}/>
    {!open ? <button className="secondary" onClick={() => {setOpen(true); setOpenedByUser(true);}}><Icon name="plus" size={16}/>{pt.configureAi}</button> :
      <form className="form-grid" onSubmit={save}>
        <Label text={pt.apiKey} hint={pt.apiKeyHint}><input autoFocus={openedByUser} type="password" autoComplete="new-password" minLength={12} maxLength={4096} required={!row.configured} placeholder={row.configured ? pt.keepCredential : 'sk-...'} value={apiKey} onChange={event => setApiKey(event.target.value)}/></Label>
        <Label text={pt.aiModel} hint={pt.aiModelHint}><input required maxLength={120} pattern="[A-Za-z0-9._-]{1,120}" placeholder={pt.aiModelPlaceholder} value={model} onChange={event => setModel(event.target.value)}/></Label>
        <Label text={pt.monthlyInterpretations} hint={pt.monthlyInterpretationsHint}><input type="number" inputMode="numeric" min={1} max={200000} required value={monthly} onChange={event => setMonthly(event.target.value)}/></Label>
        <Label text={pt.patientInterpretations} hint={pt.patientInterpretationsHint}><input type="number" inputMode="numeric" min={1} max={1000} required value={patient} onChange={event => setPatient(event.target.value)}/></Label>
        {invalidLimits && <p className="feedback error wide" role="alert">{pt.aiLimitsInvalid}</p>}
        <label className="check wide"><input type="checkbox" checked={accepted} onChange={event => setAccepted(event.target.checked)}/><span>{pt.aiPolicyAccept}<small className="field-hint">{pt.aiPolicyAcceptHint}</small></span></label>
        {accepted && <details className="advanced wide"><summary>{pt.aiReferences}</summary>
          <div className="form-grid">
            <Label text={pt.dataPolicyReference}><input maxLength={254} placeholder={pt.optional} value={policyRef} onChange={event => setPolicyRef(event.target.value)}/></Label>
            <Label text={pt.contractReference}><input maxLength={254} placeholder={pt.optional} value={contractRef} onChange={event => setContractRef(event.target.value)}/></Label>
          </div>
        </details>}
        <label className="check wide"><input type="checkbox" checked={enabled} disabled={!accepted} onChange={event => setEnabled(event.target.checked)}/><span>{pt.aiEnable}</span></label>
        <div className="form-actions wide"><button disabled={action.busy || invalidLimits}>{action.busy ? pt.loading : pt.saveAndVerify}</button></div>
      </form>}
  </section>;
}

export function IntegrationPage({member}: {member: Membership}) {
  const queues = useRemote<Page<Queue>>(member, '/admin/queues');
  // Enquanto a Meta não confirma o webhook, a página se atualiza sozinha para refletir a etapa.
  const result = useRemote<Page<IntegrationState>>(member, '/integrations', {refetchInterval: 15_000});
  const whatsapp = result.data?.items.find(item => item.provider === 'whatsapp');
  const ai = result.data?.items.find(item => item.provider === 'ai');
  return <>
    <PageHeader title={pt.integrations} description={pt.integrationsDescription}/>
    <p className="note"><Icon name="lock" size={16}/><span>{pt.integrationHint}</span></p>
    {result.isPending || queues.isPending ? <Loading/> : result.isError ? <Failure error={result.error}/> : <>
      {whatsapp && <WhatsAppSetup key="whatsapp" member={member} row={whatsapp} queues={queues.data?.items ?? []}/>}
      {ai && <AISetup key="ai" member={member} row={ai}/>}
    </>}
  </>;
}
