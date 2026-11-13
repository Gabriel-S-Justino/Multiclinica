import { useState, type ReactNode } from 'react';
import { ActivationCode } from './AccountActivation';
import { api } from './api';
import { pt } from './locales';
import { ConfirmButton, Empty, Failure, Feedback, Icon, Label, Loading, Modal, PageHeader, Status, formatInstant, formatLongDay, isoToZoned, minutes, useAction, useRemote, zonedToIso } from './ui';
import type { Catalog, EntityReceipt, IntegrationState, Membership, Page, Queue, RecordData, SupportRequest } from './types';

type Option = {value:string; label:string};
export type Field = {name:string; label:string; type?:'text'|'number'|'checkbox'|'date'|'time'|'minutes'|'select'|'multi'|'datetime'; options?:Option[]; optional?:boolean; initial?:unknown; when?:{name:string; value:boolean}; group?:string; hint?:string};
type Values = Record<string, unknown>;

export const clinicRoles = ['collaborator','reception','admin'].map(value=>({value,label:pt.roles[value]}));

export function permissionFields(professionals?: Option[], queues?: Option[]): Field[] {
  return [
    {name:'role',label:pt.role,type:'select',options:clinicRoles},
    {name:'active',label:pt.active,type:'checkbox'},
    {name:'can_manage_schedule',label:pt.manageSchedule,type:'checkbox'},
    {name:'professional_ids',label:pt.assignedProfessionals,type:'multi',optional:true,options:professionals},
    {name:'queue_ids',label:pt.assignedQueues,type:'multi',optional:true,options:queues},
  ];
}

/** Formulário genérico de cadastro exibido em uma janela modal, com erros de validação no próprio contexto. */
export function Editor({title, fields, initial, busy, onSave, onCancel, action, timezone, intro}: {title:string; fields:Field[]; initial?:RecordData; busy:boolean; onSave:(values:RecordData)=>void; onCancel:()=>void; action?:ReturnType<typeof useAction>; timezone?:string; intro?:ReactNode}) {
  const [values,setValues] = useState<Values>(()=>Object.fromEntries(fields.map(field=>{
    const raw = initial?.[field.name] ?? field.initial ?? (field.type==='checkbox'?false:field.type==='multi'?[]:'');
    return [field.name, field.type==='datetime' && typeof raw==='string' && raw ? isoToZoned(raw,timezone) : raw];
  })));
  const visible = fields.filter(field=>!field.when || Boolean(values[field.when.name])===field.when.value);
  function submit() {
    const payload:RecordData = {version:typeof initial?.version==='number'?initial.version:0};
    for (const field of visible) {
      const value = values[field.name];
      if (field.type==='number' || (field.type==='select' && typeof field.initial==='number')) payload[field.name] = value==='' || value===null ? null : Number(value);
      else if (field.type==='minutes') {if(typeof value==='number') payload[field.name]=value; else {const [hours,mins] = String(value??'').split(':').map(Number); payload[field.name] = hours*60+mins;}}
      else if (field.type==='datetime') payload[field.name] = value ? zonedToIso(String(value),timezone) : null;
      else payload[field.name] = value==='' && field.optional ? null : value;
    }
    onSave(payload);
  }
  const set = (name:string, value:unknown) => setValues(old=>({...old,[name]:value}));
  function control(field:Field) {
    if (field.type==='checkbox') return <label className="check wide" key={field.name}><input type="checkbox" checked={Boolean(values[field.name])} onChange={event=>set(field.name,event.target.checked)}/><span>{field.label}{field.hint && <small className="field-hint">{field.hint}</small>}</span></label>;
    if (field.type==='multi') {
      const chosen = Array.isArray(values[field.name]) ? values[field.name] as string[] : [];
      return <fieldset className="choice-group wide" key={field.name}><legend>{field.label}</legend>
        {field.options?.length ? <div className="choice-list">{field.options.map(option=><label className="choice" key={option.value}><input type="checkbox" checked={chosen.includes(option.value)} onChange={event=>set(field.name,event.target.checked?[...chosen,option.value]:chosen.filter(item=>item!==option.value))}/><span>{option.label}</span></label>)}</div>
          : <p className="muted">{pt.selectAll}</p>}
      </fieldset>;
    }
    return <Label key={field.name} text={field.label} hint={field.hint}>
      {field.type==='select' ? <select required={!field.optional} value={String(values[field.name]??'')} onChange={event=>set(field.name,event.target.value)}>
        <option value="">{pt.select}</option>{field.options?.map(option=><option value={option.value} key={option.value}>{option.label}</option>)}</select> :
        <input name={field.name} type={field.type==='minutes'?'text':field.type==='datetime'?'datetime-local':field.type??'text'} inputMode={field.type==='number'||field.type==='minutes'?'numeric':undefined} min={field.type==='number'?0:undefined}
          pattern={field.type==='minutes'?'([01][0-9]|2[0-3]):[0-5][0-9]|24:00':undefined} placeholder={field.type==='minutes'?pt.hourFormat:undefined} required={!field.optional} maxLength={field.type==='text'||!field.type?254:undefined}
          value={field.type==='minutes' && typeof values[field.name]==='number'?minutes(values[field.name] as number):String(values[field.name]??'')} onChange={event=>set(field.name,event.target.value)}/>}
    </Label>;
  }
  const groups:{name?:string;fields:Field[]}[] = [];
  for (const field of visible) { const current = groups.at(-1); if (current && current.name===field.group) current.fields.push(field); else groups.push({name:field.group,fields:[field]}); }
  return <Modal title={title} onClose={()=>{if(!busy)onCancel();}} size={visible.length>8?'wide':undefined}>
    {action && <Feedback action={action} errorsOnly/>}{intro}
    <form className="editor-form" onSubmit={event=>{event.preventDefault();submit();}}>
      {groups.map((group,index)=><div className="form-group" key={`${group.name??''}:${index}`}>{group.name && <h3 className="group-title">{group.name}</h3>}<div className="form-grid">{group.fields.map(control)}</div></div>)}
      <div className="form-actions sticky-actions"><button type="button" className="secondary" disabled={busy} onClick={onCancel}>{pt.cancel}</button><button disabled={busy}>{busy?pt.loading:pt.save}</button></div>
    </form>
  </Modal>;
}

