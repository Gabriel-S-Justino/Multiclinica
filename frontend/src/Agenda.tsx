import { useState } from 'react';
import { AppointmentDetails, Booking } from './Booking';
import { pt } from './locales';
import { Empty, Failure, Label, Loading, PageHeader, Status, formatDay, localDay, shiftDay, useRemote } from './ui';
import type { Appointment, Catalog, Membership, Page } from './types';

export function Agenda({member}: {member:Membership}) {
  const [date,setDate] = useState(localDay(member.timezone));
  const [view,setView] = useState<'day'|'week'>('week');
  const [professional,setProfessional] = useState('');
  const [selected,setSelected] = useState<string>();
  const [booking,setBooking] = useState<Appointment | true>();
  const [cursor,setCursor] = useState<string>();
  const [notice,setNotice] = useState('');
  const catalog = useRemote<Catalog>(member,'/portal/catalog');
  const last = shiftDay(date,view==='week'?6:0);
  const query = new URLSearchParams({first_date:date,last_date:last,limit:'100'});
  if (professional) query.set('professional_id',professional);
  if (cursor) query.set('cursor',cursor);
  const appointments = useRemote<Page<Appointment>>(member,`/appointments?${query}`);
  const days = Array.from({length:view==='week'?7:1},(_,index)=>shiftDay(date,index));
  function changeDate(value:string) {setDate(value);setCursor(undefined);}
  return <>
    <PageHeader title={pt.agenda} description={pt.agendaDescription}><button onClick={()=>{setBooking(true);setNotice('');}}>+ {pt.newAppointment}</button></PageHeader>
    {notice && <p role="status" className="feedback success">{notice}</p>}
    <section className="calendar-panel">
      <div className="calendar-toolbar"><div className="date-controls"><button className="icon-button secondary" aria-label={pt.previous} onClick={()=>changeDate(shiftDay(date,view==='week'?-7:-1))}>‹</button>
        <Label text={pt.date}><input type="date" value={date} required onChange={event=>changeDate(event.target.value)}/></Label>
        <button className="icon-button secondary" aria-label={pt.following} onClick={()=>changeDate(shiftDay(date,view==='week'?7:1))}>›</button></div>
        <Label text={pt.professional}><select value={professional} onChange={event=>{setProfessional(event.target.value);setCursor(undefined);}}><option value="">{pt.allProfessionals}</option>{catalog.data?.professionals.map(item=><option key={item.id} value={item.id}>{item.display_name}</option>)}</select></Label>
        <div className="segmented" aria-label={pt.agenda}><button className={view==='day'?'selected':''} aria-pressed={view==='day'} onClick={()=>{setView('day');setCursor(undefined);}}>{pt.day}</button><button className={view==='week'?'selected':''} aria-pressed={view==='week'} onClick={()=>{setView('week');setCursor(undefined);}}>{pt.week}</button></div>
      </div>
      {appointments.isPending ? <Loading/> : appointments.isError ? <Failure error={appointments.error}/> : <div className={`calendar-grid view-${view}`}>
        {days.map(day=><section className="calendar-day" key={day} aria-label={formatDay(day)}><header><span>{new Intl.DateTimeFormat('pt-BR',{weekday:'short',timeZone:'UTC'}).format(new Date(`${day}T12:00:00Z`))}</span><h2>{formatDay(day)}</h2></header>
          <div className="day-body">{appointments.data.items.filter(row=>row.local_date===day).map(row=><button key={row.id} className={`appointment-card appointment-${row.status}`} onClick={()=>setSelected(row.id)}>
            <span className="appointment-time">{row.local_start}–{row.local_end}</span><strong>{row.patient_name}</strong><span>{row.service_name}</span><small>{row.professional_name}</small><Status value={row.status}/>
          </button>)}{!appointments.data.items.some(row=>row.local_date===day) && <Empty/>}</div></section>)}
      </div>}
      <footer className="calendar-footer"><span>{pt.timezone}: {catalog.data?.timezone ?? member.timezone}</span>{appointments.data?.next_cursor && <button className="secondary" onClick={()=>setCursor(appointments.data?.next_cursor ?? undefined)}>{pt.following}</button>}
        {cursor && <button className="secondary" onClick={()=>setCursor(undefined)}>{pt.back}</button>}</footer>
    </section>
    {selected && !booking && <AppointmentDetails member={member} appointmentId={selected} onClose={()=>setSelected(undefined)} onReschedule={row=>{setSelected(undefined);setBooking(row);}}/>}
    {booking && <Booking member={member} original={booking===true?undefined:booking} onClose={()=>setBooking(undefined)} onDone={id=>{setNotice(booking===true?pt.appointmentCreated:pt.rescheduled);setBooking(undefined);setSelected(id);}}/>}
  </>;
}
