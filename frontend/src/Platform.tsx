import { useState } from 'react';
import { ActivationCode } from './AccountActivation';
import { pt } from './locales';
import { clinicRoles, Editor, permissionFields, type Field } from './Management';
import { ConfirmButton, Empty, Failure, Feedback, Icon, Label, Loading, Modal, PageHeader, useAction, useRemote } from './ui';
import type { Membership, Page, RecordData } from './types';
import { ProfileFields, profileFields, profileJpeg, type PersonalDetails } from './Profile';
import { PlatformAuditReport, PlatformOverview } from './PlatformReports';

type Clinic = {id:string;name:string;timezone:string;active:boolean;version:number;registration:RecordData|null};
type UserAffiliation = {
  id:string;tenant_id:string;tenant_name:string;tenant_active:boolean;role:string;active:boolean;
};
type PlatformUser = {
  id:string;login:string;active:boolean;details:PersonalDetails|null;platform_operator:boolean;
  has_photo:boolean;memberships:UserAffiliation[];
};
type UserGroup = {
  name:string;
  users:{user:PlatformUser;affiliation?:UserAffiliation}[];
};

function groupUsers(users: PlatformUser[]) {
  const institutions = new Map<string, UserGroup>();
  const operators: UserGroup = {name:'Administração da plataforma', users:[]};
  const unassigned: UserGroup = {name:'Sem vínculo institucional', users:[]};
  for (const user of users) {
    if (user.platform_operator) operators.users.push({user});
    if (!user.platform_operator && !user.memberships.length) unassigned.users.push({user});
    for (const affiliation of user.memberships) {
      const group = institutions.get(affiliation.tenant_id) ?? {name:affiliation.tenant_name, users:[]};
      group.users.push({user, affiliation});
      institutions.set(affiliation.tenant_id, group);
    }
  }
  return [
    ...[...institutions.values()].sort((a,b)=>a.name.localeCompare(b.name,'pt-BR')),
    operators,
    unassigned,
  ].filter(group=>group.users.length);
}
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

export type PlatformSection = 'overview' | 'clinics' | 'users' | 'audit';

const sectionDescriptions: Record<PlatformSection,string> = {
  overview:'Acompanhe clínicas e usuários e acesse as tarefas mais comuns.',
  clinics:'Cadastre clínicas, convide usuários e ajuste as permissões de cada equipe.',
  users:'Gerencie contas, dados pessoais e vínculos com as clínicas.',
  audit:'Consulte e exporte os eventos registrados na plataforma e nas clínicas.',
};

function initialsOf(text:string) {
  return text.trim().split(/[\s@.]+/).filter(Boolean).slice(0,2).map(word=>Array.from(word)[0]).join('').toLocaleUpperCase('pt-BR');
}

export function UserAvatar({name,photo,size='sm'}:{name:string;photo?:string;size?:'sm'|'lg'}) {
  return <span className={`user-avatar user-avatar-${size}`} aria-hidden="true">{photo?<img src={photo} alt="" width={size==='lg'?72:40} height={size==='lg'?72:40}/>:initialsOf(name)}</span>;
}

