import { useEffect, useState, type ReactNode } from 'react';
import { NavLink, Navigate, Route, Routes, useLocation, useMatch, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from './api';
import { AccountActivation } from './AccountActivation';
import { Agenda } from './Agenda';
import { Audit, Schedules, Services, Settings, SupportReviews, Team } from './Management';
import { IntegrationPage } from './Integrations';
import { InboxPage } from './InboxPage';
import { Platform, type PlatformSection } from './Platform';
import { Profile } from './Profile';
import { pt } from './locales';
import { Empty, Failure, Feedback, Icon, Label, Loading, Modal, PageHeader, timezoneLabel, useAction, useRemote, type IconName } from './ui';
import type { Membership, Page, Professional, Session } from './types';

function Login({onAuthenticated,info}: {onAuthenticated:()=>Promise<unknown>;info?:string}) {
  const [challenge,setChallenge]=useState<string>();
  const [login,setLogin]=useState('');const [password,setPassword]=useState('');const [code,setCode]=useState('');
  const [mode,setMode]=useState<'login'|'recover'|'change'|'activate'>('login');
  const [token,setToken]=useState('');const [replacement,setReplacement]=useState('');
  const [confirmation,setConfirmation]=useState('');
  const action=useAction();
  const mismatch=mode==='change' && confirmation.length>0 && replacement!==confirmation;
  function backToLogin() {
    setMode('login');setChallenge(undefined);setPassword('');setCode('');
    setToken('');setReplacement('');setConfirmation('');
  }
  const [showPassword,setShowPassword]=useState(false);
  const passwordType=showPassword?'text':'password'; // pragma: allowlist secret (tipo do campo)
  const reveal=<button type="button" className="text-button reveal-toggle" aria-pressed={showPassword} onClick={()=>setShowPassword(value=>!value)}><Icon name={showPassword?'eyeOff':'eye'} size={16}/>{pt.showPasswords}</button>;
  return <div className="auth-layout"><section className="auth-story" aria-label={pt.title}><div className="brand-lockup"><span className="brand" aria-hidden="true"><Icon name="plus" size={20}/></span><strong>{pt.title}</strong></div><div className="auth-story-copy"><h1>{pt.foundation}</h1>
      <ul className="auth-features">{pt.loginFeatures.map((item,index)=><li key={item}><span aria-hidden="true"><Icon name={(['calendar','chat','shield'] as const)[index]} size={18}/></span>{item}</li>)}</ul></div><p className="auth-footnote"><Icon name="lock" size={14}/>{pt.mfaNotice}</p></section>
    <main className="auth-panel"><div className="auth-form"><p className="eyebrow">{pt.subtitle}</p><h2 className="auth-title">{mode==='activate'?pt.activateAccount:mode==='change'?pt.changeOwnPassword:mode==='recover'?pt.resetPassword:challenge?pt.verify:pt.signIn}</h2><Feedback action={action}/>{info&&<p role="status" className="feedback success">{info}</p>}
      {mode==='activate'?<AccountActivation onAuthenticated={onAuthenticated}/>:<form onSubmit={event=>{event.preventDefault();void action.run(async()=>{
        if(mode==='recover'){
          await api('/auth/recovery/confirm',{token,password:replacement});backToLogin();return;
        }
        if(mode==='change'){
          if(replacement!==confirmation)throw new Error('password_mismatch');
          await api('/auth/password/change',{login,current_password:password,new_password:replacement,code});
          backToLogin();return;
        }
        const result=challenge?await api<{status:string;challenge?:string}>('/auth/mfa/verify',{challenge,code}):await api<{status:string;challenge?:string}>('/auth/login',{login,password});
        setPassword('');setCode('');if(result.challenge)setChallenge(result.challenge);else{setChallenge(undefined);await onAuthenticated();}
      },mode==='change'?pt.passwordChanged:mode==='recover'?pt.passwordReset:'');}}>
        {challenge&&mode==='login'&&<p className="note compact">{pt.mfaHint}</p>}
        {mode==='change'?<>
          <Label text={pt.login}><input autoComplete="username" required maxLength={254} value={login} onChange={event=>setLogin(event.target.value)}/></Label>
          <Label text={pt.currentPassword}><input type={passwordType} autoComplete="current-password" required maxLength={128} value={password} onChange={event=>setPassword(event.target.value)}/></Label>
          <Label text={pt.code}><input inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required value={code} onChange={event=>setCode(event.target.value)}/></Label>
          <Label text={pt.newPassword}><input type={passwordType} autoComplete="new-password" minLength={12} maxLength={128} required value={replacement} onChange={event=>setReplacement(event.target.value)}/></Label>
          <Label text={pt.confirmNewPassword}><input type={passwordType} autoComplete="new-password" minLength={12} maxLength={128} required value={confirmation} onChange={event=>setConfirmation(event.target.value)}/></Label>
          {mismatch&&<p role="alert" className="feedback error">{pt.passwordMismatch}</p>}
          {reveal}
        </>:mode==='recover'?<>
          <Label text={pt.recoveryToken}><input type="password" autoComplete="off" required maxLength={128} value={token} onChange={event=>setToken(event.target.value)}/></Label>
          <Label text={pt.newPassword} hint={pt.passwordRule}><input type={passwordType} autoComplete="new-password" minLength={12} maxLength={128} required value={replacement} onChange={event=>setReplacement(event.target.value)}/></Label>
          {reveal}
        </>:challenge?
          <Label text={pt.code}><input className="code-input" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required autoFocus value={code} onChange={event=>setCode(event.target.value)}/></Label>
        :<>
          <Label text={pt.login}><input autoComplete="username" required maxLength={254} value={login} onChange={event=>setLogin(event.target.value)}/></Label>
          <Label text={pt.password}><input type={passwordType} autoComplete="current-password" required maxLength={128} value={password} onChange={event=>setPassword(event.target.value)}/></Label>
          {reveal}
        </>}
        <button className="full" disabled={action.busy||mismatch}>{action.busy?pt.loading:mode==='change'?pt.changeOwnPassword:mode==='recover'?pt.resetPassword:challenge?pt.verify:pt.signIn}</button>
      </form>}
      {challenge||mode!=='login'?<div className="auth-help"><button className="text-button" type="button" onClick={backToLogin}><Icon name="left" size={16}/>{pt.backLogin}</button></div>
        :<div className="auth-help">
          <p className="muted">{pt.forgotPassword}</p>
          <div className="auth-links"><button className="text-button" type="button" disabled={action.busy||!login} onClick={()=>void action.run(()=>api('/auth/recovery/request',{login}),pt.recoveryInfo)}>{pt.recovery}</button>
          <button className="text-button" type="button" onClick={()=>setMode('recover')}>{pt.haveRecovery}</button>
          <button className="text-button" type="button" onClick={()=>{action.clearError();setMode('activate');}}>{pt.activateAccount}</button></div>
          {!login&&<small className="field-hint">{pt.recoveryNeedsLogin}</small>}
        </div>}
    </div></main></div>;
}

function InvitationCard({row,onAccepted}:{row:{id:string;clinic_name:string;role:string};onAccepted:()=>Promise<unknown>}) {
  const [code,setCode]=useState('');const action=useAction();
  return <form className="record-card invitation-card" onSubmit={event=>{event.preventDefault();void action.run(async()=>{await api(`/auth/invitations/${row.id}/accept`,{activation_code:code.trim()});await onAccepted();},pt.invitationAccepted);}}>
    <div className="record-main"><h3>{row.clinic_name}</h3><p className="muted">{pt.roles[row.role]}</p></div>
    <Label text={pt.activationCode} hint={pt.acceptCodeHint}><input required autoComplete="off" spellCheck={false} maxLength={128} value={code} onChange={event=>setCode(event.target.value)}/></Label>
    <button disabled={action.busy||!code.trim()}>{pt.acceptInvitation}</button>
    <div className="wide"><Feedback action={action}/></div>
  </form>;
}

function Invitations({onAccepted}: {onAccepted:()=>Promise<unknown>}) {
  const result=useQuery({queryKey:['invitations'],queryFn:()=>api<Page<{id:string;clinic_name:string;role:string}>>('/auth/invitations'),retry:false});
  if(!result.data?.items.length)return null;
  return <section className="invitation-panel" aria-label={pt.invitations}><h2>{pt.invitations}</h2>{result.data.items.map(row=><InvitationCard key={row.id} row={row} onAccepted={async()=>{await result.refetch();await onAccepted();}}/>)}</section>;
}

function Roster({member}: {member:Membership}) {
  const result=useRemote<Page<Professional>>(member,'/professionals');
  if(!result.data?.items.length)return null;
  return <section className="roster"><h2>{pt.professionals}</h2><ul>{result.data.items.map(row=><li key={row.id}><span className="roster-dot" aria-hidden="true"/>{row.display_name}</li>)}</ul></section>;
}

function Allowed({member,capability,children}:{member:Membership;capability:string;children:ReactNode}) {return member.capabilities?.includes(capability)?children:<><PageHeader title={pt.denied}/><Empty icon="lock">{pt.deniedHint}</Empty></>;}

function AccountPassword({onClose,onChanged}: {onClose:()=>void;onChanged:()=>Promise<unknown>}) {
  const [newPassword,setNewPassword]=useState('');
  const [confirmation,setConfirmation]=useState('');
  const action=useAction();
  const mismatch=confirmation.length>0&&confirmation!==newPassword;
  return <Modal title={pt.changeOwnPassword} onClose={onClose} size="narrow">
    <Feedback action={action}/>
    <p className="note">{pt.accountPasswordHint}</p>
    <form className="form-grid single" onSubmit={event=>{event.preventDefault();if(mismatch)return;void action.run(async()=>{
      await api('/auth/password/change-authenticated',{new_password:newPassword});
      setNewPassword('');setConfirmation('');
      await onChanged();
    });}}>
      <Label text={pt.newPassword} hint={pt.passwordRule}><input type="password" autoComplete="new-password" minLength={12} maxLength={128} required value={newPassword} onChange={event=>setNewPassword(event.target.value)}/></Label>
      <Label text={pt.confirmNewPassword}><input type="password" autoComplete="new-password" minLength={12} maxLength={128} required value={confirmation} onChange={event=>setConfirmation(event.target.value)}/></Label>
      {mismatch&&<p role="alert" className="feedback error">{pt.passwordMismatch}</p>}
      <div className="form-actions wide"><button type="button" className="secondary" onClick={onClose}>{pt.cancel}</button><button disabled={action.busy||mismatch}>{action.busy?pt.loading:pt.changeOwnPassword}</button></div>
    </form>
  </Modal>;
}

function AccountPage({role,onPasswordChanged}: {role:string;onPasswordChanged:()=>Promise<unknown>}) {
  const [passwordOpen,setPasswordOpen]=useState(false);
  return <>
    <Profile role={role} onPassword={()=>setPasswordOpen(true)}/>
    {passwordOpen&&<AccountPassword onClose={()=>setPasswordOpen(false)} onChanged={onPasswordChanged}/>}
  </>;
}

const navigation:{path:string;title:string;icon:IconName;cap:string}[]=[
  {path:'/agenda',title:pt.agenda,icon:'calendar',cap:'agenda.read'},{path:'/inbox',title:pt.inbox,icon:'inbox',cap:'inbox.read'},
  {path:'/schedules',title:pt.schedules,icon:'clock',cap:'agenda.read'},{path:'/services',title:pt.services,icon:'services',cap:'services.manage'},
  {path:'/team',title:pt.team,icon:'team',cap:'team.manage'},{path:'/settings',title:pt.settings,icon:'settings',cap:'settings.manage'},
  {path:'/integrations',title:pt.integrations,icon:'plug',cap:'integrations.manage'},{path:'/audit',title:pt.audit,icon:'audit',cap:'audit.read'},
  {path:'/support',title:pt.supportRequests,icon:'shield',cap:'support.review'}];

const platformHome = '/admin';
const platformAccount = `${platformHome}/account`;
const platformTitle = 'Administração da plataforma';
const platformOption = '__platform';
const platformNavigation = [
  {path:platformHome, section:'overview', title:'Visão geral', icon:'services'},
  {path:'/admin/clinics', section:'clinics', title:'Clínicas', icon:'building'},
  {path:'/admin/users', section:'users', title:'Usuários', icon:'team'},
  {path:'/admin/audit', section:'audit', title:pt.audit, icon:'audit'},
] as const satisfies ReadonlyArray<{path:string;section:PlatformSection;title:string;icon:IconName}>;

const platformMember: Membership = {id:'platform',tenant_id:'',role:'superadmin',capabilities:['platform.manage']};

function Workspace({session,member,onSwitch,onLogout,onPasswordChanged,switching,onAccepted}: {session:Session;member?:Membership;onSwitch:(id:string)=>Promise<void>;onLogout:()=>Promise<void>;onPasswordChanged:()=>Promise<unknown>;switching:boolean;onAccepted:()=>Promise<unknown>}) {
  const location=useLocation();
  const navigate=useNavigate();
  const platformPath=useMatch('/admin/*');
  const legacyPlatformPath=useMatch('/clinics');
  const inPlatform=Boolean(session.platform_access && (platformPath || legacyPlatformPath || !member));
  const workspaceMember=inPlatform?platformMember:member;
  const personalAccountPath=useMatch('/account');
  const platformAccountPath=useMatch(platformAccount);
  const accountPath=personalAccountPath || (inPlatform && platformAccountPath);
  const [menuOpen,setMenuOpen]=useState(false);
  useEffect(()=>{setMenuOpen(false);document.getElementById('page-title')?.focus({preventScroll:false});},[location.pathname]);
  useEffect(()=>{if(!menuOpen)return;function escape(event:KeyboardEvent){if(event.key==='Escape')setMenuOpen(false);}window.addEventListener('keydown',escape);return()=>window.removeEventListener('keydown',escape);},[menuOpen]);
  const role=pt.roles[workspaceMember?.role??'']??(session.memberships.length===1?pt.roles[session.memberships[0].role]:pt.subtitle);
  return <><div className={menuOpen?'workspace menu-open':'workspace'}><a className="skip-link" href="#workspace-content" onClick={event=>{event.preventDefault();document.getElementById('workspace-content')?.focus();}}>{pt.skip}</a>
    <aside className="sidebar" id="workspace-menu" aria-label={pt.menu}><div className="sidebar-head"><div className="brand-lockup"><span className="brand" aria-hidden="true"><Icon name="plus" size={20}/></span><span className="brand-text"><strong>{pt.title}</strong><small>{inPlatform?pt.platformShort:pt.clinicPortal}</small></span></div><button type="button" className="icon-button ghost menu-close" aria-label={pt.closeMenu} onClick={()=>setMenuOpen(false)}><Icon name="close"/></button></div>
    {session.memberships.length>0&&<div className="clinic-select"><Label text={pt.choose}><select aria-label={pt.choose} value={inPlatform?platformOption:session.active_membership_id??''} disabled={switching} onChange={event=>{const value=event.target.value;if(value===platformOption)navigate(platformHome);else if(value===session.active_membership_id)navigate('/agenda');else if(value)void onSwitch(value);}}>{!inPlatform&&!session.active_membership_id&&<option value="">{pt.choose}</option>}<optgroup label={pt.clinics}>{session.memberships.map((item,index)=><option key={item.id} value={item.id}>{item.clinic_name??`${pt.clinic} ${index+1}`}</option>)}</optgroup>{session.platform_access&&<optgroup label={pt.administration}><option value={platformOption}>{pt.platformShort}</option></optgroup>}</select></Label></div>}
    {inPlatform?<nav aria-label={platformTitle}>
      {platformNavigation.map(item=><NavLink end to={item.path} key={item.path}><Icon name={item.icon}/>{item.title}</NavLink>)}
    </nav>:<nav aria-label={pt.workspace}>
      {navigation.filter(item=>member?.capabilities?.includes(item.cap)).map(item=><NavLink to={item.path} key={item.path}><Icon name={item.icon}/>{item.title}</NavLink>)}
    </nav>}
    {!inPlatform&&member?.capabilities?.includes('agenda.read')&&<Roster member={member}/>}
  </aside><div className="sidebar-backdrop" aria-hidden="true" onClick={()=>setMenuOpen(false)}/>
  <div className="workspace-main"><header className="topbar">
      <button type="button" className="icon-button ghost menu-toggle" aria-label={pt.openMenu} aria-expanded={menuOpen} aria-controls="workspace-menu" onClick={()=>setMenuOpen(true)}><Icon name="menu"/></button>
      <div className="topbar-context"><strong>{inPlatform?platformTitle:member?.clinic_name??pt.title}</strong>{!inPlatform&&member?.timezone&&<span className="timezone"><Icon name="globe" size={14}/>{timezoneLabel(member.timezone)}</span>}</div>
      <div className="account">
        <NavLink to={inPlatform?platformAccount:'/account'} className="account-link" onClick={()=>setMenuOpen(false)}>
          <Icon name="user" size={18}/><span>{pt.myAccount}</span>
        </NavLink>
        <button type="button" className="ghost account-button" onClick={()=>void onLogout()}><Icon name="logout" size={16}/><span>{pt.logout}</span></button></div>
    </header>
    <main id="workspace-content" tabIndex={-1}>{!inPlatform&&!accountPath&&<Invitations onAccepted={onAccepted}/>}
    {switching?<Loading/>:accountPath?<AccountPage role={role} onPasswordChanged={onPasswordChanged}/>:inPlatform?<Routes>
      {platformNavigation.map(item=><Route key={item.path} path={item.path} element={
        <Platform key={item.section} section={item.section} title={item.title} member={platformMember} userId={session.user_id}/>
      }/>)}
      <Route path="*" element={<Navigate to={platformHome} replace/>}/>
    </Routes>:!member?<><PageHeader title={pt.choose}/><Empty icon="building">{pt.selectClinic}</Empty></>:<Routes>
      <Route path="/agenda" element={<Allowed member={member} capability="agenda.read"><Agenda member={member}/></Allowed>}/>
      <Route path="/services" element={<Allowed member={member} capability="services.manage"><Services member={member}/></Allowed>}/>
      <Route path="/team" element={<Allowed member={member} capability="team.manage"><Team member={member}/></Allowed>}/>
      <Route path="/schedules" element={<Allowed member={member} capability="agenda.read"><Schedules member={member}/></Allowed>}/>
      <Route path="/settings" element={<Allowed member={member} capability="settings.manage"><Settings member={member}/></Allowed>}/>
      <Route path="/inbox" element={<Allowed member={member} capability="inbox.read"><InboxPage member={member}/></Allowed>}/>
      <Route path="/integrations" element={<Allowed member={member} capability="integrations.manage"><IntegrationPage member={member}/></Allowed>}/>
      <Route path="/audit" element={<Allowed member={member} capability="audit.read"><Audit member={member}/></Allowed>}/>
      <Route path="/support" element={<Allowed member={member} capability="support.review"><SupportReviews member={member}/></Allowed>}/>
      <Route path="*" element={<Navigate to="/agenda" replace/>}/>
    </Routes>}</main></div></div>
  </>;
}

export function App() {
  const navigate=useNavigate();
  const client=useQueryClient();// Sem sessão carregada, não revalidar ao voltar o foco ou a conexão: a consulta voltaria a "pendente",
  // desmontaria a tela de login e apagaria o que a pessoa digitou (por exemplo, ao buscar o código no autenticador).
  const revalidateSession=(query:{state:{data:unknown}})=>query.state.data!==undefined;
  const session=useQuery({queryKey:['session'],queryFn:()=>api<Session>('/auth/session'),retry:false,refetchOnWindowFocus:revalidateSession,refetchOnReconnect:revalidateSession});
  const [switching,setSwitching]=useState(false);const [passwordChanged,setPasswordChanged]=useState(false);const [sessionExpired,setSessionExpired]=useState(false);const action=useAction();
  const refetch=session.refetch;
  useEffect(()=>{function expire(){setSessionExpired(true);client.removeQueries({predicate:query=>query.queryKey[0]!=='session'});void refetch();}window.addEventListener('clinic:session-expired',expire);return()=>window.removeEventListener('clinic:session-expired',expire);},[client,refetch]);
  const unauthenticated=session.isError&&session.error instanceof ApiError&&session.error.status===401;
  useEffect(()=>{if(unauthenticated)document.title=`${pt.signIn} · ${pt.title}`;},[unauthenticated]);
  async function authenticated(){
    setPasswordChanged(false);
    setSessionExpired(false);
    client.clear();
    const result=await refetch();
    if(result.data?.platform_access) navigate(platformHome,{replace:true});
    return result;
  }
  async function passwordChangedSuccessfully(){setPasswordChanged(true);client.clear();return refetch();}
  async function switchClinic(id:string){setSwitching(true);await action.run(async()=>{await client.cancelQueries();client.removeQueries({predicate:query=>query.queryKey[0]!=='session'});await api('/auth/active-membership',{membership_id:id});const result=await refetch();const member=result.data?.memberships.find(item=>item.id===id);navigate(member?.capabilities?.includes('platform.manage')?platformHome:'/agenda',{replace:true});});setSwitching(false);}
  async function logout(){await action.run(async()=>{await api('/auth/logout',{});client.clear();await refetch();});}
  if(session.isPending)return <main className="startup"><Loading/></main>;
  if(session.isError){if(unauthenticated)return <Login onAuthenticated={authenticated} info={passwordChanged?pt.passwordChanged:sessionExpired?pt.sessionExpired:undefined}/>;return <main className="startup"><Failure error={session.error}/><button onClick={()=>void refetch()}><Icon name="refresh" size={16}/>{pt.refresh}</button></main>;}
  return <>{action.error!==undefined&&<div className="global-feedback"><Feedback action={action} errorsOnly/></div>}<Workspace onPasswordChanged={passwordChangedSuccessfully} session={session.data} member={session.data.memberships.find(item=>item.id===session.data.active_membership_id)} switching={switching} onSwitch={switchClinic} onLogout={logout} onAccepted={refetch}/></>;
}
