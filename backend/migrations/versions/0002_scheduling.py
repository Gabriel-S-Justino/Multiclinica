"""Scheduling, verified links, conversation transaction and durable outbox."""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TABLES = [
    "contacts",
    "idempotency_records",
    "outbox",
    "patients",
    "services",
    "contact_patient_links",
    "conversations",
    "holidays",
    "professional_schedules",
    "professional_services",
    "schedule_exceptions",
    "appointment_holds",
    "blocked_periods",
    "conversation_state",
    "service_resources",
    "appointments",
    "appointment_transitions",
    "booking_resources",
]
DDL = [
    "\nCREATE TABLE contacts (\n\tphone_ciphertext VARCHAR(1024) NOT NULL, \n\tphone_hash VARCHAR(64) NOT NULL, \n\tactive BOOLEAN NOT NULL, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tUNIQUE (tenant_id, phone_hash), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_contacts_tenant_id ON contacts (tenant_id)",
    "\nCREATE TABLE idempotency_records (\n\tkey VARCHAR(128) NOT NULL, \n\tactor_id UUID NOT NULL, \n\toperation VARCHAR(30) NOT NULL, \n\trequest_hash VARCHAR(64) NOT NULL, \n\tresult JSONB NOT NULL, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tUNIQUE (tenant_id, key), \n\tFOREIGN KEY(actor_id) REFERENCES users (id), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_idempotency_records_tenant_id ON idempotency_records (tenant_id)",
    "\nCREATE TABLE outbox (\n\tevent_key VARCHAR(180) NOT NULL, \n\tevent_type VARCHAR(60) NOT NULL, \n\taggregate_id UUID NOT NULL, \n\tpayload JSONB NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tUNIQUE (tenant_id, event_key), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_outbox_tenant_id ON outbox (tenant_id)",
    "\nCREATE TABLE patients (\n\tname_ciphertext VARCHAR(2048) NOT NULL, \n\tbirth_date_ciphertext VARCHAR(1024), \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_patients_tenant_id ON patients (tenant_id)",
    "\nCREATE TABLE services (\n\tname VARCHAR(120) NOT NULL, \n\tactive BOOLEAN NOT NULL, \n\trequires_professional BOOLEAN NOT NULL, \n\tpolicy_validated BOOLEAN NOT NULL, \n\trequires_birth_date BOOLEAN NOT NULL, \n\tduration_minutes INTEGER NOT NULL, \n\tstep_minutes INTEGER NOT NULL, \n\tbuffer_before INTEGER NOT NULL, \n\tbuffer_after INTEGER NOT NULL, \n\tmin_notice_minutes INTEGER NOT NULL, \n\tcancellation_notice_minutes INTEGER NOT NULL, \n\treschedule_notice_minutes INTEGER NOT NULL, \n\thorizon_days INTEGER NOT NULL, \n\tmax_reschedules INTEGER NOT NULL, \n\thold_ttl_minutes INTEGER NOT NULL, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tCHECK (duration_minutes BETWEEN 1 AND 720 AND step_minutes BETWEEN 1 AND 720), \n\tCHECK (buffer_before BETWEEN 0 AND 240 AND buffer_after BETWEEN 0 AND 240), \n\tCHECK (min_notice_minutes >= 0 AND cancellation_notice_minutes >= 0 AND reschedule_notice_minutes >= 0), \n\tCHECK (horizon_days BETWEEN 1 AND 365 AND max_reschedules >= 0 AND hold_ttl_minutes BETWEEN 1 AND 60), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_services_tenant_id ON services (tenant_id)",
    "\nCREATE TABLE contact_patient_links (\n\tcontact_id UUID NOT NULL, \n\tpatient_id UUID NOT NULL, \n\trelationship VARCHAR(30) NOT NULL, \n\tverification_method VARCHAR(30), \n\tverified_at TIMESTAMP WITH TIME ZONE, \n\tverified_until TIMESTAMP WITH TIME ZONE, \n\tverified_by UUID, \n\trevoked BOOLEAN NOT NULL, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tUNIQUE (tenant_id, contact_id, patient_id), \n\tFOREIGN KEY(tenant_id, contact_id) REFERENCES contacts (tenant_id, id), \n\tFOREIGN KEY(tenant_id, patient_id) REFERENCES patients (tenant_id, id), \n\tFOREIGN KEY(verified_by) REFERENCES users (id), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_contact_patient_links_tenant_id ON contact_patient_links (tenant_id)",
    "\nCREATE TABLE conversations (\n\tcontact_id UUID NOT NULL, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tFOREIGN KEY(tenant_id, contact_id) REFERENCES contacts (tenant_id, id), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_conversations_tenant_id ON conversations (tenant_id)",
    "\nCREATE TABLE holidays (\n\tunit_id UUID, \n\tday DATE NOT NULL, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tFOREIGN KEY(tenant_id, unit_id) REFERENCES units (tenant_id, id), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_holidays_day ON holidays (day)",
    "CREATE INDEX ix_holidays_tenant_id ON holidays (tenant_id)",
    "\nCREATE TABLE professional_schedules (\n\tprofessional_id UUID NOT NULL, \n\tunit_id UUID NOT NULL, \n\tweekday INTEGER NOT NULL, \n\tstart_minute INTEGER NOT NULL, \n\tend_minute INTEGER NOT NULL, \n\tvalid_from DATE NOT NULL, \n\tvalid_until DATE, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tFOREIGN KEY(tenant_id, professional_id) REFERENCES professionals (tenant_id, id), \n\tFOREIGN KEY(tenant_id, unit_id) REFERENCES units (tenant_id, id), \n\tCHECK (weekday BETWEEN 0 AND 6), \n\tCHECK (start_minute >= 0 AND start_minute < end_minute AND end_minute <= 1440), \n\tCHECK (valid_until IS NULL OR valid_until >= valid_from), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_professional_schedules_tenant_id ON professional_schedules (tenant_id)",
    "CREATE INDEX ix_professional_schedules_professional_id ON professional_schedules (professional_id)",
    "\nCREATE TABLE professional_services (\n\tprofessional_id UUID NOT NULL, \n\tservice_id UUID NOT NULL, \n\tactive BOOLEAN NOT NULL, \n\tduration_minutes INTEGER, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tUNIQUE (tenant_id, professional_id, service_id), \n\tFOREIGN KEY(tenant_id, professional_id) REFERENCES professionals (tenant_id, id), \n\tFOREIGN KEY(tenant_id, service_id) REFERENCES services (tenant_id, id), \n\tCHECK (duration_minutes IS NULL OR duration_minutes BETWEEN 1 AND 720), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_professional_services_tenant_id ON professional_services (tenant_id)",
    "\nCREATE TABLE schedule_exceptions (\n\tprofessional_id UUID NOT NULL, \n\tunit_id UUID NOT NULL, \n\tday DATE NOT NULL, \n\tclosed BOOLEAN NOT NULL, \n\tstart_minute INTEGER, \n\tend_minute INTEGER, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tFOREIGN KEY(tenant_id, professional_id) REFERENCES professionals (tenant_id, id), \n\tFOREIGN KEY(tenant_id, unit_id) REFERENCES units (tenant_id, id), \n\tCHECK ((closed AND start_minute IS NULL AND end_minute IS NULL) OR (NOT closed AND start_minute IS NOT NULL AND end_minute IS NOT NULL AND start_minute >= 0 AND end_minute > start_minute AND end_minute <= 1440)), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_schedule_exceptions_tenant_id ON schedule_exceptions (tenant_id)",
    "CREATE INDEX ix_schedule_exceptions_professional_id ON schedule_exceptions (professional_id)",
    "\nCREATE TABLE appointment_holds (\n\towner_user_id UUID NOT NULL, \n\tstate VARCHAR(20) NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tconversation_id UUID, \n\treplaces_appointment_id UUID, \n\tprofessional_id UUID NOT NULL, \n\tservice_id UUID NOT NULL, \n\tunit_id UUID NOT NULL, \n\tcontact_id UUID NOT NULL, \n\tstarts_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tends_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tduration_minutes INTEGER NOT NULL, \n\tbuffer_before INTEGER NOT NULL, \n\tbuffer_after INTEGER NOT NULL, \n\toccupied_start TIMESTAMP WITH TIME ZONE NOT NULL, \n\toccupied_end TIMESTAMP WITH TIME ZONE NOT NULL, \n\toccupied_period TSTZRANGE GENERATED ALWAYS AS (tstzrange(occupied_start, occupied_end, '[)')) STORED NOT NULL, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tFOREIGN KEY(tenant_id, professional_id) REFERENCES professionals (tenant_id, id), \n\tFOREIGN KEY(tenant_id, service_id) REFERENCES services (tenant_id, id), \n\tFOREIGN KEY(tenant_id, unit_id) REFERENCES units (tenant_id, id), \n\tFOREIGN KEY(tenant_id, contact_id) REFERENCES contacts (tenant_id, id), \n\tCHECK (duration_minutes BETWEEN 1 AND 720 AND buffer_before BETWEEN 0 AND 240 AND buffer_after BETWEEN 0 AND 240), \n\tCHECK (ends_at = starts_at + duration_minutes * interval '1 minute' AND occupied_start = starts_at - buffer_before * interval '1 minute' AND occupied_end = ends_at + buffer_after * interval '1 minute'), \n\tFOREIGN KEY(tenant_id, conversation_id) REFERENCES conversations (tenant_id, id), \n\tCHECK (state IN ('held','released','consumed')), \n\tFOREIGN KEY(owner_user_id) REFERENCES users (id), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_appointment_holds_tenant_id ON appointment_holds (tenant_id)",
    "CREATE INDEX ix_hold_active ON appointment_holds (tenant_id, professional_id, expires_at)",
    "CREATE INDEX ix_appointment_holds_professional_id ON appointment_holds (professional_id)",
    "\nCREATE TABLE blocked_periods (\n\tunit_id UUID, \n\tprofessional_id UUID, \n\tresource_id UUID, \n\tstarts_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tends_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tFOREIGN KEY(tenant_id, unit_id) REFERENCES units (tenant_id, id), \n\tFOREIGN KEY(tenant_id, professional_id) REFERENCES professionals (tenant_id, id), \n\tFOREIGN KEY(tenant_id, resource_id) REFERENCES resources (tenant_id, id), \n\tCHECK (ends_at > starts_at), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_blocked_periods_tenant_id ON blocked_periods (tenant_id)",
    "CREATE INDEX ix_blocked_periods_professional_id ON blocked_periods (professional_id)",
    "\nCREATE TABLE conversation_state (\n\tconversation_id UUID NOT NULL, \n\tstate VARCHAR(40) NOT NULL, \n\tversion INTEGER NOT NULL, \n\tcontext JSONB NOT NULL, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tUNIQUE (tenant_id, conversation_id), \n\tFOREIGN KEY(tenant_id, conversation_id) REFERENCES conversations (tenant_id, id), \n\tCHECK (version >= 0), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_conversation_state_tenant_id ON conversation_state (tenant_id)",
    "\nCREATE TABLE service_resources (\n\tservice_id UUID NOT NULL, \n\tresource_id UUID NOT NULL, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tUNIQUE (tenant_id, service_id, resource_id), \n\tFOREIGN KEY(tenant_id, service_id) REFERENCES services (tenant_id, id), \n\tFOREIGN KEY(tenant_id, resource_id) REFERENCES resources (tenant_id, id), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_service_resources_tenant_id ON service_resources (tenant_id)",
    "\nCREATE TABLE appointments (\n\tpatient_id UUID NOT NULL, \n\tsource_hold_id UUID NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tversion INTEGER NOT NULL, \n\treschedule_count INTEGER NOT NULL, \n\treplaced_by_id UUID, \n\tprofessional_id UUID NOT NULL, \n\tservice_id UUID NOT NULL, \n\tunit_id UUID NOT NULL, \n\tcontact_id UUID NOT NULL, \n\tstarts_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tends_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tduration_minutes INTEGER NOT NULL, \n\tbuffer_before INTEGER NOT NULL, \n\tbuffer_after INTEGER NOT NULL, \n\toccupied_start TIMESTAMP WITH TIME ZONE NOT NULL, \n\toccupied_end TIMESTAMP WITH TIME ZONE NOT NULL, \n\toccupied_period TSTZRANGE GENERATED ALWAYS AS (tstzrange(occupied_start, occupied_end, '[)')) STORED NOT NULL, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tFOREIGN KEY(tenant_id, professional_id) REFERENCES professionals (tenant_id, id), \n\tFOREIGN KEY(tenant_id, service_id) REFERENCES services (tenant_id, id), \n\tFOREIGN KEY(tenant_id, unit_id) REFERENCES units (tenant_id, id), \n\tFOREIGN KEY(tenant_id, contact_id) REFERENCES contacts (tenant_id, id), \n\tCHECK (duration_minutes BETWEEN 1 AND 720 AND buffer_before BETWEEN 0 AND 240 AND buffer_after BETWEEN 0 AND 240), \n\tCHECK (ends_at = starts_at + duration_minutes * interval '1 minute' AND occupied_start = starts_at - buffer_before * interval '1 minute' AND occupied_end = ends_at + buffer_after * interval '1 minute'), \n\tFOREIGN KEY(tenant_id, patient_id) REFERENCES patients (tenant_id, id), \n\tFOREIGN KEY(tenant_id, source_hold_id) REFERENCES appointment_holds (tenant_id, id), \n\tFOREIGN KEY(tenant_id, replaced_by_id) REFERENCES appointments (tenant_id, id) DEFERRABLE INITIALLY DEFERRED, \n\tUNIQUE (tenant_id, source_hold_id), \n\tCHECK (status IN ('scheduled','confirmed','completed','canceled','no_show','rescheduled')), \n\tCHECK (version >= 0 AND reschedule_count >= 0), \n\tCHECK ((status = 'rescheduled') = (replaced_by_id IS NOT NULL)), \n\tCONSTRAINT appointments_no_overlap EXCLUDE USING gist (tenant_id WITH =, professional_id WITH =, occupied_period WITH &&) WHERE (status IN ('scheduled','confirmed')), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_appointments_tenant_id ON appointments (tenant_id)",
    "CREATE INDEX ix_appointments_professional_id ON appointments (professional_id)",
    "\nCREATE TABLE appointment_transitions (\n\tappointment_id UUID NOT NULL, \n\tfrom_status VARCHAR(20), \n\tto_status VARCHAR(20) NOT NULL, \n\tactor_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tFOREIGN KEY(tenant_id, appointment_id) REFERENCES appointments (tenant_id, id), \n\tFOREIGN KEY(actor_id) REFERENCES users (id), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_appointment_transitions_tenant_id ON appointment_transitions (tenant_id)",
    "\nCREATE TABLE booking_resources (\n\tresource_id UUID NOT NULL, \n\thold_id UUID, \n\tappointment_id UUID, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tFOREIGN KEY(tenant_id, resource_id) REFERENCES resources (tenant_id, id), \n\tFOREIGN KEY(tenant_id, hold_id) REFERENCES appointment_holds (tenant_id, id), \n\tFOREIGN KEY(tenant_id, appointment_id) REFERENCES appointments (tenant_id, id), \n\tCHECK ((hold_id IS NOT NULL) <> (appointment_id IS NOT NULL)), \n\tUNIQUE (tenant_id, hold_id, resource_id), \n\tUNIQUE (tenant_id, appointment_id, resource_id), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_booking_resources_resource_id ON booking_resources (resource_id)",
    "CREATE INDEX ix_booking_resources_tenant_id ON booking_resources (tenant_id)",
]