export function Platform({member,userId,section,title}:{
  member:Membership;userId:string;section:PlatformSection;title:string;
}) {
  const action=useAction(member);
  const [editing,setEditing]=useState<Clinic|RecordData|null>(null);
  const [invite,setInvite]=useState<Clinic|null>(null);
  const [invitingSuperadmin,setInvitingSuperadmin]=useState(false);
  const [code,setCode]=useState('');
  const [clinicCursor,setClinicCursor]=useState('');
  const [userCursor,setUserCursor]=useState('');
  const [search,setSearch]=useState('');
  const [selectedId,setSelectedId]=useState<string|null>(null);
  const [permissionsClinic,setPermissionsClinic]=useState<Clinic|null>(null);
  const tenants=useRemote<Page<Clinic>>(member,section==='clinics'?`/platform/tenants?limit=50&cursor=${encodeURIComponent(clinicCursor)}`:null);
  const users=useRemote<Page<PlatformUser>>(member,section==='users'?`/platform/users?limit=50&search=${encodeURIComponent(search)}&cursor=${encodeURIComponent(userCursor)}`:null);
  const selected=users.data?.items.find(user=>user.id===selectedId);
  const editingClinic=editing&&typeof editing.id==='string'?editing as Clinic:null;

  function saveClinic(values:RecordData) {
    const {name,timezone,active,version,...registration}=values;
    void action.run(async()=>{
      const id=editing?.id;
      await action.send(id?`/platform/tenants/${id}`:'/platform/tenants',{name,timezone,active,version,registration},id?'PATCH':'POST');
      setEditing(null);
    },pt.saved);
  }

  return <>
    <PageHeader title={title} description={sectionDescriptions[section]}>
      {section==='clinics'&&<button onClick={()=>{action.clearError();setEditing({});}}><Icon name="plus" size={16}/>{pt.newClinic}</button>}
      {section==='users'&&<button onClick={()=>{action.clearError();setInvitingSuperadmin(true);}}><Icon name="plus" size={16}/>Cadastrar Superadmin</button>}
    </PageHeader>
    <Feedback action={action}/>
    {section==='overview'&&<PlatformOverview member={member}/>}
    {section==='audit'&&<PlatformAuditReport member={member}/>}
    {section==='clinics' && <>
      {tenants.isPending?<Loading/>:tenants.isError?<Failure error={tenants.error}/>:!tenants.data.items.length?<Empty icon="building">Nenhuma clínica cadastrada. Use “Nova clínica” para começar.</Empty>:
        <div className="record-list">{tenants.data.items.map(clinic=><article className={`record-card${clinic.active?'':' is-inactive'}`} key={clinic.id}>
          <span className="record-icon" aria-hidden="true"><Icon name="building" size={20}/></span>
          <div className="record-main"><div className="record-title"><h2>{clinic.name}</h2><span className={`badge ${clinic.active?'active':'inactive'}`}>{clinic.active?pt.active:pt.inactive}</span></div>
          <p className="muted">{[clinic.registration?.document,[clinic.registration?.city,clinic.registration?.state].filter(Boolean).join('/'),clinic.timezone].filter(Boolean).map(String).join(' · ')}</p></div>
          <div className="record-actions">
            {clinic.active&&<button className="secondary" onClick={()=>{action.clearError();setInvite(clinic);}}><Icon name="plus" size={16}/>Convidar usuário</button>}
            <button className="secondary" onClick={()=>setPermissionsClinic(clinic)}>{pt.permissions}</button>
            <button className="secondary" onClick={()=>{action.clearError();setEditing(clinic);}}>{pt.edit}</button>
          </div>
        </article>)}</div>}
      <div className="form-actions">{clinicCursor&&<button className="secondary" onClick={()=>setClinicCursor('')}>Primeira página</button>}
      {tenants.data?.next_cursor&&<button className="secondary" onClick={()=>setClinicCursor(tenants.data.next_cursor??'')}>Próxima página</button>}</div>
    </>}{section==='users'&&<>
      <div className="panel search-panel">
        <label className="search-field"><span className="visually-hidden">Buscar por nome, login, e-mail ou instituição</span><Icon name="search" size={18}/>
          <input type="search" placeholder="Buscar por nome, login, e-mail ou instituição" maxLength={254} value={search} onChange={event=>{setSearch(event.target.value);setUserCursor('');}}/></label>
        {users.data&&<span className="muted search-count">{users.data.items.length} {users.data.items.length===1?'usuário':'usuários'}{users.data.next_cursor?' nesta página':''}</span>}
      </div>
      {users.isPending?<Loading/>:users.isError?<Failure error={users.error}/>:!users.data.items.length?<Empty icon="user">{search?'Nenhum usuário encontrado para esta busca.':pt.noRecords}</Empty>:
        <div className="user-groups">{groupUsers(users.data.items).map(group=><section className="panel" key={group.users[0].affiliation?.tenant_id ?? group.name}>
          <div className="section-heading"><h2>{group.name}</h2><span className="badge">{group.users.length}</span></div>
          <div className="record-list">{group.users.map(({user,affiliation})=><article className={`record-card${user.active?'':' is-inactive'}`} key={user.id}>
            <UserAvatar name={user.details?.full_name??user.login} photo={user.has_photo?`/v1/platform/users/${user.id}/photo`:undefined}/>
            <div className="record-main"><div className="record-title"><h3>{user.details?.full_name??user.login}</h3>
              {!user.active&&<span className="badge inactive">{pt.inactive}</span>}
              {user.id===userId&&<span className="badge status-scheduled">Você</span>}
            </div>
            <p className="muted">{[user.details?user.login:null,affiliation?pt.roles[affiliation.role]:user.platform_operator?'Operador da plataforma':null,affiliation&&!affiliation.active?'Vínculo inativo':null,affiliation&&!affiliation.tenant_active?'Instituição inativa':null].filter(Boolean).join(' · ')}</p></div>
            <button className="secondary" onClick={()=>{action.clearError();setSelectedId(user.id);}}>Gerenciar cadastro</button>
          </article>)}</div>
        </section>)}</div>}
      <div className="form-actions">{userCursor&&<button className="secondary" onClick={()=>setUserCursor('')}>Primeira página</button>}
      {users.data?.next_cursor&&<button className="secondary" onClick={()=>setUserCursor(users.data.next_cursor??'')}>Próxima página</button>}</div>
    </>}
    {editing&&<Editor title={editingClinic?`${pt.edit}: ${editingClinic.name}`:pt.newClinic} initial={{...editing,...(editing.registration as RecordData|null)}} fields={clinicFields} busy={action.busy} action={action} onCancel={()=>setEditing(null)} onSave={saveClinic}
      danger={editingClinic&&<ConfirmButton label="Excluir clínica" title={`Excluir ${editingClinic.name}?`} message="A clínica e seus vínculos sairão da operação. O histórico ficará preservado."
        busy={action.busy} onConfirm={()=>action.run(async()=>{await action.send(`/platform/tenants/${editingClinic.id}`,{version:editingClinic.version},'DELETE');setEditing(null);},'Clínica excluída.')}/>}/>}
    {invite&&<Editor title={`Convidar usuário · ${invite.name}`} fields={[{name:'login',label:pt.inviteLogin},{name:'role',label:pt.role,type:'select',options:clinicRoles}]}
      busy={action.busy} action={action} intro={<p className="note">{pt.inviteHint}</p>} onCancel={()=>setInvite(null)}
      onSave={({login,role})=>void action.run(async()=>{
        const result=await action.send<{activation_code:string}>(`/platform/tenants/${invite.id}/invitations`,{login,role});
        setInvite(null);setCode(result.activation_code);
      },pt.invitationRequested)}/>}
    {invitingSuperadmin&&<Editor title="Cadastrar Superadmin" fields={[{name:'login',label:'E-mail do novo Superadmin',type:'email'}]}
      busy={action.busy} action={action} onCancel={()=>setInvitingSuperadmin(false)}
      intro={<p className="note">Use um e-mail ainda sem conta no portal. O convite expira em 24 horas. A pessoa convidada informa os dados pessoais, cria a senha e configura o autenticador ao ativar a conta.</p>}
      onSave={({login})=>void action.run(async()=>{
        const result=await action.send<{activation_code:string}>('/platform/operators/invitations',{login});
        setInvitingSuperadmin(false);
        setCode(result.activation_code);
      },pt.invitationRequested)}/>}
    {code&&<ActivationCode code={code} onClose={()=>setCode('')}
      hint={section==='users'?'Compartilhe o código em particular com o destinatário. Ele poderá ativar a conta na tela de login em até 24 horas.':undefined}/>}
    {permissionsClinic&&<ClinicPermissions clinic={permissionsClinic} member={member} onClose={()=>setPermissionsClinic(null)}/>}
    {selected&&<UserRecord key={selected.id} user={selected} member={member} ownAccount={selected.id===userId}
      onClose={()=>setSelectedId(null)}/>}
  </>;
}

