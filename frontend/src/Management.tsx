import { useState, type ReactNode } from 'react';
import { pt } from './locales';
import { Empty, Failure, Feedback, Label, Loading, Modal, PageHeader, Status, minutes, useAction, useRemote } from './ui';
import type { Catalog, EntityReceipt, IntegrationState, Membership, Page, Queue, RecordData, SupportRequest } from './types';

type Option = {value:string; label:string};
export type Field = {name:string; label:string; type?:'text'|'number'|'checkbox'|'date'|'time'|'minutes'|'select'|'multi'; options?:Option[]; optional?:boolean; initial?:unknown; when?:{name:string; value:boolean}};
type Values = Record<string, unknown>;

export function Editor({title, fields, initial, busy, onSave, onCancel}: {title:string; fields:Field[]; initial?:RecordData; busy:boolean; onSave:(values:RecordData)=>void; onCancel:()=>void}) {
  const [values,setValues] = useState<Values>(()=>Object.fromEntries(fields.map(field=>[field.name,initial?.[field.name] ?? field.initial ?? (field.type==='checkbox'?false:field.type==='multi'?[]:'')])));
  const visible = fields.filter(field=>!field.when || Boolean(values[field.when.name])===field.when.value);
  function submit() {
    const payload:RecordData = {version:typeof initial?.version==='number'?initial.version:0};
    for (const field of visible) {
      const value = values[field.name];
      if (field.type==='number' || (field.type==='select' && typeof field.initial==='number')) payload[field.name] = value==='' || value===null ? null : Number(value);
      else if (field.type==='minutes') {if(typeof value==='number') payload[field.name]=value; else {const [hours,mins] = String(value??'').split(':').map(Number); payload[field.name] = hours*60+mins;}}
      else payload[field.name] = value==='' && field.optional ? null : value;
    }
    onSave(payload);
  }
  return <section className="editor-panel"><h3>{title}</h3><form className="form-grid" onSubmit={event=>{event.preventDefault();submit();}}>
    {visible.map(field=>field.type==='checkbox' ? <label className="check wide" key={field.name}><input type="checkbox" checked={Boolean(values[field.name])} onChange={event=>setValues({...values,[field.name]:event.target.checked})}/>{field.label}</label> : <Label key={field.name} text={field.label}>
      {field.type==='select' || field.type==='multi' ? <select multiple={field.type==='multi'} required={!field.optional} value={field.type==='multi' ? Array.isArray(values[field.name])?(values[field.name] as string[]):[] : String(values[field.name]??'')} onChange={event=>setValues({...values,[field.name]:field.type==='multi'?Array.from(event.target.selectedOptions).map(option=>option.value):event.target.value})}>
        {field.type!=='multi' && <option value="">{pt.select}</option>}{field.options?.map(option=><option value={option.value} key={option.value}>{option.label}</option>)}</select> :
        <input name={field.name} type={field.type==='minutes'?'text':field.type??'text'} pattern={field.type==='minutes'?'[0-2][0-9]:[0-5][0-9]':undefined} placeholder={field.type==='minutes'?pt.hourFormat:undefined} required={!field.optional} maxLength={field.type==='text'||!field.type?254:undefined} value={field.type==='minutes' && typeof values[field.name]==='number'?minutes(values[field.name] as number):String(values[field.name]??'')} onChange={event=>setValues({...values,[field.name]:event.target.value})}/>}
    </Label>)}
    <div className="form-actions wide"><button type="button" className="secondary" onClick={onCancel}>{pt.cancel}</button><button disabled={busy}>{busy?pt.loading:pt.save}</button></div>
  </form></section>;
}

function Cards({rows, onEdit, label, children}: {rows:RecordData[]; onEdit:(row:RecordData)=>void; label:string; children?:(row:RecordData)=>ReactNode}) {
  if (!rows.length) return <Empty/>;
  return <div className="record-list">{rows.map(row=><article className="record-card" key={String(row.id)}><div><h3>{String(row[label]??row.id)}</h3>{typeof row.active==='boolean' && <span className={`badge ${row.active?'active':'inactive'}`}>{row.active?pt.active:pt.deactivate}</span>}{children?.(row)}</div><button className="secondary" onClick={()=>onEdit(row)}>{pt.edit}</button></article>)}</div>;
}

