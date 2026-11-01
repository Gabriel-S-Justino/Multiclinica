import { useEffect, useState, type ReactNode } from 'react';
import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from './api';
import { Agenda } from './Agenda';
import { Audit, IntegrationPage, Schedules, Services, Settings, SupportReviews, Team } from './Management';
import { InboxPage } from './InboxPage';
import { Platform } from './Platform';
import { pt } from './locales';
import { Empty, Failure, Feedback, Label, Loading, PageHeader, useAction, useRemote } from './ui';
import type { Membership, Page, Professional, Session } from './types';

function Login({onAuthenticated}: {onAuthenticated:()=>Promise<unknown>}) {
  const [challenge,setChallenge]=useState<string>();const [login,setLogin]=useState('');const [password,setPassword]=useState('');const [code,setCode]=useState('');
  const [recovery,setRecovery]=useState(false);const [token,setToken]=useState('');const [replacement,setReplacement]=useState('');
  const action=useAction();
  return <div className="auth-layout"><section className="auth-story" aria-label={pt.title}><div className="brand-lockup"><span className="brand" aria-hidden="true">+</span><strong>{pt.title}</strong></div><div><p className="eyebrow">{pt.workspace}</p><h1>{pt.foundation}</h1><div className="story-lines" aria-hidden="true"><i/><i/><i/></div></div><p>{pt.agenda} · {pt.inbox}</p></section>
    <main className="auth-panel"><div className="auth-form"><p className="eyebrow">{pt.subtitle}</p><h2>{recovery?pt.resetPassword:challenge?pt.verify:pt.signIn}</h2><Feedback action={action}/>
      <form onSubmit={event=>{event.preventDefault();void action.run(async()=>{
        if(recovery){await api('/auth/recovery/confirm',{token,password:replacement});setRecovery(false);setToken('');setReplacement('');action.setNotice(pt.passwordReset);return;}
        const result=challenge?await api<{status:string;challenge?:string}>('/auth/mfa/verify',{challenge,code}):await api<{status:string;challenge?:string}>('/auth/login',{login,password});
        setPassword('');setCode('');if(result.challenge)setChallenge(result.challenge);else{setChallenge(undefined);await onAuthenticated();}
      });}}>
        {recovery?<><Label text={pt.recoveryToken}><input type="password" autoComplete="off" required maxLength={128} value={token} onChange={event=>setToken(event.target.value)}/></Label><Label text={pt.newPassword}><input type="password" autoComplete="new-password" minLength={12} maxLength={128} required value={replacement} onChange={event=>setReplacement(event.target.value)}/></Label></>:challenge?<Label text={pt.code}><input inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required autoFocus value={code} onChange={event=>setCode(event.target.value)}/></Label>:<>
          <Label text={pt.login}><input autoComplete="username" required maxLength={254} value={login} onChange={event=>setLogin(event.target.value)}/></Label>
          <Label text={pt.password}><input type="password" autoComplete="current-password" required maxLength={128} value={password} onChange={event=>setPassword(event.target.value)}/></Label></>}
        <button className="full" disabled={action.busy}>{action.busy?pt.loading:recovery?pt.resetPassword:challenge?pt.verify:pt.signIn}</button>
      </form>
      {challenge||recovery?<button className="text-button" onClick={()=>{setChallenge(undefined);setRecovery(false);setPassword('');setCode('');setToken('');setReplacement('');}}>{pt.backLogin}</button>:<div className="auth-help"><button className="text-button" disabled={action.busy||!login} onClick={()=>void action.run(()=>api('/auth/recovery/request',{login}),pt.recoveryInfo)}>{pt.recovery}</button><button className="text-button" onClick={()=>setRecovery(true)}>{pt.haveRecovery}</button></div>}
    </div></main></div>;
}

function Invitations({onAccepted}: {onAccepted:()=>Promise<unknown>}) {
  const result=useQuery({queryKey:['invitations'],queryFn:()=>api<Page<{id:string;clinic_name:string;role:string}>>('/auth/invitations'),retry:false});const action=useAction();
  if(!result.data?.items.length)return null;
  return <section className="invitation-panel" aria-label={pt.invitations}><h2>{pt.invitations}</h2><Feedback action={action}/>{result.data.items.map(row=><div className="record-card" key={row.id}><span>{row.clinic_name} · {pt.roles[row.role]}</span><button disabled={action.busy} onClick={()=>void action.run(async()=>{await api(`/auth/invitations/${row.id}/accept`,{});await result.refetch();await onAccepted();},pt.invitationAccepted)}>{pt.acceptInvitation}</button></div>)}</section>;
}

function Roster({member}: {member:Membership}) {
  const result=useRemote<Page<Professional>>(member,'/professionals');
  if(!result.data?.items.length)return null;
  return <section className="roster"><h2>{pt.professionals}</h2><ul>{result.data.items.map(row=><li key={row.id}><span aria-hidden="true">•</span>{row.display_name}</li>)}</ul></section>;
}

function Allowed({member,capability,children}:{member:Membership;capability:string;children:ReactNode}) {return member.capabilities?.includes(capability)?children:<><PageHeader title={pt.denied}/><Empty>{pt.denied}</Empty></>;}

