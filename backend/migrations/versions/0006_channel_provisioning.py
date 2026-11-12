"""Restrict messaging-channel creation to recently authorized clinic administrators.

Runtime cannot create arbitrary users or memberships; this narrowly-scoped
SECURITY DEFINER operation provisions exactly one noninteractive service actor
and channel for the caller's active clinic, with sending disabled by default.
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE FUNCTION public.provision_clinic_whatsapp_channel(
        p_tenant_id uuid,
        p_queue_id uuid,
        p_phone_number_id text,
        p_account_id text,
        p_graph_version text,
        p_service_password_hash text
    ) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = pg_catalog, public
    AS $function$
    DECLARE
        actor_text text := current_setting('app.user_id', true);
        tenant_text text := current_setting('app.tenant_id', true);
        service_user uuid := gen_random_uuid();
        service_membership uuid := gen_random_uuid();
        new_channel uuid := gen_random_uuid();
    BEGIN
        IF actor_text IS NULL OR actor_text = ''
           OR tenant_text IS NULL OR tenant_text <> p_tenant_id::text
           OR NOT EXISTS (
                SELECT 1 FROM public.memberships m
                JOIN public.users u ON u.id = m.user_id
                JOIN public.tenants t ON t.id = m.tenant_id
                WHERE m.user_id = actor_text::uuid
                  AND m.tenant_id = p_tenant_id
                  AND m.role = 'admin'
                  AND m.active AND u.active AND NOT u.is_service AND t.active
           )
        THEN
            RAISE EXCEPTION 'not_authorized' USING ERRCODE='42501';
        END IF;
        IF p_phone_number_id !~ '^[0-9]{1,80}$'
           OR p_account_id !~ '^[0-9]{1,80}$'
           OR p_graph_version !~ '^v[0-9]{1,3}[.]0$'
           OR length(p_service_password_hash) > 512
           OR p_service_password_hash NOT LIKE '$argon2id$%'
           OR NOT EXISTS (
                SELECT 1 FROM public.service_queues q
                WHERE q.id = p_queue_id AND q.tenant_id = p_tenant_id AND q.active
           )
        THEN
            RAISE EXCEPTION 'invalid_channel_configuration' USING ERRCODE='22023';
        END IF;
        IF EXISTS (SELECT 1 FROM public.messaging_channels WHERE tenant_id = p_tenant_id)
        THEN
            RAISE EXCEPTION 'channel_already_exists' USING ERRCODE='23505';
        END IF;
        INSERT INTO public.users (
            id, login, password_hash, active, last_totp_step, is_service
        ) VALUES (
            service_user, 'service-' || new_channel::text || '@internal.invalid',
            p_service_password_hash, true, -1, true
        );
        INSERT INTO public.memberships (
            id, tenant_id, user_id, role, active, can_manage_schedule
        ) VALUES (
            service_membership, p_tenant_id, service_user, 'messaging', true, false
        );
        INSERT INTO public.messaging_channels (
            id, tenant_id, phone_number_id, account_id, actor_user_id,
            actor_membership_id, default_queue_id, active, send_enabled,
            graph_version, idle_minutes, ambiguity_limit
        ) VALUES (
            new_channel, p_tenant_id, p_phone_number_id, p_account_id, service_user,
            service_membership, p_queue_id, true, false, p_graph_version, 30, 3
        );
        RETURN new_channel;
    END
    $function$;
    """)
    op.execute(
        "REVOKE ALL ON FUNCTION public.provision_clinic_whatsapp_channel("
        "uuid,uuid,text,text,text,text) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.provision_clinic_whatsapp_channel("
        "uuid,uuid,text,text,text,text) TO clinic_runtime"
    )


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION public.provision_clinic_whatsapp_channel(uuid,uuid,text,text,text,text)"
    )
