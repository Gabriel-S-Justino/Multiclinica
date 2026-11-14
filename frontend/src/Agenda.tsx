import { useState } from 'react';
import { Link } from 'react-router-dom';
import { AppointmentDetails, Booking } from './Booking';
import { pt } from './locales';
import { Empty, Failure, Icon, Label, Loading, PageHeader, Status, formatDay, formatRange, formatWeekday, localDay, shiftDay, useRemote, weekStart, timezoneLabel } from './ui';
import type { Appointment, Catalog, Membership, Page } from './types';

/** Passos mínimos para a clínica conseguir agendar: unidade, profissional ativo e serviço liberado. */
function SetupChecklist({member, catalog}: {member:Membership; catalog:Catalog}) {
  const steps = [
    {done: catalog.units.length > 0, label: pt.setupUnit, to: '/settings', cap: 'settings.manage'},
    {done: catalog.professionals.some(item => item.active), label: pt.setupProfessional, to: '/team', cap: 'team.manage'},
    {done: catalog.services.some(item => item.bookable), label: pt.setupService, to: '/services', cap: 'services.manage'},
  ];
  if (steps.every(step => step.done)) return null;
  const canConfigure = steps.some(step => member.capabilities?.includes(step.cap));
  return <section className="panel setup-checklist" aria-labelledby="setup-title">
    <h2 id="setup-title">{pt.setupTitle}</h2>
    <p className="muted">{canConfigure ? pt.setupHint : pt.setupAskAdmin}</p>
    {canConfigure && <ol>{steps.map(step => <li key={step.label} className={step.done ? 'done' : ''}>
      <span className="step-index" aria-hidden="true">{step.done ? <Icon name="check" size={14}/> : null}</span>
      {step.done || !member.capabilities?.includes(step.cap) ? <span>{step.label}</span> : <Link to={step.to}>{step.label}</Link>}
      <span className="visually-hidden">{step.done ? pt.stepDone : pt.stepPending}</span>
    </li>)}</ol>}
    {canConfigure && <p className="muted setup-next">{pt.setupSchedules}</p>}
  </section>;
}

function prefersDayView() {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia('(max-width: 760px)').matches;
}