function Cards({rows, onEdit, label, children, icon = 'info'}: {rows:RecordData[]; onEdit:(row:RecordData)=>void; label:string; children?:(row:RecordData)=>ReactNode; icon?:Parameters<typeof Empty>[0]['icon']}) {
  if (!rows.length) return <Empty icon={icon}/>;
  return <div className="record-list">{rows.map(row=><article className={`record-card${row.active===false?' is-inactive':''}`} key={String(row.id)}><div className="record-main"><div className="record-title"><h3>{String(row[label]??row.id)}</h3>{typeof row.active==='boolean' && <span className={`badge ${row.active?'active':'inactive'}`}>{row.active?pt.active:pt.inactive}</span>}</div>{children?.(row)}</div><button className="secondary" onClick={()=>onEdit(row)}>{pt.edit}</button></article>)}</div>;
}

export function Services({member}: {member:Membership}) {
  const result = useRemote<Page<RecordData>>(member,'/services');
  const catalog = useRemote<Catalog>(member,'/portal/catalog');
  const queues = useRemote<Page<Queue>>(member,'/admin/queues');
  const action = useAction(member);
  const [editing,setEditing] = useState<RecordData|null>(null);
  const clinical = {name:'requires_professional',value:true};
  const fields:Field[] = [
    {name:'name',label:pt.name,group:pt.generalGroup},{name:'display_order',label:pt.displayOrder,type:'number',group:pt.generalGroup},
    {name:'service_queue_id',label:pt.serviceQueue,type:'select',optional:true,options:queues.data?.items.map(item=>({value:item.id,label:item.name})),group:pt.generalGroup},
    {name:'active',label:pt.active,type:'checkbox',group:pt.generalGroup},{name:'requires_professional',label:pt.requiresProfessional,type:'checkbox',initial:true,group:pt.generalGroup},
    ...([['duration_minutes',pt.duration],['step_minutes',pt.step],['buffer_before',pt.bufferBefore],['buffer_after',pt.bufferAfter],['min_notice_minutes',pt.minNotice],
      ['cancellation_notice_minutes',pt.cancelNotice],['reschedule_notice_minutes',pt.rescheduleNotice],['horizon_days',pt.horizon],['max_reschedules',pt.maxReschedules],['hold_ttl_minutes',pt.holdTtl]] as const).map(([name,label]):Field=>({name,label,type:'number',when:clinical,group:pt.rulesGroup})),
    {name:'required_resource_ids',label:pt.requiredResources,type:'multi',optional:true,options:catalog.data?.resources.map(item=>({value:item.id,label:item.name})),when:clinical,group:pt.rulesGroup},
    {name:'requires_birth_date',label:pt.requiresBirthDate,type:'checkbox',when:clinical,group:pt.confirmGroup},{name:'policy_validated',label:pt.policyValidated,type:'checkbox',when:clinical,group:pt.confirmGroup},
  ];
  return <><PageHeader title={pt.services} description={pt.servicesDescription}><button onClick={()=>{action.clearError();setEditing({});}}><Icon name="plus" size={16}/>{pt.newService}</button></PageHeader><Feedback action={action}/>
    {editing && <Editor key={String(editing.id??'new')} title={editing.id?`${pt.edit}: ${String(editing.name)}`:pt.newService} fields={fields} initial={editing} busy={action.busy} action={action} onCancel={()=>setEditing(null)} onSave={values=>void action.run(async()=>{
      await action.send<EntityReceipt>(editing.id?`/services/${editing.id}`:'/services',values,editing.id?'PATCH':'POST');setEditing(null);
    },pt.saved)}/>}
    {result.isPending ? <Loading/> : result.isError ? <Failure error={result.error}/> : <Cards icon="services" rows={result.data.items} label="name" onEdit={row=>{action.clearError();setEditing(row);}}>{row=><div className="record-meta">{row.display_order!==undefined && row.display_order!==null && <span>{pt.displayOrderShort}: {String(row.display_order)}</span>}{typeof row.duration_minutes==='number' && <span>{pt.durationShort}: {row.duration_minutes} {pt.minutesShort}</span>}{row.active===true && <ConfirmButton label={pt.deactivate} title={pt.deactivateTitle} message={pt.deactivateMessage} busy={action.busy} onConfirm={()=>action.run(()=>action.send(`/services/${row.id}`,{version:row.version},'DELETE'),pt.saved)}/>}</div>}</Cards>}
  </>;
}

