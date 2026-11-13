import { useState } from 'react';
import { ActivationCode } from './AccountActivation';
import { pt } from './locales';
import { clinicRoles, Editor, permissionFields, type Field } from './Management';
import { ConfirmButton, Empty, Failure, Feedback, Icon, Label, Loading, Modal, PageHeader, useAction, useRemote } from './ui';
import type { Membership, Page, RecordData } from './types';
import type { PersonalDetails } from './Profile';

type Clinic = {id:string;name:string;timezone:string;active:boolean;version:number;registration:RecordData|null};
type PlatformUser = {id:string;login:string;active:boolean;details:PersonalDetails|null;platform_operator:boolean};
const states = 'AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split(' ');
type PermissionsPage = Page<RecordData> & {
  professionals: {id:string;name:string}[];
  queues: {id:string;name:string}[];
};
const clinicFields: Field[] = [
  {name:'name',label:'Nome fantasia',group:'Identificação'},
  {name:'legal_name',label:'Razão social',group:'Identificação'},
  {name:'document',label:'CNPJ',group:'Identificação',hint:'14 dígitos, com ou sem pontuação'},
  {name:'responsible_name',label:'Responsável pela clínica',group:'Contato'},
  {name:'email',label:'E-mail institucional',group:'Contato'},
  {name:'phone',label:'Telefone institucional',group:'Contato'},
  {name:'postal_code',label:'CEP',group:'Endereço'},
  {name:'address',label:'Logradouro',group:'Endereço'},
  {name:'address_number',label:'Número',group:'Endereço'},
  {name:'complement',label:'Complemento',group:'Endereço',optional:true},
  {name:'neighborhood',label:'Bairro',group:'Endereço'},
  {name:'city',label:'Município',group:'Endereço'},
  {name:'state',label:'UF',group:'Endereço',type:'select',options:states.map(value=>({value,label:value}))},
  {name:'timezone',label:pt.timezone,group:'Configuração',initial:'America/Sao_Paulo'},
  {name:'active',label:pt.active,group:'Configuração',type:'checkbox',initial:true},
];

export function Platform({member}:{member:Membership}) {
  const action=useAction(member);
  const [tab,setTab]=useState<'clinics'|'users'>('clinics');
  const [editing,setEditing]=useState<Clinic|RecordData|null>(null);
  const [invite,setInvite]=useState<Clinic|null>(null);
  const [code,setCode]=useState('');
  const [clinicCursor,setClinicCursor]=useState('');
  const [userCursor,setUserCursor]=useState('');
  const [search,setSearch]=useState('');
  const [selected,setSelected]=useState<PlatformUser|null>(null);
  const [permissionsClinic,setPermissionsClinic]=useState<Clinic|null>(null);
  const tenants=useRemote<Page<Clinic>>(member,`/platform/tenants?limit=50&cursor=${encodeURIComponent(clinicCursor)}`);
  const users=useRemote<Page<PlatformUser>>(member,tab==='users'?`/platform/users?limit=50&search=${encodeURIComponent(search)}&cursor=${encodeURIComponent(userCursor)}`:null);

  function saveClinic(values:RecordData) {
    const {name,timezone,active,version,...registration}=values;
    void action.run(async()=>{
      const id=editing?.id;
      await action.send(id?`/platform/tenants/${id}`:'/platform/tenants',{name,timezone,active,version,registration},id?'PATCH':'POST');
      setEditing(null);
    },pt.saved);
  }

  return <>
    <PageHeader title="Administração da plataforma">
      {tab==='clinics'&&<button onClick={()=>{action.clearError();setEditing({});}}><Icon name="plus" size={16}/>{pt.newClinic}</button>}
    </PageHeader>
    <div className="form-actions platform-tabs">
      <button className={tab==='clinics'?'':'secondary'} aria-pressed={tab==='clinics'} onClick={()=>setTab('clinics')}>Clínicas</button>
      <button className={tab==='users'?'':'secondary'} aria-pressed={tab==='users'} onClick={()=>setTab('users')}>Usuários</button>
    </div>
    <Feedback action={action}/>
    {tab==='clinics' ? <>
      {tenants.isPending?<Loading/>:tenants.isError?<Failure error={tenants.error}/>:!tenants.data.items.length?<Empty icon="building"/>:
        <div className="record-list">{tenants.data.items.map(clinic=><article className="record-card" key={clinic.id}>
          <div className="record-main"><div className="record-title"><h2>{clinic.name}</h2><span className={`badge ${clinic.active?'active':'inactive'}`}>{clinic.active?pt.active:pt.inactive}</span></div>
          <p className="muted">{[clinic.registration?.document,clinic.registration?.city,clinic.registration?.state].filter(Boolean).join(' · ') || clinic.timezone}</p></div>
          <div className="record-actions">
            {clinic.active&&clinic.id!==member.tenant_id&&<button className="secondary" onClick={()=>{action.clearError();setInvite(clinic);}}>Convidar usuário</button>}
            {clinic.id!==member.tenant_id&&<button className="secondary" onClick={()=>setPermissionsClinic(clinic)}>{pt.permissions}</button>}
            <button className="secondary" onClick={()=>{action.clearError();setEditing(clinic);}}>{pt.edit}</button>
          </div>
        </article>)}</div>}
      <div className="form-actions">{clinicCursor&&<button className="secondary" onClick={()=>setClinicCursor('')}>Primeira página</button>}
      {tenants.data?.next_cursor&&<button className="secondary" onClick={()=>setClinicCursor(tenants.data.next_cursor??'')}>Próxima página</button>}</div>
    </>:<>
      <Label text="Buscar por nome ou login"><input type="search" maxLength={254} value={search} onChange={event=>{setSearch(event.target.value);setUserCursor('');}}/></Label>
      {users.isPending?<Loading/>:users.isError?<Failure error={users.error}/>:!users.data.items.length?<Empty icon="user"/>:
        <div className="record-list">{users.data.items.map(user=><article className="record-card" key={user.id}>
          <div className="record-main"><div className="record-title"><h2>{user.details?.full_name??user.login}</h2><span className={`badge ${user.active?'active':'inactive'}`}>{user.active?pt.active:pt.inactive}</span></div>
          {user.details&&<p className="muted">{user.login}</p>}</div>
          <button className="secondary" onClick={()=>{action.clearError();setSelected(user);}}>Ver cadastro</button>
        </article>)}</div>}
      <div className="form-actions">{userCursor&&<button className="secondary" onClick={()=>setUserCursor('')}>Primeira página</button>}
      {users.data?.next_cursor&&<button className="secondary" onClick={()=>setUserCursor(users.data.next_cursor??'')}>Próxima página</button>}</div>
    </>}
    {editing&&<Editor title={editing.id?pt.edit:pt.newClinic} initial={{...editing,...(editing.registration as RecordData|null)}} fields={clinicFields} busy={action.busy} action={action} onCancel={()=>setEditing(null)} onSave={saveClinic}/>}
    {invite&&<Editor title={`Convidar usuário · ${invite.name}`} fields={[{name:'login',label:pt.inviteLogin},{name:'role',label:pt.role,type:'select',options:clinicRoles}]}
      busy={action.busy} action={action} intro={<p className="note">{pt.inviteHint}</p>} onCancel={()=>setInvite(null)}
      onSave={({login,role})=>void action.run(async()=>{
        const result=await action.send<{activation_code:string}>(`/platform/tenants/${invite.id}/invitations`,{login,role});
        setInvite(null);setCode(result.activation_code);
      },pt.invitationRequested)}/>}
    {code&&<ActivationCode code={code} onClose={()=>setCode('')}/>}
    {permissionsClinic&&<ClinicPermissions clinic={permissionsClinic} member={member} onClose={()=>setPermissionsClinic(null)}/>}
    {selected&&<UserRecord user={selected} busy={action.busy} action={action} onClose={()=>setSelected(null)}
      onChange={()=>void action.run(async()=>{await action.send(`/platform/users/${selected.id}`,{active:!selected.active},'PATCH');setSelected(null);},pt.saved)}/>}
  </>;
}

