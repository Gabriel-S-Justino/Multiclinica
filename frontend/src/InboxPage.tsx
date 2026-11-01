import { useState } from 'react';
import { pt } from './locales';
import { Empty, Failure, Feedback, Label, Loading, Modal, PageHeader, Status, useAction, useRemote } from './ui';
import type { Handoff, Membership, Message, Page, Queue } from './types';

function Conversation({member, id}: {member:Membership;id:string}) {
  const [cursor,setCursor]=useState<string>();
  const result=useRemote<Page<Message>&{handoff:Handoff}>(member,`/handoffs/${id}/messages${cursor?`?cursor=${encodeURIComponent(cursor)}`:''}`);
  const action=useAction(member);const [text,setText]=useState('');
  const handoff=result.data?.handoff;
  function act(name:string) {if(handoff) void action.run(()=>action.send(`/handoffs/${id}/${name}`,{version:handoff.version}),pt.handoffUpdated);}
  return <section className="conversation-panel" aria-label={pt.conversation}>
    {result.isPending?<Loading/>:result.isError?<Failure error={result.error}/>:handoff && <>
      <header className="conversation-header"><div><h2>{handoff.queue_name}</h2><p className="muted">{pt.reasons[handoff.reason_code]}</p></div><Status value={handoff.status}/></header>
      <Feedback action={action}/><div className="conversation-actions"><button className="secondary" onClick={()=>void result.refetch()}>{pt.refresh}</button>
        {handoff.status==='waiting' && <button disabled={action.busy} onClick={()=>act('claim')}>{pt.claim}</button>}
        {handoff.assigned_to_me && handoff.status==='assigned' && <><button className="secondary" disabled={action.busy} onClick={()=>act('release')}>{pt.release}</button><button className="secondary" disabled={action.busy} onClick={()=>act('close')}>{pt.closeHandoff}</button></>}
      </div>
      <ol className="messages" aria-label={pt.conversation}>{result.data.items.map(message=><li key={message.id} className={`message ${message.direction}`}><p>{message.text}</p><footer><time dateTime={message.created_at}>{new Date(message.created_at).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit',timeZone:member.timezone})}</time><Status value={message.delivery_status}/></footer></li>)}</ol>
      {!result.data.items.length && <Empty>{pt.noMessages}</Empty>}
      {cursor && <button className="secondary" onClick={()=>setCursor(undefined)}>{pt.back}</button>}{result.data.next_cursor && <button className="secondary" onClick={()=>setCursor(result.data.next_cursor??undefined)}>{pt.following}</button>}
      {handoff.assigned_to_me && handoff.status==='assigned' && <form className="reply-form" onSubmit={event=>{event.preventDefault();void action.run(async()=>{await action.send(`/handoffs/${id}/replies`,{version:handoff.version,text});setText('');},pt.replyQueued);}}><Label text={pt.reply}><textarea autoComplete="off" maxLength={4000} required value={text} onChange={event=>setText(event.target.value)} rows={3}/></Label><p className="muted">{pt.queuedHint}</p><button disabled={action.busy}>{pt.sendReply}</button></form>}
    </>}
  </section>;
}

export function InboxPage({member}:{member:Membership}) {
  const [selected,setSelected]=useState<string>();const [create,setCreate]=useState(false);
  const [phone,setPhone]=useState('');const [queue,setQueue]=useState('');const [reason,setReason]=useState('patient_request');
  const [cursor,setCursor]=useState<string>();
  const result=useRemote<Page<Handoff>>(member,`/inbox?limit=100${cursor?`&cursor=${encodeURIComponent(cursor)}`:''}`);const queues=useRemote<Page<Queue>>(member,'/queues');const action=useAction(member);
  return <><PageHeader title={pt.inbox} description={pt.inboxDescription}><div className="form-actions"><button className="secondary" onClick={()=>void result.refetch()}>{pt.refresh}</button><button onClick={()=>setCreate(true)}>+ {pt.newHandoff}</button></div></PageHeader><Feedback action={action}/>
    <div className="inbox-layout"><aside className="inbox-list" aria-label={pt.inbox}>{result.isPending?<Loading/>:result.isError?<Failure error={result.error}/>:!result.data.items.length?<Empty/>:result.data.items.map(row=><button key={row.id} className={`conversation-card ${selected===row.id?'selected':''}`} onClick={()=>setSelected(row.id)}><strong>{row.queue_name}</strong><span>{pt.reasons[row.reason_code]}</span><Status value={row.status}/></button>)}{cursor&&<button className="secondary" onClick={()=>setCursor(undefined)}>{pt.back}</button>}{result.data?.next_cursor&&<button className="secondary" onClick={()=>setCursor(result.data.next_cursor??undefined)}>{pt.following}</button>}</aside>
      {selected?<Conversation key={selected} member={member} id={selected}/>:<section className="conversation-panel"><Empty>{pt.selectConversation}</Empty></section>}
    </div>
    {create && <Modal title={pt.newHandoff} onClose={()=>setCreate(false)}><form className="form-grid" onSubmit={event=>{event.preventDefault();void action.run(async()=>{
      const contact=await action.send<{contact_id:string}>('/contacts',{phone});
      const result=await action.send<Handoff&{notice?:string}>('/handoffs',{contact_id:contact.contact_id,queue_id:queue,reason_code:reason});
      setSelected(result.id);setCreate(false);setPhone('');if(result.notice)action.setNotice(result.notice);
    },pt.handoffCreated);}}><Label text={pt.contactPhone}><input type="tel" autoComplete="off" placeholder="+5511999999999" required maxLength={16} value={phone} onChange={event=>setPhone(event.target.value)}/></Label><Label text={pt.queue}><select required value={queue} onChange={event=>setQueue(event.target.value)}><option value="">{pt.select}</option>{queues.data?.items.map(row=><option key={row.id} value={row.id}>{row.name}</option>)}</select></Label>
      <Label text={pt.reason}><select value={reason} onChange={event=>setReason(event.target.value)}>{Object.entries(pt.reasons).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></Label><div className="wide"><button disabled={action.busy}>{pt.create}</button></div></form><Feedback action={action}/></Modal>}
  </>;
}
