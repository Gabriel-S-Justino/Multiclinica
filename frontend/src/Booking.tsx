import { useEffect, useState } from 'react';
import { api } from './api';
import { pt } from './locales';
import { ConfirmButton, Empty, Failure, Feedback, Icon, Label, Loading, Modal, Status, formatDay, formatLongDay, localDay, timezoneLabel, useAction, useRemote } from './ui';
import type { Appointment, AppointmentReceipt, Catalog, Hold, Membership, Page, PatientOption, Slot, Summary } from './types';

/** Segundos restantes até um instante, atualizados a cada segundo. */
function useSecondsLeft(until?: string) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!until) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [until]);
  return until ? Math.max(0, Math.floor((new Date(until).getTime() - now) / 1000)) : 0;
}

function HoldTimer({seconds, until, timezone}: {seconds: number; until: string; timezone: string}) {
  const clock = new Intl.DateTimeFormat('pt-BR', {hour:'2-digit', minute:'2-digit', timeZone: timezone}).format(new Date(until));
  if (!seconds) return <p className="feedback error" role="alert"><Icon name="alert"/><span>{pt.holdExpired}</span></p>;
  const remaining = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
  return <p className={`note compact hold-timer${seconds <= 60 ? ' is-ending' : ''}`}><Icon name="clock" size={16}/>
    <span>{pt.reservedUntil} {clock}. {pt.timeLeft} <strong className="tabular">{remaining}</strong>.</span></p>;
}