function ClinicPermissions({clinic,member,onClose}:{clinic:Clinic;member:Membership;onClose:()=>void}) {
  const action=useAction(member);
  const [cursor,setCursor]=useState('');
  const [editing,setEditing]=useState<RecordData|null>(null);
  const path=`/platform/tenants/${clinic.id}/permissions`;
  const permissions=useRemote<PermissionsPage>(member,`${path}?cursor=${encodeURIComponent(cursor)}`);
  const page=permissions.data;
  if(editing&&page) return <Editor title={`${pt.permissions} · ${String(editing.login)}`} initial={editing}
    action={action} busy={action.busy} onCancel={()=>setEditing(null)}
    fields={permissionFields(
      page.professionals.map(item=>({value:item.id,label:item.name})),
      page.queues.map(item=>({value:item.id,label:item.name})),
    )}
    onSave={values=>void action.run(async()=>{
      await action.send(`${path}/${String(editing.id)}`,values,'PATCH');
      setEditing(null);
    },pt.saved)}/>;
  return <Modal title={`${pt.permissions} · ${clinic.name}`} onClose={onClose}>
    <Feedback action={action}/>
    {permissions.isPending?<Loading/>:permissions.isError?<Failure error={permissions.error}/>:
      !page?.items.length?<Empty icon="user"/>:<div className="record-list">
        {page.items.map(row=><article className="record-card" key={String(row.id)}>
          <div><h3>{String(row.login)}</h3><p className="muted">{pt.roles[String(row.role)]} · {row.active?pt.active:pt.inactive}</p></div>
          <button className="secondary" onClick={()=>{action.clearError();setEditing(row);}}>{pt.edit}</button>
        </article>)}
      </div>}
    <div className="form-actions">
      {cursor&&<button className="secondary" onClick={()=>setCursor('')}>Primeira página</button>}
      {page?.next_cursor&&<button className="secondary" onClick={()=>setCursor(page.next_cursor??'')}>Próxima página</button>}
    </div>
  </Modal>;
}

function UserRecord({user,busy,action,onClose,onChange}:{user:PlatformUser;busy:boolean;action:ReturnType<typeof useAction>;onClose:()=>void;onChange:()=>void}) {
  const details=user.details;
  return <Modal title={details?.full_name??user.login} onClose={onClose}>
    <Feedback action={action} errorsOnly/>
    <dl className="review-grid">
      <dt>Login</dt><dd>{user.login}</dd>
      <dt>E-mail de contato</dt><dd>{details?.email??'—'}</dd>
      <dt>Telefone</dt><dd>{details?.phone??'—'}</dd>
      <dt>Função</dt><dd>{details?.job_title??'—'}</dd>
      <dt>Registro profissional</dt><dd>{details?.professional_registration??'—'}</dd>
      <dt>Situação</dt><dd>{user.active?pt.active:pt.inactive}</dd>
    </dl>
    {!user.platform_operator&&<ConfirmButton label={user.active?'Desativar acesso':'Reativar acesso'} title={user.active?'Desativar acesso':'Reativar acesso'}
      message={user.active?'A conta perderá acesso a todas as clínicas.':'A conta voltará a acessar seus vínculos ativos.'}
      busy={busy} onConfirm={onChange}/>}
  </Modal>;
}
