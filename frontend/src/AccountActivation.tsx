import { useEffect, useRef, useState, type FormEvent } from 'react';
import qrcode from 'qrcode-generator';
import { api } from './api';
import { pt } from './locales';
import { ProfileFields, profileFields } from './Profile';
import { Feedback, Label, Modal, useAction } from './ui';

export function ActivationCode({ code, onClose, hint = pt.activationShare }: {
  code: string; onClose: () => void; hint?: string;
}) {
  return <Modal title={pt.activationCode} size="narrow" onClose={onClose}>
    <p className="note">{hint}</p>
    <Label text={pt.activationCode}>
      <input readOnly value={code} onFocus={event => event.target.select()} />
    </Label>
  </Modal>;
}

function AuthenticatorQr({ login, secret }: { login: string; secret: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const element = canvas.current;
    const context = element?.getContext('2d');
    if (!element || !context) return;

    const issuer = 'Multiclinica';
    const account = Array.from(login.trim().toLowerCase().replaceAll(':', ' ')).slice(0, 80).join('');
    const params = new URLSearchParams({ secret, issuer });
    const uri = `otpauth://totp/${issuer}:${encodeURIComponent(account)}?${params}`;
    const qr = qrcode(0, 'M');
    qr.addData(uri);
    qr.make();

    const modules = qr.getModuleCount();
    const quietZone = 4;
    const scale = 6;
    const size = (modules + quietZone * 2) * scale;
    element.width = element.height = size;
    context.fillStyle = '#fff';
    context.fillRect(0, 0, size, size);
    context.fillStyle = '#000';
    for (let row = 0; row < modules; row++) {
      for (let column = 0; column < modules; column++) {
        if (qr.isDark(row, column)) {
          context.fillRect((column + quietZone) * scale, (row + quietZone) * scale, scale, scale);
        }
      }
    }
  }, [login, secret]);

  return <canvas ref={canvas} className="authenticator-qr" role="img" aria-label={pt.activationQrLabel} />;
}

export function AccountActivation({ onAuthenticated }: { onAuthenticated: () => Promise<unknown> }) {
  const action = useAction();
  const [login, setLogin] = useState('');
  const [activationCode, setActivationCode] = useState('');
  const [authenticatorKey, setAuthenticatorKey] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [code, setCode] = useState('');
  const mismatch = confirmation.length > 0 && password !== confirmation;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mismatch) return;
    const invite = { login, activation_code: activationCode.trim() };
    const profile = authenticatorKey ? profileFields(event.currentTarget) : undefined;
    void action.run(async () => {
      if (!authenticatorKey) {
        const setup = await api<{ authenticator_key: string }>('/auth/activate/setup', invite);
        setAuthenticatorKey(setup.authenticator_key);
        return;
      }
      await api('/auth/activate', { ...invite, password, authenticator_key: authenticatorKey, code, profile });
      setAuthenticatorKey('');
      setPassword('');
      setConfirmation('');
      setCode('');
      setActivationCode('');
      await onAuthenticated();
    });
  }

  return <>
    <Feedback action={action} />
    <form onSubmit={submit}>
      {authenticatorKey ? <>
        <p className="note">{pt.activationQrHint}</p>
        <AuthenticatorQr login={login} secret={authenticatorKey} />
        <details>
          <summary>{pt.activationManual}</summary>
          <Label text={pt.activationAuthenticator} hint={pt.activationMfaHint}>
            <input readOnly value={authenticatorKey} onFocus={event => event.target.select()} />
          </Label>
        </details>
        <ProfileFields email={login.includes('@') ? login.trim() : undefined} />
        <Label text={pt.newPassword} hint={pt.passwordRule}>
          <input type="password" autoComplete="new-password" minLength={12} maxLength={128}
            required value={password} onChange={event => setPassword(event.target.value)} />
        </Label>
        <Label text={pt.confirmNewPassword}>
          <input type="password" autoComplete="new-password" minLength={12} maxLength={128}
            required value={confirmation} onChange={event => setConfirmation(event.target.value)} />
        </Label>
        {mismatch && <p role="alert" className="feedback error">{pt.passwordMismatch}</p>}
        <Label text={pt.code}>
          <input inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}"
            maxLength={6} required value={code} onChange={event => setCode(event.target.value)} />
        </Label>
      </> : <>
        <Label text={pt.login}>
          <input autoComplete="username" minLength={3} maxLength={254}
            required value={login} onChange={event => setLogin(event.target.value)} />
        </Label>
        <Label text={pt.activationCode}>
          <input autoComplete="off" spellCheck={false} maxLength={128}
            required value={activationCode} onChange={event => setActivationCode(event.target.value)} />
        </Label>
      </>}
      <button className="full" disabled={action.busy || mismatch}>
        {action.busy ? pt.loading : authenticatorKey ? pt.activateAccount : pt.activationStart}
      </button>
    </form>
  </>;
}