LOCK_FUNCTION = """
CREATE FUNCTION lock_schedule(t uuid) RETURNS void LANGUAGE sql VOLATILE AS $$
  SELECT pg_advisory_xact_lock(hashtextextended('clinic-schedule:' || t::text, 0));
$$
"""

BOOKING_GUARD = """
CREATE FUNCTION guard_booking() RETURNS trigger LANGUAGE plpgsql VOLATILE AS $$
DECLARE live boolean; kind text; excluded_appointment uuid;
BEGIN
  PERFORM lock_schedule(NEW.tenant_id);
  kind := CASE WHEN TG_TABLE_NAME='appointment_holds' THEN 'hold' ELSE 'appointment' END;
  IF TG_OP='UPDATE' THEN
    IF ROW(NEW.id,NEW.tenant_id,NEW.professional_id,NEW.unit_id,NEW.contact_id,NEW.service_id,
           NEW.starts_at,NEW.ends_at,NEW.duration_minutes,NEW.buffer_before,NEW.buffer_after,
           NEW.occupied_start,NEW.occupied_end)
       IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.professional_id,OLD.unit_id,OLD.contact_id,OLD.service_id,
           OLD.starts_at,OLD.ends_at,OLD.duration_minutes,OLD.buffer_before,OLD.buffer_after,
           OLD.occupied_start,OLD.occupied_end) THEN
      RAISE EXCEPTION 'immutable_booking' USING ERRCODE='23514';
    END IF;
    IF kind='hold' THEN
      IF NEW.expires_at IS DISTINCT FROM OLD.expires_at OR NEW.owner_user_id<>OLD.owner_user_id
        OR NEW.conversation_id IS DISTINCT FROM OLD.conversation_id
        OR NEW.replaces_appointment_id IS DISTINCT FROM OLD.replaces_appointment_id
        OR (NEW.state<>OLD.state AND (OLD.state<>'held' OR NEW.state NOT IN ('released','consumed'))) THEN
        RAISE EXCEPTION 'invalid_hold_transition' USING ERRCODE='23514';
      END IF;
    ELSE
      IF NEW.patient_id<>OLD.patient_id OR NEW.source_hold_id<>OLD.source_hold_id
        OR NEW.reschedule_count<>OLD.reschedule_count
        OR (NEW.status=OLD.status AND ROW(NEW.version,NEW.replaced_by_id) IS DISTINCT FROM ROW(OLD.version,OLD.replaced_by_id))
        OR (NEW.status<>OLD.status AND (OLD.status NOT IN ('scheduled','confirmed')
            OR NEW.status NOT IN ('confirmed','completed','canceled','no_show','rescheduled')
            OR NEW.version<>OLD.version+1))
        OR (NEW.status IN ('completed','no_show') AND clock_timestamp()<NEW.starts_at) THEN
        RAISE EXCEPTION 'invalid_appointment_transition' USING ERRCODE='23514';
      END IF;
    END IF;
  ELSIF kind='appointment' THEN
    IF NEW.status<>'scheduled' OR NOT EXISTS (
      SELECT 1 FROM appointment_holds h WHERE h.tenant_id=NEW.tenant_id AND h.id=NEW.source_hold_id
      AND h.state='consumed' AND h.professional_id=NEW.professional_id AND h.service_id=NEW.service_id
      AND h.unit_id=NEW.unit_id AND h.contact_id=NEW.contact_id
      AND h.starts_at=NEW.starts_at AND h.ends_at=NEW.ends_at
      AND ((h.replaces_appointment_id IS NULL AND NEW.reschedule_count=0) OR EXISTS (
        SELECT 1 FROM appointments predecessor WHERE predecessor.tenant_id=NEW.tenant_id
        AND predecessor.id=h.replaces_appointment_id AND predecessor.status='rescheduled' AND predecessor.replaced_by_id=NEW.id
        AND NEW.reschedule_count=predecessor.reschedule_count+1))
    ) THEN RAISE EXCEPTION 'invalid_source_hold' USING ERRCODE='23514'; END IF;
  END IF;
  IF kind='hold' THEN
    excluded_appointment := NEW.replaces_appointment_id;
    IF NEW.replaces_appointment_id IS NOT NULL AND NOT EXISTS (
      SELECT 1 FROM appointments a WHERE a.tenant_id=NEW.tenant_id AND a.id=NEW.replaces_appointment_id
      AND a.contact_id=NEW.contact_id AND a.service_id=NEW.service_id AND a.status IN ('scheduled','confirmed')
    ) AND NEW.state='held' THEN RAISE EXCEPTION 'invalid_replacement_hold' USING ERRCODE='23514'; END IF;
    live := NEW.state='held' AND NEW.expires_at>clock_timestamp();
  ELSE live := NEW.status IN ('scheduled','confirmed'); END IF;
  IF NOT live THEN RETURN NEW; END IF;
  IF EXISTS (SELECT 1 FROM appointments a WHERE a.tenant_id=NEW.tenant_id
      AND a.professional_id=NEW.professional_id AND a.status IN ('scheduled','confirmed')
      AND (kind<>'appointment' OR a.id<>NEW.id)
      AND a.id IS DISTINCT FROM excluded_appointment
      AND tstzrange(a.occupied_start,a.occupied_end,'[)') && tstzrange(NEW.occupied_start,NEW.occupied_end,'[)'))
    OR EXISTS (SELECT 1 FROM appointment_holds h WHERE h.tenant_id=NEW.tenant_id
      AND h.professional_id=NEW.professional_id AND h.state='held' AND h.expires_at>clock_timestamp()
      AND (kind<>'hold' OR h.id<>NEW.id)
      AND tstzrange(h.occupied_start,h.occupied_end,'[)') && tstzrange(NEW.occupied_start,NEW.occupied_end,'[)')) THEN
    RAISE EXCEPTION 'booking_conflict' USING ERRCODE='23P01';
  END IF;
  RETURN NEW;
END $$
"""

