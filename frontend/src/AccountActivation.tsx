import { useState, type FormEvent } from 'react';
import { api } from './api';
import { pt } from './locales';
import { ProfileFields, profileFields } from './Profile';
import { Feedback, Label, Modal, useAction } from './ui';

export function ActivationCode({ code, onClose }: { code: string; onClose: () => void }) {
  return <Modal title={pt.activationCode} size="narrow" onClose={onClose}>
    <p className="note">{pt.activationShare}</p>
    <Label text={pt.activationCode}>
      <input readOnly value={code} onFocus={event => event.target.select()} />
    </Label>
  </Modal>;
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
        <ProfileFields email={login.includes('@') ? login.trim() : undefined} />
        <Label text={pt.activationAuthenticator} hint={pt.activationMfaHint}>
          <input readOnly value={authenticatorKey} onFocus={event => event.target.select()} />
        </Label>
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