function ClinicPermissions({clinic,member,onClose,membershipId}:{
  clinic:Pick<Clinic,'id'|'name'>;member:Membership;onClose:()=>void;membershipId?:string;
}) {
  const action=useAction(member);
  const [cursor,setCursor]=useState('');
  const [editing,setEditing]=useState<RecordData|null>(null);
  const path=`/platform/tenants/${clinic.id}/permissions`;
  const params=new URLSearchParams({cursor});
  if (membershipId) params.set('membership_id',membershipId);
  const permissions=useRemote<PermissionsPage>(member,`${path}?${params}`);
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
      !page?.items.length?<Empty icon="user">Nenhum usuário vinculado a esta clínica.</Empty>:<div className="record-list">
        {page.items.map(row=><article className="record-card" key={String(row.id)}>
          <div className="record-main"><div className="record-title"><h3>{String(row.login)}</h3>{row.active===false&&<span className="badge inactive">{pt.inactive}</span>}</div><p className="muted">{pt.roles[String(row.role)]}</p></div>
          <button className="secondary" onClick={()=>{action.clearError();setEditing(row);}}>{pt.edit}</button>
        </article>)}
      </div>}
    <div className="form-actions">
      {cursor&&<button className="secondary" onClick={()=>setCursor('')}>Primeira página</button>}
      {page?.next_cursor&&<button className="secondary" onClick={()=>setCursor(page.next_cursor??'')}>Próxima página</button>}
    </div>
  </Modal>;
}

