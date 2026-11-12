import { useEffect, useRef, useState } from 'react';
import { pt } from './locales';
import { Empty, Failure, Feedback, Icon, Label, Loading, Modal, PageHeader, Status, useAction, useRemote } from './ui';
import type { Handoff, Membership, Message, Page, Queue } from './types';

function time(value: string, timezone?: string) {
  return new Date(value).toLocaleTimeString('pt-BR', {hour:'2-digit', minute:'2-digit', timeZone: timezone});
}

function Conversation({member, id}: {member:Membership;id:string}) {
  const [cursor,setCursor]=useState<string>();
  const result=useRemote<Page<Message>&{handoff:Handoff}>(member,`/handoffs/${id}/messages${cursor?`?cursor=${encodeURIComponent(cursor)}`:''}`);
  const action=useAction(member);const [text,setText]=useState('');
  const list=useRef<HTMLOListElement>(null);
  const handoff=result.data?.handoff;
  const count=result.data?.items.length ?? 0;
  useEffect(()=>{const element=list.current;if(element)element.scrollTop=element.scrollHeight;},[count]);
  function act(name:string) {if(handoff) void action.run(()=>action.send(`/handoffs/${id}/${name}`,{version:handoff.version}),pt.handoffUpdated);}
  function reply() {if(handoff && text.trim()) void action.run(async()=>{await action.send(`/handoffs/${id}/replies`,{version:handoff.version,text});setText('');},pt.replyQueued);}
  const canReply = !!handoff && handoff.assigned_to_me && handoff.status==='assigned';
  return <section className="conversation-panel" aria-label={pt.conversation}>
    {result.isPending?<Loading/>:result.isError?<Failure error={result.error}/>:handoff && <>
      <header className="conversation-header"><div><h2>{handoff.queue_name}</h2><p className="muted">{pt.reasons[handoff.reason_code]} · {pt.openedAt} {time(handoff.created_at, member.timezone)}</p></div><Status value={handoff.status}/></header>
      <Feedback action={action}/><div className="conversation-actions">
        {handoff.status==='waiting' && <button disabled={action.busy} onClick={()=>act('claim')}>{pt.claim}</button>}
        {canReply && <><button className="secondary" disabled={action.busy} onClick={()=>act('release')}>{pt.release}</button><button className="secondary" disabled={action.busy} onClick={()=>act('close')}>{pt.closeHandoff}</button></>}
        <button className="ghost push-right" disabled={result.isFetching} onClick={()=>void result.refetch()}><Icon name="refresh" size={16}/>{pt.refresh}</button>
      </div>
      {cursor && <button className="text-button" onClick={()=>setCursor(undefined)}>{pt.back}</button>}
      {result.data.items.length ? <ol className="messages" ref={list} aria-label={pt.conversation}>{result.data.items.map(message=><li key={message.id} className={`message ${message.direction}`}><p>{message.text}</p><footer><time dateTime={message.created_at}>{time(message.created_at, member.timezone)}</time><Status value={message.delivery_status}/></footer></li>)}</ol>
        : <Empty icon="chat">{pt.noMessages}</Empty>}
      {result.data.next_cursor && <button className="text-button" onClick={()=>setCursor(result.data.next_cursor??undefined)}>{pt.following}</button>}
      {canReply && <form className="reply-form" onSubmit={event=>{event.preventDefault();reply();}}><Label text={pt.reply}><textarea autoComplete="off" maxLength={4000} required value={text} onChange={event=>setText(event.target.value)} onKeyDown={event=>{if(event.key==='Enter'&&(event.ctrlKey||event.metaKey)){event.preventDefault();reply();}}} rows={3}/></Label>
        <div className="reply-footer"><p className="muted">{pt.queuedHint} {pt.sendShortcut}</p><span className="char-count" aria-hidden="true">{text.length}/4000</span><button disabled={action.busy||!text.trim()}>{pt.sendReply}</button></div></form>}
    </>}
  </section>;
}