export function Services({member}: {member:Membership}) {
  const result = useRemote<Page<RecordData>>(member,'/services');
  const catalog = useRemote<Catalog>(member,'/portal/catalog');
  const queues = useRemote<Page<Queue>>(member,'/admin/queues');
  const action = useAction(member);
  const [editing,setEditing] = useState<RecordData|null>(null);
  const clinical = {name:'requires_professional',value:true};
  const fields:Field[] = [
    {name:'name',label:pt.name},{name:'display_order',label:pt.displayOrder,type:'number'},
    {name:'active',label:pt.active,type:'checkbox'},{name:'requires_professional',label:pt.requiresProfessional,type:'checkbox',initial:true},
    {name:'service_queue_id',label:pt.serviceQueue,type:'select',optional:true,options:queues.data?.items.map(item=>({value:item.id,label:item.name}))},
    ...([['duration_minutes',pt.duration],['step_minutes',pt.step],['buffer_before',pt.bufferBefore],['buffer_after',pt.bufferAfter],['min_notice_minutes',pt.minNotice],
      ['cancellation_notice_minutes',pt.cancelNotice],['reschedule_notice_minutes',pt.rescheduleNotice],['horizon_days',pt.horizon],['max_reschedules',pt.maxReschedules],['hold_ttl_minutes',pt.holdTtl]] as const).map(([name,label]):Field=>({name,label,type:'number',when:clinical})),
    {name:'required_resource_ids',label:pt.requiredResources,type:'multi',optional:true,options:catalog.data?.resources.map(item=>({value:item.id,label:item.name})),when:clinical},
    {name:'requires_birth_date',label:pt.requiresBirthDate,type:'checkbox',when:clinical},{name:'policy_validated',label:pt.policyValidated,type:'checkbox',when:clinical},
  ];
  return <><PageHeader title={pt.services} description={pt.servicesDescription}><button onClick={()=>setEditing({})}>+ {pt.newService}</button></PageHeader><Feedback action={action}/>
    {editing && <Editor key={String(editing.id??'new')} title={pt.services} fields={fields} initial={editing} busy={action.busy} onCancel={()=>setEditing(null)} onSave={values=>void action.run(async()=>{
      await action.send<EntityReceipt>(editing.id?`/services/${editing.id}`:'/services',values,editing.id?'PATCH':'POST');setEditing(null);
    },pt.saved)}/>}
    {result.isPending ? <Loading/> : result.isError ? <Failure error={result.error}/> : <Cards rows={result.data.items} label="name" onEdit={setEditing}>{row=><div className="record-actions"><small>{String(row.display_order)}</small>{row.active===true && <button className="text-button danger" disabled={action.busy} onClick={()=>void action.run(()=>action.send(`/services/${row.id}`,{version:row.version},'DELETE'),pt.saved)}>{pt.deactivate}</button>}</div>}</Cards>}
  </>;
}