export function Team({member}: {member:Membership}) {
  const professionals = useRemote<Page<RecordData>>(member,'/team/professionals');
  const [membershipCursor,setMembershipCursor] = useState('');
  const members = useRemote<Page<RecordData>>(member,`/team/memberships?cursor=${encodeURIComponent(membershipCursor)}`);
  const catalog = useRemote<Catalog>(member,'/portal/catalog');
  const queues = useRemote<Page<Queue>>(member,'/admin/queues');
  const action = useAction(member);
  const [editProfessional,setProfessional] = useState<RecordData|null>(null);
  const [editMember,setMember] = useState<RecordData|null>(null);
  const [invite,setInvite] = useState(false);
  const [activationCode, setActivationCode] = useState('');
  return <><PageHeader title={pt.team} description={pt.teamDescription}><button className="secondary" onClick={()=>{action.clearError();setInvite(true);}}>{pt.invite}</button><button onClick={()=>{action.clearError();setProfessional({});}}><Icon name="plus" size={16}/>{pt.newProfessional}</button></PageHeader><Feedback action={action}/>
    {invite && <Editor title={pt.invite} busy={action.busy} action={action} intro={<><p className="note">Clínica: {member.clinic_name}</p><p className="note">{pt.inviteHint}</p></>} fields={[{name:'login',label:pt.inviteLogin},{name:'role',label:pt.role,type:'select',options:clinicRoles}]} onCancel={()=>setInvite(false)} onSave={values=>void action.run(async()=>{
      const {version:ignored,...payload}=values;
      void ignored;
      const receipt=await action.send<{activation_code:string}>('/team/invitations',payload);
      setInvite(false);
      setActivationCode(receipt.activation_code);
    },pt.invitationRequested)}/>}
    {activationCode && <ActivationCode code={activationCode} onClose={()=>setActivationCode('')}/>}
    {editProfessional && <Editor key={String(editProfessional.id??'new')} title={editProfessional.id?`${pt.edit}: ${String(editProfessional.display_name)}`:pt.newProfessional} initial={editProfessional} busy={action.busy} action={action} fields={[
      {name:'display_name',label:pt.name},{name:'active',label:pt.active,type:'checkbox'},
      {name:'user_id',label:pt.portalAccount,type:'select',optional:true,options:members.data?.items.map(item=>({value:String(item.user_id),label:String(item.login)}))},
      {name:'service_ids',label:pt.enabledServices,type:'multi',optional:true,options:catalog.data?.services.map(item=>({value:item.id,label:item.name}))},
    ]} onCancel={()=>setProfessional(null)} onSave={values=>void action.run(async()=>{await action.send(editProfessional.id?`/team/professionals/${editProfessional.id}`:'/team/professionals',values,editProfessional.id?'PATCH':'POST');setProfessional(null);},pt.saved)}/>}
    <section className="panel"><div className="section-heading"><h2>{pt.professionals}</h2></div>{professionals.isPending?<Loading/>:professionals.isError?<Failure error={professionals.error}/>:<Cards icon="team" rows={professionals.data.items} label="display_name" onEdit={row=>{action.clearError();setProfessional(row);}}>{row=>Array.isArray(row.service_ids)&&row.service_ids.length>0?<p className="muted">{row.service_ids.map(id=>catalog.data?.services.find(item=>item.id===id)?.name).filter(Boolean).join(' · ')}</p>:null}</Cards>}</section>
    <section className="panel"><div className="section-heading"><h2>{pt.memberships}</h2></div>{members.isPending?<Loading/>:members.isError?<Failure error={members.error}/>:<Cards icon="user" rows={members.data.items} label="login" onEdit={row=>{action.clearError();setMember(row);}}>{row=><p className="muted">{pt.roles[String(row.role)]}</p>}</Cards>}</section>
    <div className="form-actions">
      {membershipCursor&&<button className="secondary" onClick={()=>setMembershipCursor('')}>Primeira página</button>}
      {members.data?.next_cursor&&<button className="secondary" onClick={()=>setMembershipCursor(members.data.next_cursor??'')}>Próxima página</button>}
    </div>
    {editMember && <Editor title={`${pt.permissions}: ${String(editMember.login)}`} initial={editMember} busy={action.busy} action={action}
      intro={<ConfirmButton label="Excluir vínculo" title="Excluir usuário da clínica"
        message="O usuário perderá o acesso a esta clínica. O histórico ficará preservado."
        busy={action.busy} onConfirm={()=>action.run(async()=>{
          await action.send(`/team/memberships/${editMember.id}`,{version:editMember.version},'DELETE');
          setMember(null);
        },'Vínculo excluído.')}/>}
      fields={permissionFields(
      professionals.data?.items.map(item=>({value:String(item.id),label:String(item.display_name)})),
      queues.data?.items.map(item=>({value:item.id,label:item.name})),
    )} onCancel={()=>setMember(null)} onSave={values=>void action.run(async()=>{await action.send(`/team/memberships/${editMember.id}`,values,'PATCH');setMember(null);},pt.saved)}/>}
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
      {name:'start_minute',label:pt.startTime,type:'minutes',when:{name:'closed',value:false}},{name:'end_minute',label:pt.endTime,type:'minutes',when:{name:'closed',value:false}}] : [...base,{name:'starts_at',label:pt.startsAt,type:'datetime',hint:pt.clinicTime},{name:'ends_at',label:pt.endsAt,type:'datetime',hint:pt.clinicTime}];
  const tz = catalog.data?.timezone ?? member.timezone;
  function describe(kind:string,row:RecordData) {
    if (kind==='schedule') return {title:pt.weekdays[Number(row.weekday)],detail:`${minutes(Number(row.start_minute))} a ${minutes(Number(row.end_minute))}`};
    if (kind==='exception') return {title:typeof row.day==='string'?formatLongDay(row.day):'',detail:row.closed===true?pt.closed:`${minutes(Number(row.start_minute))} a ${minutes(Number(row.end_minute))}`};
    return {title:formatInstant(String(row.starts_at),tz),detail:`${pt.until} ${formatInstant(String(row.ends_at),tz)}`};
  }
  return <><PageHeader title={pt.schedules} description={pt.schedulesDescription}/><Feedback action={action}/>
    <div className="panel filter-panel"><Label text={pt.professional}><select value={professional} onChange={event=>{setProfessional(event.target.value);setEditing(null);}}><option value="">{pt.select}</option>{catalog.data?.professionals.map(item=><option key={item.id} value={item.id}>{item.display_name}</option>)}</select></Label></div>
    {!professional && <Empty icon="clock">{pt.chooseProfessionalHint}</Empty>}
    {editing && <Editor key={`${editing.kind}:${editing.row.id??'new'}`} title={editing.row.id?`${pt.edit}: ${kinds.find(item=>item.kind===editing.kind)?.title}`:kinds.find(item=>item.kind===editing.kind)?.button ?? pt.schedules} fields={fields} initial={editing.row} busy={action.busy} action={action} timezone={tz} onCancel={()=>setEditing(null)} onSave={values=>void action.run(async()=>{
      const path=`/${paths[editing.kind]}${editing.row.id?`/${editing.row.id}`:''}`;await action.send(path,values,editing.row.id?'PATCH':'POST');setEditing(null);
    },pt.hoursSaved)}/>}
    {professional && (result.isPending?<Loading/>:result.isError?<Failure error={result.error}/>:kinds.map(item=><section className="panel" key={item.kind}><div className="section-heading"><h2>{item.title}</h2>{allowed && <button className="secondary" onClick={()=>{action.clearError();setEditing({kind:item.kind,row:{professional_id:professional}});}}><Icon name="plus" size={16}/>{item.button}</button>}</div>
      {!result.data?.[item.key].length?<Empty compact/>:<div className="record-list">{result.data[item.key].map(row=>{const text=describe(item.kind,row);return <article className="record-card" key={String(row.id)}><div className="record-main"><h3>{text.title}</h3><p className="muted">{text.detail}</p></div>{allowed && <div className="record-actions">{item.kind!=='block' && <button className="secondary" onClick={()=>{action.clearError();setEditing({kind:item.kind,row});}}>{pt.edit}</button>}<ConfirmButton label={pt.remove} title={pt.removeTitle} message={pt.removeMessage} busy={action.busy} onConfirm={()=>action.run(()=>action.send(`/${paths[item.kind]}/${row.id}`,{version:row.version},'DELETE'),pt.saved)}/></div>}</article>;})}</div>}
    </section>))}
  </>;
}