function UserRecord({user,member,ownAccount,onClose}:{
  user:PlatformUser;member:Membership;ownAccount:boolean;onClose:()=>void;
}) {
  const action=useAction(member);
  const [affiliation,setAffiliation]=useState<UserAffiliation|null>(null);
  const [photoRevision,setPhotoRevision]=useState(0);
  const [editDetails,setEditDetails]=useState(Boolean(user.details));
  const path=`/platform/users/${user.id}`;
  async function savePhoto(file:File|null) {
    await action.run(async()=>{
      await action.send(`${path}/photo`,{jpeg:file?await profileJpeg(file):null},'PUT');
      setPhotoRevision(value=>value+1);
    },pt.saved);
  }
  if (affiliation) return <ClinicPermissions clinic={{id:affiliation.tenant_id,name:affiliation.tenant_name}}
    member={member} membershipId={affiliation.id} onClose={()=>setAffiliation(null)}/>;
  const name=user.details?.full_name??user.login;
  return <Modal title="Cadastro do usuário" onClose={onClose} size="wide">
    <Feedback action={action}/>
    <section className="user-record-head">
      <UserAvatar size="lg" name={name} photo={user.has_photo?`/v1${path}/photo?v=${photoRevision}`:undefined}/>
      <div className="user-record-id">
        <h3>{name}</h3>
        {user.details&&<p className="muted">{user.login}</p>}
        <div className="record-title"><span className={`badge ${user.active?'active':'inactive'}`}>{user.active?pt.active:pt.inactive}</span>{user.platform_operator&&<span className="badge status-scheduled">Operador da plataforma</span>}{ownAccount&&<span className="badge">Sua conta</span>}</div>
      </div>
      <div className="account-photo-actions">
        <label className="account-file">
          <input className="visually-hidden" type="file" accept="image/jpeg,image/png,image/webp" disabled={action.busy}
            onChange={event=>{const file=event.currentTarget.files?.[0];event.currentTarget.value='';if(file) void savePhoto(file);}}/>
          <span><Icon name="user" size={16}/>{user.has_photo?'Trocar foto':'Adicionar foto'}</span>
        </label>
        {user.has_photo&&<button type="button" className="ghost" disabled={action.busy} onClick={()=>void savePhoto(null)}>Remover foto</button>}
        <small className="field-hint">JPG, PNG ou WebP de até 10 MB</small>
      </div>
    </section>
    <section className="record-section">
      <h3 className="group-title">Dados da conta</h3>
      <form className="form-grid" onSubmit={event=>{
        event.preventDefault();
        const form=event.currentTarget;
        const login=String(new FormData(form).get('login')??'').trim();
        const details=editDetails?profileFields(form):null;
        void action.run(()=>action.send(`${path}/profile`,{login,details},'PATCH'),pt.saved);
      }}>
        <Label text={pt.login}><input name="login" required minLength={3} maxLength={254} defaultValue={user.login}/></Label>
        {editDetails?<ProfileFields initial={user.details} email={user.login.includes('@')?user.login:undefined}/>:
          <div className="inline-note wide"><p className="muted">Esta conta ainda não tem dados pessoais cadastrados.</p><button type="button" className="secondary" onClick={()=>setEditDetails(true)}>Preencher dados pessoais</button></div>}
        <div className="form-actions wide"><button disabled={action.busy}>{action.busy?pt.loading:pt.save}</button></div>
      </form>
    </section>
    <section className="record-section">
      <h3 className="group-title">Vínculos institucionais</h3>
      {user.memberships.length?<div className="record-list">{user.memberships.map(link=><div className={`record-card${link.active?'':' is-inactive'}`} key={link.id}>
        <span className="record-icon" aria-hidden="true"><Icon name="building" size={18}/></span>
        <div className="record-main"><div className="record-title"><strong>{link.tenant_name}</strong>{!link.active&&<span className="badge inactive">{pt.inactive}</span>}</div><p className="muted">{pt.roles[link.role]}{!link.tenant_active?' · Instituição inativa':''}</p></div>
        <button type="button" className="secondary" onClick={()=>setAffiliation(link)}>{pt.permissions}</button>
      </div>)}</div>:<p className="muted">{user.platform_operator?'Conta global da plataforma, sem vínculo com clínicas.':'Sem vínculo institucional.'}</p>}
    </section>
    {!ownAccount&&<section className="record-section danger-zone">
      <h3 className="group-title">Acesso à conta</h3>
      <p className="muted">{user.active?'Desativar impede o acesso a todas as clínicas sem apagar o histórico.':'Esta conta está desativada.'}</p>
      <div className="record-actions">
        {!user.platform_operator&&<ConfirmButton className="secondary" label={user.active?'Desativar acesso':'Reativar acesso'} title={user.active?'Desativar acesso':'Reativar acesso'}
          message={user.active?'A conta perderá acesso a todas as clínicas.':'A conta voltará a acessar seus vínculos ativos.'}
          busy={action.busy} onConfirm={()=>action.run(()=>action.send(path,{active:!user.active},'PATCH'),pt.saved)}/>}
        <ConfirmButton className="danger secondary" label="Excluir usuário" title="Excluir usuário"
          message="A conta será retirada da plataforma e perderá acesso a todas as clínicas. O histórico ficará preservado."
          busy={action.busy} onConfirm={()=>action.run(async()=>{await action.send(path,{},'DELETE');onClose();},'Usuário excluído.')}/>
      </div>
    </section>}
  </Modal>;
}