export function Booking({member, original, onClose, onDone}: {member: Membership; original?: Appointment; onClose: () => void; onDone: (id:string) => void}) {
  const catalog = useRemote<Catalog>(member, '/portal/catalog');
  const action = useAction(member);
  const [serviceId, setService] = useState(original?.service_id ?? '');
  const [unitId, setUnit] = useState(original?.unit_id ?? '');
  const [professionalId, setProfessional] = useState(original?.professional_id ?? '');
  const [date, setDate] = useState(original?.local_date ?? localDay(member.timezone));
  const [phone, setPhone] = useState('');
  const [contactId, setContact] = useState(original?.contact_id ?? '');
  const [patients, setPatients] = useState<PatientOption[]>([]);
  const [patientId, setPatient] = useState(original?.patient_id ?? '');
  const [patientName, setPatientName] = useState(original?.patient_name ?? '');
  const [birthDate, setBirthDate] = useState('');
  const [purpose, setPurpose] = useState(false);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [slotCursor, setSlotCursor] = useState<string | null>();
  const [searched, setSearched] = useState(false);
  const [hold, setHold] = useState<Hold>();
  const [summary, setSummary] = useState<Summary>();
  const service = catalog.data?.services.find(item => item.id === serviceId);
  const secondsLeft = useSecondsLeft(summary?.expires_at);

  async function lookup() {
    await action.run(async () => {
      const result = await action.send<{contact_id:string}>('/contacts', {phone});
      const linked = await api<Page<PatientOption>>(`/contacts/${result.contact_id}/patients`);
      setContact(result.contact_id); setPatients(linked.items);
    });
  }
  async function search(cursor?: string | null) {
    await action.run(async () => {
      const query = new URLSearchParams({service_id:serviceId, unit_id:unitId, first_date:date, last_date:date, limit:'25'});
      if (professionalId) query.set('professional_id',professionalId);
      if (cursor) query.set('cursor',cursor);
      const result = await api<Page<Slot>>(`/availability?${query}`);
      setSlots(cursor ? [...slots,...result.items] : result.items); setSlotCursor(result.next_cursor); setSearched(true);
    });
  }
  async function reserve(slot: Slot) {
    await action.run(async () => {
      const result = await action.send<Hold>('/holds', {service_id:serviceId,unit_id:unitId,professional_id:slot.professional_id,
        contact_id:contactId,starts_at:slot.starts_at,
        ...(original ? {reschedule_appointment_id:original.id,appointment_version:original.version} : {})});
      setHold(result);
      setSummary(await api<Summary>(`/holds/${result.hold_id}/summary`));
    });
  }
  async function release() {
    if (hold) await action.run(async () => {await action.send(`/holds/${hold.hold_id}/release`, {hold_id:hold.hold_id,contact_id:contactId}); setHold(undefined); setSummary(undefined);});
  }
  async function confirm() {
    const result = await action.run(async () => {
      if (!hold) throw new Error();
      return original
        ? action.send<AppointmentReceipt>(`/appointments/${original.id}/reschedule`, {appointment_id:original.id,contact_id:contactId,version:original.version,hold_id:hold.hold_id})
        : action.send<AppointmentReceipt>('/appointments', {hold_id:hold.hold_id,contact_id:contactId,
          ...(patientId ? {patient_id:patientId} : {new_patient:{display_name:patientName,purpose_acknowledged:purpose,...(service?.requires_birth_date ? {birth_date:birthDate} : {})}})});
    });
    if (result) onDone(result.appointment_id);
  }
  function close() { if (action.busy) return; if (hold) void action.send(`/holds/${hold.hold_id}/release`, {hold_id:hold.hold_id,contact_id:contactId}).catch(() => undefined); onClose(); }

  const patientReady = !!original || (!!contactId && (!!patientId || (!!patientName.trim() && purpose && (!service?.requires_birth_date || !!birthDate))));
  const searchHint = !contactId ? pt.searchHintContact : !patientReady ? pt.searchHintPatient : !serviceId || !unitId ? pt.searchHintService : '';
  const step = summary ? 3 : patientReady ? 2 : 1;
  const professionalName = (id: string) => catalog.data?.professionals.find(item=>item.id===id)?.display_name;
  function resetContact() { setContact(''); setPatients([]); setPatient(''); setPatientName(''); setPurpose(false); setSlots([]); setSearched(false); }

  return <Modal title={original ? pt.reschedule : pt.newAppointment} onClose={close} size="wide">
    <ol className="steps" aria-label={pt.steps}>{(original ? [pt.stepSlot, pt.stepReview] : [pt.stepPatient, pt.stepSlot, pt.stepReview]).map((label, index) => {
      const number = original ? index + 2 : index + 1;
      return <li key={label} className={number < step ? 'done' : number === step ? 'current' : ''} aria-current={number === step ? 'step' : undefined}><span className="step-index" aria-hidden="true">{number < step ? <Icon name="check" size={14}/> : index + 1}</span>{label}</li>;
    })}</ol>
    {!summary && <p className="muted">{pt.newBookingDescription}</p>}<Feedback action={action}/>
    {catalog.isPending ? <Loading/> : catalog.isError ? <Failure error={catalog.error}/> : summary ? <>
      <h3>{pt.review}</h3><p className="muted">{pt.reviewHint}</p><dl className="review-grid">
        <dt>{pt.patient}</dt><dd>{patientId ? patients.find(item => item.id===patientId)?.display_name ?? patientName : patientName}</dd>
        <dt>{pt.service}</dt><dd>{summary.service_name}</dd><dt>{pt.professional}</dt><dd>{summary.professional_name}</dd>
        <dt>{pt.date}</dt><dd>{formatLongDay(summary.local_date)} · {summary.local_start}</dd><dt>{pt.unit}</dt><dd>{summary.unit_name}</dd>
        <dt>{pt.durationShort}</dt><dd>{summary.duration_minutes} {pt.minutesShort}</dd>
        <dt>{pt.timezone}</dt><dd>{timezoneLabel(summary.timezone)}</dd>
      </dl><HoldTimer seconds={secondsLeft} until={summary.expires_at} timezone={summary.timezone}/>
      <div className="form-actions"><button className="secondary" disabled={action.busy} onClick={() => {
          // Uma reserva expirada já foi liberada pelo servidor; basta voltar à escolha de horário.
          if (secondsLeft) void release(); else { setHold(undefined); setSummary(undefined); setSlots([]); setSearched(false); }
        }}>{secondsLeft ? pt.back : pt.chooseAnotherSlot}</button>
        <button disabled={action.busy || !secondsLeft} onClick={() => void confirm()}>{action.busy ? pt.loading : original ? pt.confirmReschedule : pt.confirmBooking}</button></div>
    </> : <>
      {original ? <div className="context-card"><Icon name="user"/><div><strong>{original.patient_name}</strong><p className="muted">{original.service_name} · {formatDay(original.local_date)} {original.local_start}</p></div></div>
      : <section className="form-section"><h3>{pt.patient}</h3><p className="muted">{pt.contactDifferent}</p>
        {!contactId ? <form onSubmit={(event) => {event.preventDefault(); void lookup();}} className="inline-form">
          <Label text={pt.contactPhone}><input type="tel" autoComplete="off" placeholder="+5511999999999" pattern="\+[1-9][0-9]{7,14}" maxLength={16} required value={phone} onChange={event => setPhone(event.target.value)}/></Label>
          <button disabled={action.busy}>{pt.lookupContact}</button></form> : <>
            <div className="context-card"><Icon name="phone"/><div><span className="muted">{pt.contact}</span><strong>{phone}</strong></div><button type="button" className="text-button" disabled={action.busy} onClick={resetContact}>{pt.changeContact}</button></div>
            <Label text={pt.patient}><select value={patientId} onChange={event => {setPatient(event.target.value); setPatientName(patients.find(item=>item.id===event.target.value)?.display_name ?? '');}}>
              <option value="">{pt.newPatient}</option>{patients.map(item=><option key={item.id} value={item.id}>{item.display_name}</option>)}</select></Label>
            {!patientId && <div className="form-grid"><Label text={pt.patientName}><input autoComplete="off" maxLength={120} required value={patientName} onChange={event=>setPatientName(event.target.value)}/></Label>
              {service?.requires_birth_date && <Label text={pt.birthDate}><input type="date" autoComplete="off" value={birthDate} onChange={event=>setBirthDate(event.target.value)}/></Label>}
              <label className="check wide"><input type="checkbox" checked={purpose} onChange={event=>setPurpose(event.target.checked)}/>{pt.purpose}</label></div>}
          </>}
      </section>}
      {!original && !catalog.data.services.some(item=>item.bookable) && <p className="note"><Icon name="info" size={16}/>{pt.noBookableServices}</p>}
      <form className="form-grid" onSubmit={event=>{event.preventDefault(); void search();}}>
        <Label text={pt.service}><select required disabled={!!original} value={serviceId} onChange={event=>{setService(event.target.value); setSlots([]); setSearched(false);}}><option value="">{pt.select}</option>
          {catalog.data.services.filter(item=>item.bookable || item.id===original?.service_id).map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></Label>
        <Label text={pt.unit}><select required value={unitId} onChange={event=>{setUnit(event.target.value);setSearched(false);setSlots([]);}}><option value="">{pt.select}</option>{catalog.data.units.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></Label>
        <Label text={pt.professional}><select value={professionalId} onChange={event=>{setProfessional(event.target.value);setSlots([]);setSearched(false);}}><option value="">{pt.noPreference}</option>{catalog.data.professionals.filter(item=>item.active).map(item=><option key={item.id} value={item.id}>{item.display_name}</option>)}</select></Label>
        <Label text={pt.date}><input type="date" required min={localDay(member.timezone)} value={date} onChange={event=>{setDate(event.target.value);setSlots([]);setSearched(false);}}/></Label>
        <div className="wide search-row"><button disabled={action.busy || !contactId || !patientReady}>{pt.chooseSlot}</button>{searchHint && <small className="field-hint">{searchHint}</small>}</div>
      </form>
      {searched && <section className="form-section slots-section"><h3>{pt.availableSlots}</h3>{!slots.length ? <Empty icon="calendar">{pt.noSlots}</Empty> : <><p className="muted">{pt.slotHint}</p><div className="slot-list">{slots.map(slot=><button type="button" className="slot secondary" key={`${slot.professional_id}:${slot.starts_at}`} disabled={action.busy} onClick={()=>void reserve(slot)}>
        <strong>{slot.local_start}</strong><span>{professionalName(slot.professional_id)}</span></button>)}</div></>}
        {slotCursor && <button type="button" className="secondary" disabled={action.busy} onClick={()=>void search(slotCursor)}>{pt.more}</button>}</section>}
    </>}
  </Modal>;
}

export function AppointmentDetails({member, appointmentId, onClose, onReschedule}: {member:Membership; appointmentId:string; onClose:()=>void; onReschedule:(appointment:Appointment)=>void}) {
  const result = useRemote<Appointment>(member, `/appointments/${appointmentId}`);
  const action = useAction(member);
  const [mode,setMode] = useState<'details'|'cancel'|'verify'>('details');
  const [relationship,setRelationship] = useState('self');
  const [identity,setIdentity] = useState(false);
  const [authority,setAuthority] = useState(false);
  const [evidence,setEvidence] = useState('');
  const row = result.data;
  async function change(target:string) {
    if (!row) return;
    await action.run(()=>action.send(`/appointments/${row.id}/transitions`,{appointment_id:row.id,contact_id:row.contact_id,version:row.version,target_status:target}),pt.statusUpdated);
  }
  return <Modal title={mode==='verify'?pt.verifyIdentity:mode==='cancel'?pt.cancelAppointment:pt.appointmentDetails} onClose={onClose}>
    <Feedback action={action}/>{result.isPending ? <Loading/> : result.isError ? <Failure error={result.error}/> : row && <>
      <div className="appointment-title"><div><h3>{row.patient_name}</h3><p>{row.service_name}</p></div><Status value={row.status}/></div>
      <dl className="review-grid"><dt>{pt.professional}</dt><dd>{row.professional_name}</dd><dt>{pt.date}</dt><dd>{formatLongDay(row.local_date)}</dd><dt>{pt.time}</dt><dd>{row.local_start} a {row.local_end}</dd><dt>{pt.unit}</dt><dd>{row.unit_name}</dd></dl>
      {mode==='cancel' ? <div className="confirm-box"><h3>{pt.confirmCancelTitle}</h3><p>{pt.cancellationHint}</p><div className="form-actions"><button type="button" className="secondary" disabled={action.busy} onClick={()=>setMode('details')}>{pt.keepAppointment}</button><button className="danger" disabled={action.busy} onClick={()=>void action.run(async()=>{await action.send(`/appointments/${row.id}/cancel`,{appointment_id:row.id,contact_id:row.contact_id,version:row.version});setMode('details');},pt.canceled)}>{pt.cancelConfirm}</button></div></div> : mode==='verify' ? <form className="form-grid" onSubmit={event=>{event.preventDefault();void action.run(async()=>{
        await action.send('/patient-verifications',{patient_id:row.patient_id,contact_id:row.contact_id,relationship,identity_checked:identity,authority_checked:authority,evidence_reference:evidence});setMode('details');
      },pt.verified);}}><p className="wide muted">{pt.identityHint}</p><Label text={pt.relationship}><select value={relationship} onChange={event=>setRelationship(event.target.value)}><option value="self">{pt.self}</option><option value="dependent">{pt.dependent}</option><option value="authorized_other">{pt.authorizedOther}</option></select></Label>
        <Label text={pt.evidence}><input pattern="[A-Za-z0-9._:-]{1,80}" required value={evidence} onChange={event=>setEvidence(event.target.value)} maxLength={80}/></Label>
        <label className="check wide"><input type="checkbox" required checked={identity} onChange={event=>setIdentity(event.target.checked)}/>{pt.identityChecked}</label>
        <label className="check wide"><input type="checkbox" required checked={authority} onChange={event=>setAuthority(event.target.checked)}/>{pt.authorityChecked}</label><div className="form-actions wide"><button type="button" className="secondary" disabled={action.busy} onClick={()=>setMode('details')}>{pt.back}</button><button disabled={action.busy}>{pt.verifyIdentity}</button></div>
      </form> : <div className="form-actions wrap details-actions">
        {row.actions.includes('cancel') && <button className="danger secondary push-left" onClick={()=>setMode('cancel')}>{pt.cancelAppointment}</button>}
        {row.actions.includes('no_show') && <ConfirmButton className="secondary" label={pt.noShow} title={pt.noShowTitle} message={pt.noShowMessage} busy={action.busy} onConfirm={()=>change('no_show')}/>}
        {row.actions.includes('reschedule') && <button className="secondary" onClick={()=>onReschedule(row)}>{pt.reschedule}</button>}
        {row.actions.includes('verify_identity') && <button className="secondary" onClick={()=>setMode('verify')}>{pt.verifyIdentity}</button>}
        {row.actions.includes('complete') && <button disabled={action.busy} onClick={()=>void change('completed')}>{pt.complete}</button>}
        {row.actions.includes('confirm') && <button disabled={action.busy} onClick={()=>void change('confirmed')}>{pt.confirmAttendance}</button>}
      </div>}
    </>}
  </Modal>;
}