export function Team({member}: {member:Membership}) {
  const professionals = useRemote<Page<RecordData>>(member,'/team/professionals');
  const members = useRemote<Page<RecordData>>(member,'/team/memberships');
  const catalog = useRemote<Catalog>(member,'/portal/catalog');
  const queues = useRemote<Page<Queue>>(member,'/admin/queues');
  const action = useAction(member);
  const [editProfessional,setProfessional] = useState<RecordData|null>(null);
  const [editMember,setMember] = useState<RecordData|null>(null);
  const [invite,setInvite] = useState(false);
  const roles = Object.entries(pt.roles).filter(([key])=>key!=='superadmin').map(([value,label])=>({value,label}));
  return <><PageHeader title={pt.team} description={pt.teamDescription}><div className="form-actions"><button className="secondary" onClick={()=>setInvite(true)}>{pt.invite}</button><button onClick={()=>setProfessional({})}>+ {pt.newProfessional}</button></div></PageHeader><Feedback action={action}/>
    {invite && <Editor title={pt.invite} busy={action.busy} fields={[{name:'login',label:pt.inviteLogin},{name:'role',label:pt.role,type:'select',options:roles}]} onCancel={()=>setInvite(false)} onSave={values=>void action.run(async()=>{const {version:ignored,...payload}=values;void ignored;await action.send('/team/invitations',payload);setInvite(false);},pt.invitationRequested)}/>}
    {invite && <p className="note">{pt.inviteHint}</p>}
    {editProfessional && <Editor key={String(editProfessional.id??'new')} title={pt.newProfessional} initial={editProfessional} busy={action.busy} fields={[
      {name:'display_name',label:pt.name},{name:'active',label:pt.active,type:'checkbox'},
      {name:'user_id',label:pt.portalAccount,type:'select',optional:true,options:members.data?.items.map(item=>({value:String(item.user_id),label:String(item.login)}))},
      {name:'service_ids',label:pt.enabledServices,type:'multi',optional:true,options:catalog.data?.services.map(item=>({value:item.id,label:item.name}))},
    ]} onCancel={()=>setProfessional(null)} onSave={values=>void action.run(async()=>{await action.send(editProfessional.id?`/team/professionals/${editProfessional.id}`:'/team/professionals',values,editProfessional.id?'PATCH':'POST');setProfessional(null);},pt.saved)}/>}
    <section className="panel"><h2>{pt.professionals}</h2>{professionals.isPending?<Loading/>:professionals.isError?<Failure error={professionals.error}/>:<Cards rows={professionals.data.items} label="display_name" onEdit={setProfessional}/>}</section>
    <section className="panel"><h2>{pt.memberships}</h2>{members.isPending?<Loading/>:members.isError?<Failure error={members.error}/>:<Cards rows={members.data.items} label="login" onEdit={setMember}>{row=><p className="muted">{pt.roles[String(row.role)]}</p>}</Cards>}</section>
    {editMember && <Modal title={pt.permissions} onClose={()=>setMember(null)}><Editor title={String(editMember.login)} initial={editMember} busy={action.busy} fields={[
      {name:'role',label:pt.role,type:'select',options:roles},{name:'active',label:pt.active,type:'checkbox'},{name:'can_manage_schedule',label:pt.manageSchedule,type:'checkbox'},
      {name:'professional_ids',label:pt.assignedProfessionals,type:'multi',optional:true,options:professionals.data?.items.map(item=>({value:String(item.id),label:String(item.display_name)}))},
      {name:'queue_ids',label:pt.assignedQueues,type:'multi',optional:true,options:queues.data?.items.map(item=>({value:item.id,label:item.name}))},
    ]} onCancel={()=>setMember(null)} onSave={values=>void action.run(async()=>{await action.send(`/team/memberships/${editMember.id}`,values,'PATCH');setMember(null);},pt.saved)}/></Modal>}
  </>;
}