function Workspace({session,member,onSwitch,onLogout,switching,onAccepted}: {session:Session;member?:Membership;onSwitch:(id:string)=>Promise<void>;onLogout:()=>Promise<void>;switching:boolean;onAccepted:()=>Promise<unknown>}) {
  const location=useLocation();
  useEffect(()=>{document.getElementById('page-title')?.focus();},[location.pathname]);
  const nav=[{path:'/agenda',title:pt.agenda,icon:'▦',cap:'agenda.read'},{path:'/inbox',title:pt.inbox,icon:'◷',cap:'inbox.read'},
    {path:'/schedules',title:pt.schedules,icon:'▤',cap:'agenda.read'},{path:'/services',title:pt.services,icon:'◇',cap:'services.manage'},
    {path:'/team',title:pt.team,icon:'♧',cap:'team.manage'},{path:'/settings',title:pt.settings,icon:'⚙',cap:'settings.manage'},
    {path:'/integrations',title:pt.integrations,icon:'↔',cap:'integrations.manage'},{path:'/audit',title:pt.audit,icon:'≡',cap:'audit.read'},
    {path:'/support',title:pt.supportRequests,icon:'◎',cap:'support.review'},{path:'/clinics',title:pt.platform,icon:'▥',cap:'platform.manage'}];
  const home=member?.capabilities?.includes('platform.manage')?'/clinics':'/agenda';
  return <div className="workspace"><a className="skip-link" href="#workspace-content" onClick={event=>{event.preventDefault();document.getElementById('workspace-content')?.focus();}}>{pt.skip}</a><aside className="sidebar"><div className="brand-lockup"><span className="brand" aria-hidden="true">+</span><strong>{pt.title}</strong></div>
    <div className="clinic-select"><Label text={pt.choose}><select aria-label={pt.choose} value={session.active_membership_id??''} disabled={switching} onChange={event=>{if(event.target.value)void onSwitch(event.target.value);}}><option value="">{pt.choose}</option>{session.memberships.map((item,index)=><option key={item.id} value={item.id}>{item.clinic_name??`${pt.clinic} ${index+1}`}</option>)}</select></Label></div>
    <nav aria-label={pt.workspace}>{nav.filter(item=>member?.capabilities?.includes(item.cap)).map(item=><NavLink to={item.path} key={item.path}><span aria-hidden="true">{item.icon}</span>{item.title}</NavLink>)}</nav>
    {member?.capabilities?.includes('agenda.read')&&<Roster member={member}/>}<div className="sidebar-footer"><span className="avatar" aria-hidden="true">{(pt.roles[member?.role??'']??pt.subtitle).slice(0,2).toUpperCase()}</span><div><strong>{pt.roles[member?.role??'']??pt.subtitle}</strong><button className="text-button" onClick={()=>void onLogout()}>{pt.logout}</button></div></div>
  </aside><div className="workspace-main"><header className="topbar"><span>{member?.clinic_name??pt.title}</span><span className="timezone">{member?.timezone}</span></header>
    <main id="workspace-content" tabIndex={-1}><Invitations onAccepted={onAccepted}/>{switching?<Loading/>:!member?<><PageHeader title={pt.choose}/><Empty>{pt.selectClinic}</Empty></>:<Routes>
      <Route path="/agenda" element={<Allowed member={member} capability="agenda.read"><Agenda member={member}/></Allowed>}/>
      <Route path="/services" element={<Allowed member={member} capability="services.manage"><Services member={member}/></Allowed>}/>
      <Route path="/team" element={<Allowed member={member} capability="team.manage"><Team member={member}/></Allowed>}/>
      <Route path="/schedules" element={<Allowed member={member} capability="agenda.read"><Schedules member={member}/></Allowed>}/>
      <Route path="/settings" element={<Allowed member={member} capability="settings.manage"><Settings member={member}/></Allowed>}/>
      <Route path="/inbox" element={<Allowed member={member} capability="inbox.read"><InboxPage member={member}/></Allowed>}/>
      <Route path="/integrations" element={<Allowed member={member} capability="integrations.manage"><IntegrationPage member={member}/></Allowed>}/>
      <Route path="/audit" element={<Allowed member={member} capability="audit.read"><Audit member={member}/></Allowed>}/>
      <Route path="/support" element={<Allowed member={member} capability="support.review"><SupportReviews member={member}/></Allowed>}/>
      <Route path="/clinics" element={<Allowed member={member} capability="platform.manage"><Platform member={member}/></Allowed>}/>
      <Route path="*" element={<Navigate to={home} replace/>}/>
    </Routes>}</main></div></div>;
}

export function App() {
  const client=useQueryClient();const session=useQuery({queryKey:['session'],queryFn:()=>api<Session>('/auth/session'),retry:false});
  const [switching,setSwitching]=useState(false);const action=useAction();
  const refetch=session.refetch;
  useEffect(()=>{function expire(){client.removeQueries({predicate:query=>query.queryKey[0]!=='session'});void refetch();}window.addEventListener('clinic:session-expired',expire);return()=>window.removeEventListener('clinic:session-expired',expire);},[client,refetch]);
  async function authenticated(){client.clear();return refetch();}
  async function switchClinic(id:string){setSwitching(true);await action.run(async()=>{await client.cancelQueries();client.removeQueries({predicate:query=>query.queryKey[0]!=='session'});await api('/auth/active-membership',{membership_id:id});await refetch();});setSwitching(false);}
  async function logout(){await action.run(async()=>{await api('/auth/logout',{});client.clear();await refetch();});}
  if(session.isPending)return <main className="startup"><Loading/></main>;
  if(session.isError){if(session.error instanceof ApiError&&session.error.status===401)return <Login onAuthenticated={authenticated}/>;return <main className="startup"><Failure error={session.error}/><button onClick={()=>void refetch()}>{pt.refresh}</button></main>;}
  return <><Feedback action={action}/><Workspace session={session.data} member={session.data.memberships.find(item=>item.id===session.data.active_membership_id)} switching={switching} onSwitch={switchClinic} onLogout={logout} onAccepted={refetch}/></>;
}