function QueueEditor({row,action,onCancel,onSave}: {row:Queue|null; action:ReturnType<typeof useAction>; onCancel:()=>void; onSave:(body:RecordData)=>void}) {
  const [name,setName]=useState(row?.name??''); const [kind,setKind]=useState(row?.kind??'general');
  const [active,setActive]=useState(row?.active??false); const [notice,setNotice]=useState(row?.outside_hours_notice??'');
  const [hours,setHours]=useState(row?.hours??[]);
  return <Modal title={row?`${pt.edit}: ${row.name}`:pt.newQueue} size="wide" onClose={()=>{if(!action.busy)onCancel();}}><Feedback action={action} errorsOnly/><form className="editor-form" onSubmit={event=>{event.preventDefault();onSave({version:row?.version??0,name,kind,active,outside_hours_notice:notice,hours});}}>
    <div className="form-grid"><Label text={pt.name}><input required maxLength={120} value={name} onChange={event=>setName(event.target.value)}/></Label><Label text={pt.queueKind}><select value={kind} onChange={event=>setKind(event.target.value)}>{Object.entries(pt.queueKinds).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></Label>
      <Label text={pt.outsideNotice}><textarea maxLength={300} required value={notice} onChange={event=>setNotice(event.target.value)}/></Label><label className="check"><input type="checkbox" checked={active} onChange={event=>setActive(event.target.checked)}/>{pt.active}</label></div>
    <fieldset className="hours-fieldset"><legend>{pt.queueHours}</legend>{!hours.length && <p className="muted">{pt.noHours}</p>}{hours.map((window,index)=><div key={index} className="hours-row">
      <Label text={pt.weekday}><select value={window.weekday} onChange={event=>setHours(hours.map((item,i)=>i===index?{...item,weekday:Number(event.target.value)}:item))}>{pt.weekdays.map((day,i)=><option key={day} value={i}>{day}</option>)}</select></Label>
      {(['start_minute','end_minute'] as const).map(field=><Label key={field} text={field==='start_minute'?pt.startTime:pt.endTime}><input type="text" inputMode="numeric" placeholder={pt.hourFormat} pattern="([01][0-9]|2[0-3]):[0-5][0-9]|24:00" required defaultValue={minutes(window[field])} onBlur={event=>{if(!event.target.validity.valid)return;const [hour,minute]=event.target.value.split(':').map(Number);setHours(hours.map((item,i)=>i===index?{...item,[field]:hour*60+minute}:item));}}/></Label>)}
      <button type="button" className="icon-button ghost danger" aria-label={`${pt.remove}: ${pt.weekdays[window.weekday]}`} onClick={()=>setHours(hours.filter((_,i)=>i!==index))}><Icon name="close"/></button>
    </div>)}<button type="button" className="secondary" disabled={hours.length>=21} onClick={()=>setHours([...hours,{weekday:0,start_minute:480,end_minute:1080}])}><Icon name="plus" size={16}/>{pt.addWindow}</button></fieldset>
    <div className="form-actions sticky-actions"><button type="button" className="secondary" disabled={action.busy} onClick={onCancel}>{pt.cancel}</button><button disabled={action.busy}>{action.busy?pt.loading:pt.save}</button></div>
  </form></Modal>;
}

export function Settings({member}: {member:Membership}) {
  const result=useRemote<{units:RecordData[];resources:RecordData[]}>(member,'/units');
  const policy=useRemote<{policy:RecordData|null}>(member,'/clinic-policy');
  const queues=useRemote<Page<Queue>>(member,'/admin/queues'); const action=useAction(member);
  const [editing,setEditing]=useState<{kind:'unit'|'resource'|'policy';row:RecordData}|null>(null);
  const [queue,setQueue]=useState<Queue|null|undefined>();
  const fields:Field[] = editing?.kind==='policy' ? [{name:'identity_policy_reference',label:pt.identityPolicyReference},{name:'verification_ttl_minutes',label:pt.verificationTtl,type:'number'},{name:'identity_policy_approved',label:pt.identityPolicyApproved,type:'checkbox'}] : [{name:'name',label:pt.name},{name:'active',label:pt.active,type:'checkbox'},...(editing?.kind==='resource'?[{name:'unit_id',label:pt.unit,type:'select' as const,options:result.data?.units.map(item=>({value:String(item.id),label:String(item.name)}))}]:[])];
  return <><PageHeader title={pt.settings} description={pt.settingsDescription}/><Feedback action={action}/>
    {editing && <Editor key={`${editing.kind}:${editing.row.id??'new'}`} title={editing.kind==='policy'?pt.identityPolicy:editing.row.id?`${pt.edit}: ${String(editing.row.name)}`:editing.kind==='unit'?pt.newUnit:pt.newResource} fields={fields} initial={editing.row} busy={action.busy} action={action} intro={editing.kind==='policy'?<p className="note">{pt.policyHint}</p>:undefined} onCancel={()=>setEditing(null)} onSave={body=>void action.run(async()=>{
      const path=editing.kind==='policy'?'/clinic-policy':`/${editing.kind==='unit'?'units':'resources'}${editing.row.id?`/${editing.row.id}`:''}`;
      await action.send(path,body,editing.kind==='policy'?'PUT':editing.row.id?'PATCH':'POST');setEditing(null);
    },pt.saved)}/>}
    {queue!==undefined && <QueueEditor key={queue?.id??'new'} row={queue} action={action} onCancel={()=>setQueue(undefined)} onSave={body=>void action.run(async()=>{await action.send(queue?`/admin/queues/${queue.id}`:'/admin/queues',body,queue?'PATCH':'POST');setQueue(undefined);},pt.saved)}/>}
    {result.isPending?<Loading/>:result.isError?<Failure error={result.error}/>:<div className="two-columns">{(['unit','resource'] as const).map(kind=><section className="panel" key={kind}><div className="section-heading"><h2>{kind==='unit'?pt.units:pt.resources}</h2><button className="secondary" onClick={()=>{action.clearError();setEditing({kind,row:{}});}}><Icon name="plus" size={16}/>{kind==='unit'?pt.newUnit:pt.newResource}</button></div><Cards icon="building" rows={kind==='unit'?result.data.units:result.data.resources} label="name" onEdit={row=>{action.clearError();setEditing({kind,row});}}>{row=>kind==='resource'?<p className="muted">{String(result.data.units.find(unit=>unit.id===row.unit_id)?.name??'')}</p>:null}</Cards></section>)}</div>}
    <section className="panel"><div className="section-heading"><h2>{pt.queues}</h2><button className="secondary" onClick={()=>{action.clearError();setQueue(null);}}><Icon name="plus" size={16}/>{pt.newQueue}</button></div>{queues.isPending?<Loading/>:queues.isError?<Failure error={queues.error}/>:<Cards icon="inbox" rows={queues.data.items as unknown as RecordData[]} label="name" onEdit={row=>{action.clearError();setQueue(queues.data.items.find(item=>item.id===row.id)??null);}}>{row=>{const item=queues.data.items.find(queueRow=>queueRow.id===row.id);return item?<p className="muted">{pt.queueKinds[item.kind]??item.kind} · {item.hours.length?item.hours.map(window=>`${pt.weekdays[window.weekday].slice(0,3)} ${minutes(window.start_minute)} a ${minutes(window.end_minute)}`).join(', '):pt.noHours}</p>:null;}}</Cards>}</section>
    <section className="panel"><div className="section-heading"><h2>{pt.identityPolicy}</h2><button className="secondary" onClick={()=>{action.clearError();setEditing({kind:'policy',row:policy.data?.policy??{}});}}>{pt.edit}</button></div>
      {policy.isPending?<Loading/>:policy.data?.policy?<div className="record-card"><div className="record-main"><div className="record-title"><h3>{String(policy.data.policy.identity_policy_reference)}</h3><span className={`badge ${policy.data.policy.identity_policy_approved?'active':'status-pending'}`}>{policy.data.policy.identity_policy_approved?pt.approved:pt.pendingApproval}</span></div>{typeof policy.data.policy.verification_ttl_minutes==='number'&&<p className="muted">{pt.verificationTtl}: {policy.data.policy.verification_ttl_minutes}</p>}</div></div>:<p className="muted">{pt.noPolicy} {pt.policyHint}</p>}</section>
  </>;
}

function CredentialForm({member,row,queues}: {member:Membership;row:IntegrationState;queues:Queue[]}) {
  const action=useAction(member);
  const [values,setValues]=useState<Record<string,string>>({...(row.provider==='ai'?{provider:'openai'}:{}),...row.metadata});
  const [verification,setVerification]=useState('');
  const whatsapp=row.provider==='whatsapp';
  const secrets=whatsapp
    ? [['access_token',pt.accessToken],['app_secret',pt.appSecret],['verify_token',pt.verifyToken]]
    : [['api_key',pt.apiKey]];
  const set=(name:string,value:string)=>setValues(old=>({...old,[name]:value}));
  const activeQueues=queues.filter(item=>item.active);
  const readyForVerify=row.setup_complete;
  return <section className="panel" aria-labelledby={`integration-${row.provider}`}>
    <div className="section-heading"><div className="integration-title"><span className="integration-icon" aria-hidden="true"><Icon name={whatsapp?'chat':'settings'} size={20}/></span><div><h2 id={`integration-${row.provider}`}>{whatsapp?pt.whatsapp:pt.ai}</h2><p className="muted">{readyForVerify?pt.readyToVerify:pt.setupIncomplete}</p></div></div><span className={`badge ${row.configured?'active':'inactive'}`}>{row.configured?pt.configured:pt.notConfigured}</span></div>
    <Feedback action={action}/>{verification&&<p className="feedback success" role="status"><Icon name="check"/><span>{verification}</span></p>}
    <form className="form-grid" onSubmit={event=>{event.preventDefault();void action.run(async()=>{
      const credentials=Object.fromEntries(Object.entries(values).filter(([,v])=>v.trim().length>0));
      await action.send(`/integrations/${row.provider}`,{version:row.version,credentials},'PUT');
      setValues(Object.fromEntries(Object.entries(values).filter(([key])=>!['access_token','app_secret','verify_token','api_key'].includes(key))));
      setVerification('');
    },pt.saved);}}>
      {whatsapp?<><Label text={pt.phoneNumberId}><input inputMode="numeric" pattern="[0-9]{1,80}" required maxLength={80} value={values.phone_number_id??''} onChange={event=>set('phone_number_id',event.target.value)}/></Label>
        <Label text={pt.accountId}><input inputMode="numeric" pattern="[0-9]{1,80}" required maxLength={80} value={values.account_id??''} onChange={event=>set('account_id',event.target.value)}/></Label>
        <Label text={pt.graphVersion}><input pattern="v[0-9]{1,3}\.0" placeholder="v25.0" required maxLength={12} value={values.graph_version??''} onChange={event=>set('graph_version',event.target.value)}/></Label>
        <Label text={pt.defaultQueue}><select required value={values.queue_id??''} onChange={event=>set('queue_id',event.target.value)}><option value="">{pt.selectActiveQueue}</option>{activeQueues.map(queue=><option key={queue.id} value={queue.id}>{queue.name}</option>)}</select></Label>
        {activeQueues.length===0&&<p className="note wide">{pt.requireQueue}</p>}
      </>:<><Label text={pt.aiProvider}><select required value={values.provider??'openai'} onChange={event=>set('provider',event.target.value)}><option value="openai">OpenAI API</option></select></Label>
        <Label text={pt.aiModel}><input required minLength={1} maxLength={120} pattern="[A-Za-z0-9._-]{1,120}" placeholder={pt.aiModelPlaceholder} value={values.model??''} onChange={event=>set('model',event.target.value)}/></Label>
        <Label text="Referência da política de dados aprovada"><input required={values.enabled==='true'} maxLength={254} value={values.data_policy_reference??''} onChange={event=>set('data_policy_reference',event.target.value)}/></Label>
        <Label text="Referência do contrato com o provedor"><input required={values.enabled==='true'} maxLength={254} value={values.contract_reference??''} onChange={event=>set('contract_reference',event.target.value)}/></Label>
        <Label text="Limite mensal de tokens"><input type="number" min={4096} max={1000000000} required={values.enabled==='true'} value={values.monthly_tokens??''} onChange={event=>set('monthly_tokens',event.target.value)}/></Label>
        <Label text="Limite de tokens por conversa"><input type="number" min={4096} max={1000000000} required={values.enabled==='true'} value={values.conversation_tokens??''} onChange={event=>set('conversation_tokens',event.target.value)}/></Label>
        <label className="check wide"><input type="checkbox" checked={values.enabled==='true'} onChange={event=>set('enabled',String(event.target.checked))}/>Usar IA para interpretar opções do menu</label></>}
      {secrets.map(([name,label])=><Label key={name} text={label}><input type="password" autoComplete="new-password" minLength={12} maxLength={4096} required={!row.configured} placeholder={row.configured?pt.keepCredential:''} value={values[name]??''} onChange={event=>set(name,event.target.value)}/></Label>)}
      <div className="form-actions wide"><button type="submit" disabled={action.busy||whatsapp&&activeQueues.length===0}>{pt.saveCredentials}</button><button type="button" className="secondary" disabled={action.busy||!readyForVerify} onClick={()=>void action.run(async()=>{await api(`/integrations/${row.provider}/verify`,{});setVerification(pt.verifiedCredentials);})}>{pt.verifyConnection}</button>
        {whatsapp&&readyForVerify&&!row.channel_id&&<button type="button" disabled={action.busy||!verification} onClick={()=>void action.run(async()=>{await action.send('/integrations/whatsapp/channel',{version:row.version});setVerification('');},pt.provisionedChannel)}>{pt.provisionChannel}</button>}
      </div>
    </form>
    {whatsapp&&row.channel_id&&<dl className="review-grid"><dt>{pt.channel}</dt><dd><code>{row.channel_id}</code></dd><dt>{pt.delivery}</dt><dd>{row.send_enabled?pt.enabled:pt.disabled}</dd>{row.webhook_url&&<><dt>{pt.metaWebhook}</dt><dd><code>{row.webhook_url}</code></dd></>}</dl>}
    {whatsapp&&!row.channel_id&&row.webhook_url&&<p><strong>{pt.metaWebhook}:</strong> <code>{row.webhook_url}</code></p>}
    <div className="integration-checklist"><h3>{pt.pendingSteps}</h3>
      {row.pending_steps.length?<ol>{row.pending_steps.map(step=><li key={step}>{pt.integrationSteps[step as keyof typeof pt.integrationSteps]??step}</li>)}</ol>:<p className="muted">{pt.nothingPending}</p>}
    </div>
  </section>;
}
export function IntegrationPage({member}:{member:Membership}) {
  const result=useRemote<Page<IntegrationState>>(member,'/integrations');
  const queues=useRemote<Page<Queue>>(member,'/admin/queues');
  return <><PageHeader title={pt.integrations} description={pt.integrationsDescription}/><p className="note"><Icon name="lock" size={16}/>{pt.integrationHint}</p>
    {result.isPending?<Loading/>:result.isError?<Failure error={result.error}/>:result.data.items.map(row=><CredentialForm key={`${row.provider}:${row.version}`} member={member} row={row} queues={queues.data?.items??[]}/>)}
  </>;
}

export function Audit({member}:{member:Membership}) {
  const [cursor,setCursor]=useState<string>();
  const result=useRemote<Page<{id:string;action:string;resource_id:string|null;created_at:string;correlation_id:string}>>(member,`/audit?limit=25${cursor?`&cursor=${encodeURIComponent(cursor)}`:''}`);
  return <><PageHeader title={pt.audit} description={pt.auditDescription}/>{result.isPending?<Loading/>:result.isError?<Failure error={result.error}/>:<section className="panel"><div className="table-scroll" tabIndex={0} role="region" aria-label={pt.audit}><table><caption className="visually-hidden">{pt.audit}</caption><thead><tr><th>{pt.when}</th><th>{pt.action}</th><th>{pt.resource}</th><th>{pt.correlation}</th></tr></thead><tbody>{result.data.items.map(row=><tr key={row.id}><td className="nowrap">{formatInstant(row.created_at,member.timezone)}</td><td><code className="tag">{row.action}</code></td><td><code>{row.resource_id?.slice(0,8)??'Não informado'}</code></td><td><code>{row.correlation_id.slice(0,8)}</code></td></tr>)}</tbody></table></div>{!result.data.items.length&&<Empty icon="audit"/>}<div className="form-actions">{cursor&&<button className="secondary" onClick={()=>setCursor(undefined)}>{pt.firstPage}</button>}{result.data.next_cursor&&<button className="secondary" onClick={()=>setCursor(result.data.next_cursor??undefined)}>{pt.olderRecords}<Icon name="right" size={16}/></button>}</div></section>}</>;
}

export function SupportReviews({member}:{member:Membership}) {
  const result=useRemote<Page<SupportRequest>>(member,'/support-requests');const action=useAction(member);
  return <><PageHeader title={pt.supportRequests} description={pt.supportDescription}/><Feedback action={action}/>{result.isPending?<Loading/>:result.isError?<Failure error={result.error}/>:!result.data.items.length?<Empty icon="shield"/>:<div className="record-list">{result.data.items.map(row=><article className="panel" key={row.id}><div className="section-heading"><h2>{pt.appointmentId}: <code>{row.appointment_id.slice(0,8)}</code></h2><Status value={row.status}/></div><p>{row.reason}</p><p className="muted">{pt.durationShort}: {row.duration_minutes} {pt.minutesShort}{row.expires_at?` · ${pt.accessExpires}: ${formatInstant(row.expires_at,member.timezone)}`:''}</p><div className="form-actions">{(row.status==='pending'?['approve','reject']:row.status==='approved'?['revoke']:[]).map(decision=><button className={decision==='approve'?'':'secondary'} key={decision} disabled={action.busy} onClick={()=>void action.run(()=>action.send(`/support-requests/${row.id}/decision`,{version:row.version,decision}),pt.saved)}>{decision==='approve'?pt.approve:decision==='reject'?pt.reject:pt.revoke}</button>)}</div></article>)}</div>}</>;
}
