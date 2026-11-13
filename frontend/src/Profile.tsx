import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from './api';
import { pt } from './locales';
import { ConfirmButton, Failure, Feedback, Icon, Label, Loading, PageHeader, useAction } from './ui';

export type PersonalDetails = {
  full_name: string;
  email: string;
  phone: string;
  job_title: string | null;
  professional_registration: string | null;
};

type ProfileData = { login: string; details: PersonalDetails | null; has_photo: boolean };

export function profileFields(form: HTMLFormElement): PersonalDetails {
  const data = new FormData(form);
  const value = (name: keyof PersonalDetails) => String(data.get(name) ?? '').trim();
  return {
    full_name: value('full_name'), email: value('email'), phone: value('phone'),
    job_title: value('job_title') || null,
    professional_registration: value('professional_registration') || null,
  };
}

export function ProfileFields({ initial, email }: { initial?: PersonalDetails | null; email?: string }) {
  return <>
    <Label text="Nome completo"><input name="full_name" autoComplete="name" required minLength={2} maxLength={120} defaultValue={initial?.full_name} /></Label>
    <Label text="E-mail de contato"><input name="email" type="email" autoComplete="email" required maxLength={254} defaultValue={initial?.email ?? email} /></Label>
    <Label text="Telefone"><input name="phone" type="tel" autoComplete="tel" required maxLength={25} pattern="\+?[0-9 ()\-]{8,24}" defaultValue={initial?.phone} /></Label>
    <Label text="Função ou especialidade (opcional)"><input name="job_title" autoComplete="organization-title" maxLength={120} defaultValue={initial?.job_title ?? ''} /></Label>
    <Label text="Registro profissional (opcional)"><input name="professional_registration" maxLength={120} defaultValue={initial?.professional_registration ?? ''} /></Label>
  </>;
}

export async function profileJpeg(file: File) {
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 10_000_000) {
    throw new Error('invalid_photo');
  }
  const image = await createImageBitmap(file);
  try {
    const canvas = document.createElement('canvas');
    const scale = Math.min(1, 256 / Math.max(image.width, image.height));
    canvas.width = Math.max(1, Math.round(image.width * scale));
    canvas.height = Math.max(1, Math.round(image.height * scale));
    const context = canvas.getContext('2d');
    if (!context) throw new Error('invalid_photo');
    context.fillStyle = '#fff';
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    for (const quality of [0.82, 0.62, 0.42]) {
      const jpeg = canvas.toDataURL('image/jpeg', quality).split(',')[1];
      if (jpeg && jpeg.length <= 60000) return jpeg;
    }
    throw new Error('invalid_photo');
  } finally {
    image.close();
  }
}

export function Profile({ role, onPassword }: { role: string; onPassword: () => void }) {
  const query = useQuery({ queryKey: ['own-profile'], queryFn: () => api<ProfileData>('/auth/profile'), retry: false });
  const action = useAction();
  const photoAction = useAction();
  const [photoRevision, setPhotoRevision] = useState(0);
  const [photoError, setPhotoError] = useState(false);

  async function savePhoto(file: File | null) {
    setPhotoError(false);
    await photoAction.run(async () => {
      let jpeg: string | null = null;
      if (file) {
        try {
          jpeg = await profileJpeg(file);
        } catch {
          setPhotoError(true);
          return;
        }
      }
      await api('/auth/profile/photo', { jpeg }, 'PUT');
      setPhotoRevision(value => value + 1);
      await query.refetch();
    });
  }

  if (query.isPending) return <><PageHeader title={pt.myAccount} /><Loading /></>;
  if (query.isError) return <><PageHeader title={pt.myAccount} /><Failure error={query.error} />
    <button type="button" className="secondary" onClick={() => void query.refetch()}>{pt.refresh}</button></>;

  const { details, login, has_photo: hasPhoto } = query.data;
  const initials = (details?.full_name || login).trim().split(/\s+/).slice(0, 2)
    .map(word => Array.from(word)[0]).join('').toLocaleUpperCase('pt-BR');

  return <div className="account-page">
    <PageHeader title={pt.myAccount} />
    <section className="panel account-identity" aria-label="Identificação da conta">
      <div className="account-identity-main">
        <div className="account-avatar">
          {hasPhoto
            ? <img src={`/v1/auth/profile/photo?v=${photoRevision}`} alt="Foto do perfil" width={88} height={88} />
            : <span aria-hidden="true">{initials}</span>}
        </div>
        <div className="account-identity-text">
          <h2>{details?.full_name || login}</h2>
          {details?.full_name && <p>{login}</p>}
          <p className="account-type"><span>Tipo de usuário</span> <strong>{role}</strong></p>
        </div>
      </div>
      <div className="account-photo-actions">
        <label className="account-file">
          <input className="visually-hidden" type="file" accept="image/jpeg,image/png,image/webp"
            aria-describedby="account-photo-hint" disabled={photoAction.busy}
            onChange={event => {
              const file = event.currentTarget.files?.[0];
              event.currentTarget.value = '';
              if (file) void savePhoto(file);
            }} />
          <span><Icon name="user" size={16} />{hasPhoto ? 'Trocar foto' : 'Adicionar foto'}</span>
        </label>
        {hasPhoto && <ConfirmButton label="Remover foto" title="Remover foto do perfil"
          message="Sua conta passará a exibir as iniciais do seu nome."
          busy={photoAction.busy} onConfirm={() => savePhoto(null)} />}
        <small id="account-photo-hint" className="field-hint">JPG, PNG ou WebP de até 10 MB</small>
      </div>
      {photoAction.busy && <p className="field-hint" role="status">Atualizando foto…</p>}
      <Feedback action={photoAction} />
      {photoError && <p className="feedback error" role="alert">Escolha uma imagem válida em JPG, PNG ou WebP de até 10 MB.</p>}
    </section>
    <div className="account-sections">
      <section className="panel account-details" aria-labelledby="account-details-title">
        <h2 id="account-details-title">Dados pessoais</h2>
        <form className="form-grid" onSubmit={event => {
          event.preventDefault();
          const updated = profileFields(event.currentTarget);
          void action.run(async () => {
            await api('/auth/profile', updated, 'PUT');
            await query.refetch();
          }, 'Dados pessoais salvos.');
        }}>
          <ProfileFields initial={details} email={login.includes('@') ? login : undefined} />
          <div className="form-actions wide"><button disabled={action.busy}>
            {action.busy ? 'Salvando…' : 'Salvar dados pessoais'}
          </button></div>
        </form>
        <Feedback action={action} />
      </section>
      <section className="panel account-security" aria-labelledby="account-security-title">
        <div className="account-security-icon"><Icon name="shield" size={22} /></div>
        <h2 id="account-security-title">Segurança</h2>
        <p className="muted">Use o autenticador para confirmar sua identidade ao entrar.</p>
        <button type="button" className="secondary" onClick={onPassword}><Icon name="lock" size={16} />Alterar senha</button>
      </section>
    </div>
  </div>;
}