export function InboxPage({member}:{member:Membership}) {
  const [selected,setSelected]=useState<string>();const [create,setCreate]=useState(false);
  const [phone,setPhone]=useState('');const [queue,setQueue]=useState('');const [reason,setReason]=useState('patient_request');
  const [cursor,setCursor]=useState<string>();
  const result=useRemote<Page<Handoff>>(member,`/inbox?limit=100${cursor?`&cursor=${encodeURIComponent(cursor)}`:''}`);const queues=useRemote<Page<Queue>>(member,'/queues');const action=useAction(member);
  const waiting=result.data?.items.filter(row=>row.status==='waiting').length ?? 0;
  return <><PageHeader title={pt.inbox} description={pt.inboxDescription}><button className="secondary" disabled={result.isFetching} onClick={()=>void result.refetch()}><Icon name="refresh" size={16}/>{pt.refresh}</button><button onClick={()=>{action.clearError();setCreate(true);}}><Icon name="plus" size={16}/>{pt.newHandoff}</button></PageHeader><Feedback action={action}/>
    <div className={`inbox-layout${selected?' has-selection':''}`}><aside className="inbox-list" aria-label={pt.conversations}>
      <div className="inbox-list-header"><h2>{pt.conversations}</h2>{waiting>0 && <span className="badge status-waiting">{waiting} {pt.statuses.waiting.toLowerCase()}</span>}</div>
      {result.isPending?<Loading/>:result.isError?<Failure error={result.error}/>:!result.data.items.length?<Empty icon="inbox"/>:result.data.items.map(row=><button key={row.id} className={`conversation-card ${selected===row.id?'selected':''}`} aria-current={selected===row.id?'true':undefined} onClick={()=>setSelected(row.id)}><span className="conversation-card-top"><strong>{row.queue_name}</strong><time dateTime={row.created_at}>{time(row.created_at, member.timezone)}</time></span><span>{pt.reasons[row.reason_code]}</span><span className="conversation-card-bottom"><Status value={row.status}/>{row.assigned_to_me && <span className="mine">{pt.assignedToMe}</span>}</span></button>)}
      {cursor&&<button className="secondary" onClick={()=>setCursor(undefined)}>{pt.back}</button>}{result.data?.next_cursor&&<button className="secondary" onClick={()=>setCursor(result.data.next_cursor??undefined)}>{pt.following}</button>}</aside>
      {selected?<div className="conversation-column"><button type="button" className="text-button back-to-list" onClick={()=>setSelected(undefined)}><Icon name="left" size={16}/>{pt.conversations}</button><Conversation key={selected} member={member} id={selected}/></div>:<section className="conversation-panel conversation-placeholder"><Empty icon="chat">{pt.selectConversation}</Empty></section>}
    </div>
    {create && <Modal title={pt.newHandoff} onClose={()=>setCreate(false)}><Feedback action={action} errorsOnly/><form className="form-grid" onSubmit={event=>{event.preventDefault();void action.run(async()=>{
      const contact=await action.send<{contact_id:string}>('/contacts',{phone});
      const result=await action.send<Handoff&{notice?:string}>('/handoffs',{contact_id:contact.contact_id,queue_id:queue,reason_code:reason});
      setSelected(result.id);setCreate(false);setPhone('');if(result.notice)action.setNotice(result.notice);
    },pt.handoffCreated);}}><Label text={pt.contactPhone}><input type="tel" autoComplete="off" placeholder="+5511999999999" required maxLength={16} value={phone} onChange={event=>setPhone(event.target.value)}/></Label><Label text={pt.queue}><select required value={queue} onChange={event=>setQueue(event.target.value)}><option value="">{pt.select}</option>{queues.data?.items.map(row=><option key={row.id} value={row.id}>{row.name}</option>)}</select></Label>
      <Label text={pt.reason}><select value={reason} onChange={event=>setReason(event.target.value)}>{Object.entries(pt.reasons).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></Label><div className="form-actions wide"><button type="button" className="secondary" onClick={()=>setCreate(false)}>{pt.cancel}</button><button disabled={action.busy}>{pt.create}</button></div></form></Modal>}
  </>;
}