export function Schedules({member}: {member:Membership}) {
  const catalog = useRemote<Catalog>(member,'/portal/catalog');
  const [professional,setProfessional] = useState('');
  const [editing,setEditing] = useState<{kind:string;row:RecordData}|null>(null);
  const result = useRemote<{schedules:RecordData[];exceptions:RecordData[];blocks:RecordData[]}>(member,professional?`/schedules?professional_id=${professional}`:null);
  const action = useAction(member);
  const allowed = member.capabilities?.includes('schedules.manage');
  const base:Field[] = [{name:'professional_id',label:pt.professional,type:'select',initial:professional,options:catalog.data?.professionals.map(item=>({value:item.id,label:item.display_name}))},
    {name:'unit_id',label:pt.unit,type:'select',options:catalog.data?.units.map(item=>({value:item.id,label:item.name}))}];
  const paths:Record<string,string> = {schedule:'schedules',exception:'schedule-exceptions',block:'blocked-periods'};
  const kinds = [{kind:'schedule',key:'schedules' as const,title:pt.workingHours,button:pt.newSchedule},{kind:'exception',key:'exceptions' as const,title:pt.exceptions,button:pt.newException},{kind:'block',key:'blocks' as const,title:pt.blocks,button:pt.newBlock}];
  const fields:Field[] = !editing ? [] : editing.kind==='schedule' ? [...base,{name:'weekday',label:pt.weekday,type:'select',initial:0,options:pt.weekdays.map((label,index)=>({value:String(index),label}))},
    {name:'start_minute',label:pt.startTime,type:'minutes'},{name:'end_minute',label:pt.endTime,type:'minutes'},{name:'valid_from',label:pt.validFrom,type:'date'},{name:'valid_until',label:pt.validUntil,type:'date',optional:true}] : editing.kind==='exception' ? [...base,{name:'day',label:pt.date,type:'date'},{name:'closed',label:pt.closed,type:'checkbox',initial:true},
      {name:'start_minute',label:pt.startTime,type:'minutes',when:{name:'closed',value:false}},{name:'end_minute',label:pt.endTime,type:'minutes',when:{name:'closed',value:false}}] : [...base,{name:'starts_at',label:pt.startsAt},{name:'ends_at',label:pt.endsAt}];
  return <><PageHeader title={pt.schedules} description={pt.schedulesDescription}/><Feedback action={action}/>
    <div className="panel"><Label text={pt.professional}><select value={professional} onChange={event=>{setProfessional(event.target.value);setEditing(null);}}><option value="">{pt.select}</option>{catalog.data?.professionals.map(item=><option key={item.id} value={item.id}>{item.display_name}</option>)}</select></Label></div>
    {editing && <Editor key={`${editing.kind}:${editing.row.id??'new'}`} title={kinds.find(item=>item.kind===editing.kind)?.title ?? pt.schedules} fields={fields} initial={editing.row} busy={action.busy} onCancel={()=>setEditing(null)} onSave={values=>void action.run(async()=>{
      const path=`/${paths[editing.kind]}${editing.row.id?`/${editing.row.id}`:''}`;await action.send(path,values,editing.row.id?'PATCH':'POST');setEditing(null);
    },pt.hoursSaved)}/>}
    {professional && (result.isPending?<Loading/>:result.isError?<Failure error={result.error}/>:kinds.map(item=><section className="panel" key={item.kind}><div className="section-heading"><h2>{item.title}</h2>{allowed && <button className="secondary" onClick={()=>setEditing({kind:item.kind,row:{professional_id:professional}})}>{item.button}</button>}</div>
      {!result.data?.[item.key].length?<Empty/>:<div className="record-list">{result.data[item.key].map(row=><article className="record-card" key={String(row.id)}><div><strong>{item.kind==='schedule'?pt.weekdays[Number(row.weekday)]:String(row.day??'')}</strong><p>{item.kind==='block'?`${String(row.starts_at)} → ${String(row.ends_at)}`:row.closed===true?pt.closed:`${minutes(Number(row.start_minute))}–${minutes(Number(row.end_minute))}`}</p></div>{allowed && <div className="form-actions">{item.kind!=='block' && <button className="secondary" onClick={()=>setEditing({kind:item.kind,row})}>{pt.edit}</button>}<button className="text-button danger" disabled={action.busy} onClick={()=>void action.run(()=>action.send(`/${paths[item.kind]}/${row.id}`,{version:row.version},'DELETE'),pt.saved)}>{pt.remove}</button></div>}</article>)}</div>}
    </section>))}
  </>;
}

