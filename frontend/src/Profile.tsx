import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from './api';
import { pt } from './locales';
import { Failure, Feedback, Label, Loading, Modal, useAction } from './ui';

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

async function profileJpeg(file: File) {
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

export function Profile({ onClose, onPassword }: { onClose: () => void; onPassword: () => void }) {
  const query = useQuery({ queryKey: ['own-profile'], queryFn: () => api<ProfileData>('/auth/profile'), retry: false });
  const action = useAction();
  const [photoRevision, setPhotoRevision] = useState(0);
  const [photoError, setPhotoError] = useState(false);

  async function savePhoto(file: File | null) {
    setPhotoError(false);
    await action.run(async () => {
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

  return <Modal title={pt.myAccount} onClose={onClose}>
    <Feedback action={action} />
    {query.isPending ? <Loading /> : query.isError ? <Failure error={query.error} /> : <>
      <div className="profile-photo">
        {query.data.has_photo && <img src={`/v1/auth/profile/photo?v=${photoRevision}`} alt="Foto do perfil" width={80} height={80} />}
        <Label text="Foto do perfil" hint="JPG, PNG ou WebP de até 10 MB">
          <input type="file" accept="image/jpeg,image/png,image/webp" disabled={action.busy}
            onChange={event => { const file = event.currentTarget.files?.[0]; event.currentTarget.value = ''; if (file) void savePhoto(file); }} />
        </Label>
        {query.data.has_photo && <button type="button" className="secondary" disabled={action.busy} onClick={() => void savePhoto(null)}>Remover foto</button>}
      </div>
      {photoError && <p className="feedback error" role="alert">Escolha uma imagem válida em JPG, PNG ou WebP de até 10 MB.</p>}
      <form className="form-grid" onSubmit={event => {
        event.preventDefault();
        const details = profileFields(event.currentTarget);
        void action.run(async () => { await api('/auth/profile', details, 'PUT'); await query.refetch(); }, pt.saved);
      }}>
        <Label text={pt.login}><input readOnly value={query.data.login} /></Label>
        <ProfileFields initial={query.data.details} email={query.data.login.includes('@') ? query.data.login : undefined} />
        <div className="form-actions wide">
          <button type="button" className="secondary" onClick={onPassword}>{pt.changeOwnPassword}</button>
          <button disabled={action.busy}>{pt.save}</button>
        </div>
      </form>
    </>}
  </Modal>;
}