export function Agenda({member}: {member:Membership}) {
  const today = localDay(member.timezone);
  const [date,setDate] = useState(today);
  const [view,setView] = useState<'day'|'week'>(() => prefersDayView() ? 'day' : 'week');
  const [professional,setProfessional] = useState('');
  const [selected,setSelected] = useState<string>();
  const [booking,setBooking] = useState<Appointment | true>();
  const [cursor,setCursor] = useState<string>();
  const [notice,setNotice] = useState('');
  const catalog = useRemote<Catalog>(member,'/portal/catalog');
  const first = view==='week' ? weekStart(date) : date;
  const last = shiftDay(first,view==='week'?6:0);
  const query = new URLSearchParams({first_date:first,last_date:last,limit:'100'});
  if (professional) query.set('professional_id',professional);
  if (cursor) query.set('cursor',cursor);
  const appointments = useRemote<Page<Appointment>>(member,`/appointments?${query}`);
  const days = Array.from({length:view==='week'?7:1},(_,index)=>shiftDay(first,index));
  const showsToday = days.includes(today);
  function changeDate(value:string) {if(value){setDate(value);setCursor(undefined);}}
  function changeView(value:'day'|'week') {setView(value);setCursor(undefined);}
  const items = appointments.data?.items ?? [];
  const active = items.filter(row=>days.includes(row.local_date) && row.status!=='canceled' && row.status!=='rescheduled').length;
  return <>
    <PageHeader title={pt.agenda} description={pt.agendaDescription}><button onClick={()=>{setBooking(true);setNotice('');}}><Icon name="plus" size={16}/>{pt.newAppointment}</button></PageHeader>
    {catalog.data && <SetupChecklist member={member} catalog={catalog.data}/>}
    {notice && <p role="status" className="feedback success"><Icon name="check"/><span>{notice}</span><button type="button" className="feedback-dismiss" aria-label={pt.dismiss} onClick={()=>setNotice('')}><Icon name="close" size={16}/></button></p>}
    <section className="calendar-panel" aria-label={pt.agenda}>
      <div className="calendar-toolbar">
        <div className="date-controls">
          <button type="button" className="secondary today-button" disabled={showsToday && date===today} onClick={()=>changeDate(today)}>{pt.today}</button>
          <div className="stepper-buttons">
            <button type="button" className="icon-button secondary" aria-label={pt.previous} onClick={()=>changeDate(shiftDay(date,view==='week'?-7:-1))}><Icon name="left"/></button>
            <button type="button" className="icon-button secondary" aria-label={pt.following} onClick={()=>changeDate(shiftDay(date,view==='week'?7:1))}><Icon name="right"/></button>
          </div>
          <Label text={pt.date}><input type="date" value={date} required onChange={event=>changeDate(event.target.value)}/></Label>
        </div>
        <Label text={pt.professional}><select value={professional} onChange={event=>{setProfessional(event.target.value);setCursor(undefined);}}><option value="">{pt.allProfessionals}</option>{catalog.data?.professionals.map(item=><option key={item.id} value={item.id}>{item.display_name}</option>)}</select></Label>
        <div className="segmented" role="group" aria-label={pt.period}><button type="button" className={view==='day'?'selected':''} aria-pressed={view==='day'} onClick={()=>changeView('day')}>{pt.day}</button><button type="button" className={view==='week'?'selected':''} aria-pressed={view==='week'} onClick={()=>changeView('week')}>{pt.week}</button></div>
      </div>
      <div className="calendar-summary"><h2 aria-live="polite">{formatRange(first,last)}</h2>{appointments.data && <span className="muted">{active} {active===1?pt.appointmentSingular:pt.appointmentsCount}</span>}</div>
      {appointments.isPending ? <Loading/> : appointments.isError ? <Failure error={appointments.error}/> : <div className={`calendar-grid view-${view}`}>
        {days.map(day=>{
          const rows = items.filter(row=>row.local_date===day);
          const isToday = day===today;
          return <section className={`calendar-day${isToday?' is-today':''}${rows.length?'':' is-empty'}`} key={day} aria-label={`${formatWeekday(day)}, ${formatDay(day)}${isToday?` (${pt.today})`:''}`}>
            <header>{view==='week' ? <button type="button" className="day-link" onClick={()=>{setDate(day);changeView('day');}} aria-label={`${pt.openDay}: ${formatWeekday(day)}, ${formatDay(day)}`}><span>{formatWeekday(day)}</span><strong>{formatDay(day)}</strong></button>
              : <div className="day-link"><span>{formatWeekday(day)}</span><strong>{formatDay(day)}</strong></div>}
              {rows.length>0 && <span className="day-count" aria-hidden="true">{rows.length}</span>}{isToday && <span className="today-pill">{pt.today}</span>}</header>
            <div className="day-body">{rows.map(row=><button type="button" key={row.id} className={`appointment-card appointment-${row.status}`} onClick={()=>setSelected(row.id)}>
              <span className="appointment-time">{row.local_start} a {row.local_end}</span><strong>{row.patient_name}</strong><span>{row.service_name}</span><small>{row.professional_name}</small><Status value={row.status}/>
            </button>)}{!rows.length && <Empty compact>{pt.noAppointments}</Empty>}</div></section>;
        })}
      </div>}
      <footer className="calendar-footer"><span><Icon name="globe" size={14}/>{pt.timezone}: {timezoneLabel(catalog.data?.timezone ?? member.timezone)}</span><div className="form-actions">
        {cursor && <button type="button" className="secondary" onClick={()=>setCursor(undefined)}>{pt.firstPage}</button>}
        {appointments.data?.next_cursor && <button type="button" className="secondary" onClick={()=>setCursor(appointments.data?.next_cursor ?? undefined)}>{pt.morePage}</button>}</div></footer>
    </section>
    {selected && !booking && <AppointmentDetails member={member} appointmentId={selected} onClose={()=>setSelected(undefined)} onReschedule={row=>{setSelected(undefined);setBooking(row);}}/>}
    {booking && <Booking member={member} original={booking===true?undefined:booking} onClose={()=>setBooking(undefined)} onDone={id=>{setNotice(booking===true?pt.appointmentCreated:pt.rescheduled);setBooking(undefined);setSelected(id);}}/>}
  </>;
}