function QueueEditor({row,action,onCancel,onSave}: {row:Queue|null; action:ReturnType<typeof useAction>; onCancel:()=>void; onSave:(body:RecordData)=>void}) {
  const [name,setName]=useState(row?.name??''); const [kind,setKind]=useState(row?.kind??'general');
  const [active,setActive]=useState(row?.active??false); const [notice,setNotice]=useState(row?.outside_hours_notice??'');
  const [hours,setHours]=useState(row?.hours??[]);
  return <section className="editor-panel"><h3>{pt.queueHours}</h3><form onSubmit={event=>{event.preventDefault();onSave({version:row?.version??0,name,kind,active,outside_hours_notice:notice,hours});}}>
    <div className="form-grid"><Label text={pt.name}><input required maxLength={120} value={name} onChange={event=>setName(event.target.value)}/></Label><Label text={pt.queueKind}><select value={kind} onChange={event=>setKind(event.target.value)}>{Object.entries(pt.queueKinds).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></Label>
      <Label text={pt.outsideNotice}><textarea maxLength={300} required value={notice} onChange={event=>setNotice(event.target.value)}/></Label><label className="check"><input type="checkbox" checked={active} onChange={event=>setActive(event.target.checked)}/>{pt.active}</label></div>
    <fieldset><legend>{pt.queueHours}</legend>{hours.map((window,index)=><div key={index} className="hours-row">
      <Label text={pt.weekday}><select value={window.weekday} onChange={event=>setHours(hours.map((item,i)=>i===index?{...item,weekday:Number(event.target.value)}:item))}>{pt.weekdays.map((day,i)=><option key={day} value={i}>{day}</option>)}</select></Label>
      {(['start_minute','end_minute'] as const).map(field=><Label key={field} text={field==='start_minute'?pt.startTime:pt.endTime}><input type="text" inputMode="numeric" placeholder={pt.hourFormat} pattern="([01][0-9]|2[0-3]):[0-5][0-9]|24:00" required defaultValue={minutes(window[field])} onBlur={event=>{if(!event.target.validity.valid)return;const [hour,minute]=event.target.value.split(':').map(Number);setHours(hours.map((item,i)=>i===index?{...item,[field]:hour*60+minute}:item));}}/></Label>)}
      <button type="button" className="secondary" onClick={()=>setHours(hours.filter((_,i)=>i!==index))}>{pt.remove}</button>
    </div>)}<button type="button" className="secondary" disabled={hours.length>=21} onClick={()=>setHours([...hours,{weekday:0,start_minute:0,end_minute:0}])}>{pt.addWindow}</button></fieldset>
    <div className="form-actions"><button type="button" className="secondary" onClick={onCancel}>{pt.cancel}</button><button disabled={action.busy}>{pt.save}</button></div>
  </form></section>;
}

export function Settings({member}: {member:Membership}) {
  const result=useRemote<{units:RecordData[];resources:RecordData[]}>(member,'/units');
  const policy=useRemote<{policy:RecordData|null}>(member,'/clinic-policy');
  const queues=useRemote<Page<Queue>>(member,'/admin/queues'); const action=useAction(member);
  const [editing,setEditing]=useState<{kind:'unit'|'resource'|'policy';row:RecordData}|null>(null);
  const [queue,setQueue]=useState<Queue|null|undefined>();
  const fields:Field[] = editing?.kind==='policy' ? [{name:'identity_policy_reference',label:pt.identityPolicyReference},{name:'verification_ttl_minutes',label:pt.verificationTtl,type:'number'},{name:'identity_policy_approved',label:pt.identityPolicyApproved,type:'checkbox'}] : [{name:'name',label:pt.name},{name:'active',label:pt.active,type:'checkbox'},...(editing?.kind==='resource'?[{name:'unit_id',label:pt.unit,type:'select' as const,options:result.data?.units.map(item=>({value:String(item.id),label:String(item.name)}))}]:[])];
  return <><PageHeader title={pt.settings} description={pt.settingsDescription}/><Feedback action={action}/>
    {editing && <Editor key={`${editing.kind}:${editing.row.id??'new'}`} title={editing.kind==='policy'?pt.identityPolicy:editing.kind==='unit'?pt.unit:pt.resource} fields={fields} initial={editing.row} busy={action.busy} onCancel={()=>setEditing(null)} onSave={body=>void action.run(async()=>{
      const path=editing.kind==='policy'?'/clinic-policy':`/${editing.kind==='unit'?'units':'resources'}${editing.row.id?`/${editing.row.id}`:''}`;
      await action.send(path,body,editing.kind==='policy'?'PUT':editing.row.id?'PATCH':'POST');setEditing(null);
    },pt.saved)}/>}
    {queue!==undefined && <QueueEditor key={queue?.id??'new'} row={queue} action={action} onCancel={()=>setQueue(undefined)} onSave={body=>void action.run(async()=>{await action.send(queue?`/admin/queues/${queue.id}`:'/admin/queues',body,queue?'PATCH':'POST');setQueue(undefined);},pt.saved)}/>}
    {result.isPending?<Loading/>:result.isError?<Failure error={result.error}/>:<div className="two-columns">{(['unit','resource'] as const).map(kind=><section className="panel" key={kind}><div className="section-heading"><h2>{kind==='unit'?pt.units:pt.resources}</h2><button className="secondary" onClick={()=>setEditing({kind,row:{}})}>{kind==='unit'?pt.newUnit:pt.newResource}</button></div><Cards rows={kind==='unit'?result.data.units:result.data.resources} label="name" onEdit={row=>setEditing({kind,row})}/></section>)}</div>}
    <section className="panel"><div className="section-heading"><h2>{pt.queues}</h2><button className="secondary" onClick={()=>setQueue(null)}>{pt.newQueue}</button></div>{queues.isPending?<Loading/>:queues.isError?<Failure error={queues.error}/>:<Cards rows={queues.data.items as unknown as RecordData[]} label="name" onEdit={row=>setQueue(queues.data.items.find(item=>item.id===row.id)??null)}/>}</section>
    <section className="panel"><div className="section-heading"><h2>{pt.identityPolicy}</h2><button className="secondary" onClick={()=>setEditing({kind:'policy',row:policy.data?.policy??{}})}>{pt.edit}</button></div><p>{pt.policyHint}</p>{policy.data?.policy && <p className="muted">{String(policy.data.policy.identity_policy_reference)}</p>}</section>
  </>;
}

function CredentialForm({member,row}: {member:Membership;row:IntegrationState}) {
  const action=useAction(member);const [values,setValues]=useState<Record<string,string>>({});
  const fields=row.provider==='ai'?[['api_key',pt.apiKey]]:[['access_token',pt.accessToken],['app_secret',pt.appSecret],['verify_token',pt.verifyToken]];
  return <section className="panel"><h2>{row.provider==='ai'?pt.ai:pt.whatsapp}</h2><p><span className="badge">{row.configured?pt.configured:pt.notConfigured}</span> · {pt.notVerified}</p><Feedback action={action}/>
    <form className="form-grid" onSubmit={event=>{event.preventDefault();void action.run(async()=>{await action.send(`/integrations/${row.provider}`,{version:row.version,credentials:values},'PUT');setValues({});},pt.saved);}}>
      {fields.map(([name,label])=><Label key={name} text={label}><input type="password" autoComplete="new-password" maxLength={4096} required value={values[name]??''} onChange={event=>setValues({...values,[name]:event.target.value})}/></Label>)}<div className="wide"><button disabled={action.busy}>{pt.saveCredentials}</button></div>
    </form></section>;
}
export function IntegrationPage({member}:{member:Membership}) {
  const result=useRemote<Page<IntegrationState>>(member,'/integrations');
  return <><PageHeader title={pt.integrations} description={pt.integrationsDescription}/><p className="note">{pt.integrationHint}</p>{result.isPending?<Loading/>:result.isError?<Failure error={result.error}/>:result.data.items.map(row=><CredentialForm key={row.provider} member={member} row={row}/>)}</>;
}

export function Audit({member}:{member:Membership}) {
  const [cursor,setCursor]=useState<string>();
  const result=useRemote<Page<{id:string;action:string;resource_id:string|null;created_at:string;correlation_id:string}>>(member,`/audit?limit=25${cursor?`&cursor=${encodeURIComponent(cursor)}`:''}`);
  return <><PageHeader title={pt.audit} description={pt.auditDescription}/>{result.isPending?<Loading/>:result.isError?<Failure error={result.error}/>:<section className="panel table-scroll"><table><caption>{pt.audit}</caption><thead><tr><th>{pt.when}</th><th>{pt.action}</th><th>{pt.resource}</th><th>{pt.correlation}</th></tr></thead><tbody>{result.data.items.map(row=><tr key={row.id}><td>{new Date(row.created_at).toLocaleString('pt-BR',{timeZone:member.timezone})}</td><td>{row.action}</td><td><code>{row.resource_id?.slice(0,8)??'—'}</code></td><td><code>{row.correlation_id.slice(0,8)}</code></td></tr>)}</tbody></table>{!result.data.items.length&&<Empty/>}<div className="form-actions">{cursor&&<button className="secondary" onClick={()=>setCursor(undefined)}>{pt.back}</button>}{result.data.next_cursor&&<button onClick={()=>setCursor(result.data.next_cursor??undefined)}>{pt.following}</button>}</div></section>}</>;
}

export function SupportReviews({member}:{member:Membership}) {
  const result=useRemote<Page<SupportRequest>>(member,'/support-requests');const action=useAction(member);
  return <><PageHeader title={pt.supportRequests} description={pt.supportDescription}/><Feedback action={action}/>{result.isPending?<Loading/>:result.isError?<Failure error={result.error}/>:!result.data.items.length?<Empty/>:<div className="record-list">{result.data.items.map(row=><article className="panel" key={row.id}><div className="section-heading"><h2>{pt.appointmentId}: <code>{row.appointment_id.slice(0,8)}</code></h2><Status value={row.status}/></div><p>{row.reason}</p><p>{pt.duration}: {row.duration_minutes}</p><div className="form-actions">{(row.status==='pending'?['approve','reject']:row.status==='approved'?['revoke']:[]).map(decision=><button className={decision==='approve'?'':'secondary'} key={decision} disabled={action.busy} onClick={()=>void action.run(()=>action.send(`/support-requests/${row.id}/decision`,{version:row.version,decision}),pt.saved)}>{decision==='approve'?pt.approve:decision==='reject'?pt.reject:pt.revoke}</button>)}</div></article>)}</div>}</>;
}