RESOURCE_GUARD = """
CREATE FUNCTION guard_booking_resource() RETURNS trigger LANGUAGE plpgsql VOLATILE AS $$
DECLARE target_start timestamptz; target_end timestamptz; target_unit uuid; live boolean; excluded_appointment uuid;
BEGIN
  PERFORM lock_schedule(NEW.tenant_id);
  IF TG_OP='UPDATE' THEN
    IF NEW.tenant_id<>OLD.tenant_id OR NEW.resource_id<>OLD.resource_id
       OR OLD.appointment_id IS NOT NULL OR NEW.appointment_id IS NULL OR NEW.hold_id IS NOT NULL
       OR NOT EXISTS (SELECT 1 FROM appointments a WHERE a.tenant_id=NEW.tenant_id
                      AND a.id=NEW.appointment_id AND a.source_hold_id=OLD.hold_id) THEN
      RAISE EXCEPTION 'invalid_resource_transfer' USING ERRCODE='23514';
    END IF;
  END IF;
  IF NEW.hold_id IS NOT NULL THEN
    SELECT occupied_start,occupied_end,unit_id,state='held' AND expires_at>clock_timestamp(),replaces_appointment_id
      INTO target_start,target_end,target_unit,live,excluded_appointment FROM appointment_holds
      WHERE tenant_id=NEW.tenant_id AND id=NEW.hold_id;
  ELSE
    SELECT occupied_start,occupied_end,unit_id,status IN ('scheduled','confirmed')
      INTO target_start,target_end,target_unit,live FROM appointments
      WHERE tenant_id=NEW.tenant_id AND id=NEW.appointment_id;
  END IF;
  IF target_start IS NULL OR NOT EXISTS (SELECT 1 FROM resources r WHERE r.tenant_id=NEW.tenant_id
      AND r.id=NEW.resource_id AND r.unit_id=target_unit AND r.active) THEN
    RAISE EXCEPTION 'invalid_resource' USING ERRCODE='23514';
  END IF;
  IF NOT live THEN RETURN NEW; END IF;
  IF EXISTS (SELECT 1 FROM booking_resources br JOIN appointments a
      ON a.tenant_id=br.tenant_id AND a.id=br.appointment_id
      WHERE br.tenant_id=NEW.tenant_id AND br.resource_id=NEW.resource_id
      AND (NEW.appointment_id IS NULL OR a.id<>NEW.appointment_id)
      AND a.id IS DISTINCT FROM excluded_appointment
      AND a.status IN ('scheduled','confirmed')
      AND tstzrange(a.occupied_start,a.occupied_end,'[)') && tstzrange(target_start,target_end,'[)'))
    OR EXISTS (SELECT 1 FROM booking_resources br JOIN appointment_holds h
      ON h.tenant_id=br.tenant_id AND h.id=br.hold_id
      WHERE br.tenant_id=NEW.tenant_id AND br.resource_id=NEW.resource_id
      AND (NEW.hold_id IS NULL OR h.id<>NEW.hold_id)
      AND h.state='held' AND h.expires_at>clock_timestamp()
      AND tstzrange(h.occupied_start,h.occupied_end,'[)') && tstzrange(target_start,target_end,'[)')) THEN
    RAISE EXCEPTION 'resource_conflict' USING ERRCODE='23P01';
  END IF;
  RETURN NEW;
END $$
"""

