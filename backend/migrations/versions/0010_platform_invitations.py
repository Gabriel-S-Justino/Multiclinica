"""Invite global operators without clinic memberships."""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

SIGNATURE = "public.activate_platform_operator(uuid,text,text,text,text,integer)"


def upgrade() -> None:
    op.execute("""
        CREATE TABLE public.platform_invitations (
            id uuid PRIMARY KEY,
            issuer_id uuid NOT NULL REFERENCES public.platform_operators(user_id),
            recipient_hash varchar(64) NOT NULL,
            proof_hash varchar(64) NOT NULL,
            expires_at timestamptz NOT NULL,
            accepted_at timestamptz
        )
    """)
    op.execute("ALTER TABLE public.platform_invitations ENABLE ROW LEVEL SECURITY")
    op.execute("GRANT SELECT, INSERT ON public.platform_invitations TO clinic_runtime")
    op.execute("""
        CREATE POLICY platform_invitation_issue ON public.platform_invitations FOR INSERT
        WITH CHECK (
            public.is_platform_actor()
            AND issuer_id::text = current_setting('app.user_id', true)
            AND accepted_at IS NULL
        )
    """)
    op.execute("""
        CREATE POLICY platform_invitation_recipient ON public.platform_invitations FOR SELECT
        USING (
            proof_hash = current_setting('app.platform_invite_proof', true)
            AND recipient_hash = current_setting('app.invite_recipient', true)
        )
    """)
    op.execute("""
        CREATE FUNCTION public.activate_platform_operator(
            p_invite uuid, p_login text, p_recipient text,
            p_password text, p_mfa text, p_step integer
        ) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public
        AS $fn$
        DECLARE
            new_user uuid;
        BEGIN
            PERFORM pg_advisory_xact_lock(128019, 1);
            IF NOT EXISTS (
                SELECT 1 FROM public.platform_invitations i
                JOIN public.platform_operators p ON p.user_id = i.issuer_id
                JOIN public.users u ON u.id = p.user_id
                WHERE i.id = p_invite
                  AND i.recipient_hash = p_recipient
                  AND i.recipient_hash = current_setting('app.invite_recipient', true)
                  AND i.proof_hash = current_setting('app.platform_invite_proof', true)
                  AND i.accepted_at IS NULL AND i.expires_at > clock_timestamp()
                  AND p.active AND u.active AND u.deleted_at IS NULL
            ) OR p_password NOT LIKE '$argon2id$%'
              OR length(p_mfa) NOT BETWEEN 1 AND 512
              OR p_step < 0
            THEN RETURN NULL; END IF;

            INSERT INTO public.users (id, login, password_hash, active, mfa_secret, last_totp_step)
            VALUES (gen_random_uuid(), p_login, p_password, true, p_mfa, p_step)
            ON CONFLICT (login) DO NOTHING
            RETURNING id INTO new_user;
            IF new_user IS NULL THEN RETURN NULL; END IF;

            INSERT INTO public.platform_operators(user_id, active) VALUES (new_user, true);
            UPDATE public.platform_invitations SET accepted_at = clock_timestamp()
            WHERE id = p_invite;
            RETURN new_user;
        END
        $fn$
    """)
    op.execute(f"REVOKE ALL ON FUNCTION {SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {SIGNATURE} TO clinic_runtime")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {SIGNATURE}")
    op.execute("DROP TABLE public.platform_invitations")