CONFIG_GUARD = """
CREATE FUNCTION lock_schedule_configuration() RETURNS trigger LANGUAGE plpgsql VOLATILE AS $$
BEGIN
  IF TG_OP='DELETE' THEN PERFORM lock_schedule(OLD.tenant_id); RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND NEW.tenant_id<>OLD.tenant_id THEN
    RAISE EXCEPTION 'immutable_tenant' USING ERRCODE='23514';
  END IF;
  PERFORM lock_schedule(NEW.tenant_id); RETURN NEW;
END $$
"""

CONFIG_TABLES = [
    "services",
    "professional_services",
    "service_resources",
    "professional_schedules",
    "schedule_exceptions",
    "blocked_periods",
    "holidays",
    "professionals",
    "units",
    "resources",
]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    for statement in DDL:
        op.execute(statement)
    op.execute(
        "ALTER TABLE appointment_holds ADD CONSTRAINT hold_replacement_fk FOREIGN KEY(tenant_id,replaces_appointment_id) REFERENCES appointments(tenant_id,id) DEFERRABLE INITIALLY DEFERRED"
    )
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} USING (tenant_id::text=current_setting('app.tenant_id',true)) WITH CHECK (tenant_id::text=current_setting('app.tenant_id',true))"
        )
        op.execute(f"REVOKE ALL ON {table} FROM PUBLIC")
        op.execute(f"GRANT SELECT ON {table} TO clinic_runtime")
    for table in [
        "contacts",
        "patients",
        "contact_patient_links",
        "appointment_transitions",
        "outbox",
        "idempotency_records",
    ]:
        op.execute(f"GRANT INSERT ON {table} TO clinic_runtime")
    for table in [
        "appointment_holds",
        "appointments",
        "conversation_state",
        "conversations",
        "booking_resources",
    ]:
        op.execute(f"GRANT INSERT, UPDATE ON {table} TO clinic_runtime")
    for statement in (LOCK_FUNCTION, BOOKING_GUARD, RESOURCE_GUARD, CONFIG_GUARD):
        op.execute(statement)
    op.execute("REVOKE ALL ON FUNCTION lock_schedule(uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION lock_schedule(uuid) TO clinic_runtime")
    op.execute("ALTER FUNCTION lock_schedule(uuid) SET search_path TO pg_catalog,public,pg_temp")
    for function in ["guard_booking", "guard_booking_resource", "lock_schedule_configuration"]:
        op.execute(f"ALTER FUNCTION {function}() SET search_path TO pg_catalog,public,pg_temp")
        op.execute(f"REVOKE ALL ON FUNCTION {function}() FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {function}() TO clinic_runtime")
    for table in ["appointment_holds", "appointments"]:
        op.execute(
            f"CREATE TRIGGER booking_integrity BEFORE INSERT OR UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION guard_booking()"
        )
    op.execute(
        "CREATE TRIGGER resource_integrity BEFORE INSERT OR UPDATE ON booking_resources FOR EACH ROW EXECUTE FUNCTION guard_booking_resource()"
    )
    for table in CONFIG_TABLES:
        op.execute(
            f"CREATE TRIGGER schedule_configuration_lock BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION lock_schedule_configuration()"
        )


def downgrade() -> None:
    op.execute("ALTER TABLE appointment_holds DROP CONSTRAINT hold_replacement_fk")
    for table in CONFIG_TABLES:
        op.execute(f"DROP TRIGGER schedule_configuration_lock ON {table}")
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
    for function in ["guard_booking", "guard_booking_resource", "lock_schedule_configuration"]:
        op.execute(f"DROP FUNCTION {function}()")
    op.execute("DROP FUNCTION lock_schedule(uuid)")
    # Do not drop btree_gist: it may have been provisioned before this migration.
