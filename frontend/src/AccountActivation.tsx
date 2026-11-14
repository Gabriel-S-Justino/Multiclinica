import { useEffect, useRef, useState, type FormEvent } from 'react';
import qrcode from 'qrcode-generator';
import { api } from './api';
import { pt } from './locales';
import { ProfileFields, profileFields } from './Profile';
import { Feedback, Icon, Label, Modal, useAction } from './ui';

export function ActivationCode({ code, onClose, hint = pt.activationShare }: {
  code: string; onClose: () => void; hint?: string;
}) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try { await navigator.clipboard.writeText(code); setCopied(true); } catch { setCopied(false); }
  }
  return <Modal title={pt.activationCode} size="narrow" onClose={onClose}>
    <p className="note">{hint}</p>
    <Label text={pt.activationCode}>
      <span className="copy-field">
        <input className="code-display" readOnly value={code} onFocus={event => event.target.select()} />
        <button type="button" className="secondary" onClick={() => void copy()}><Icon name={copied ? 'check' : 'copy'} size={16} />{copied ? 'Copiado' : 'Copiar'}</button>
      </span>
    </Label>
    {copied && <p className="visually-hidden" role="status">Código copiado.</p>}
    <div className="form-actions"><button type="button" onClick={onClose}>Concluir</button></div>
  </Modal>;
}

export function AuthenticatorQr({ login, secret }: { login: string; secret: string }) {
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
    <form onSubmit={submit} className="activation-form">
      {authenticatorKey ? <>
        <ol className="steps" aria-label="Etapas da ativação">
          <li className="done"><span className="step-index" aria-hidden="true"><Icon name="check" size={14} /></span>Convite</li>
          <li className="current" aria-current="step"><span className="step-index" aria-hidden="true">2</span>Configuração</li>
        </ol>
        <fieldset className="activation-step">
          <legend><span className="step-number" aria-hidden="true">1</span>Conecte o autenticador</legend>
          <p className="muted">{pt.activationQrHint}</p>
          <AuthenticatorQr login={login} secret={authenticatorKey} />
          <details className="manual-key">
            <summary>{pt.activationManual}</summary>
            <Label text={pt.activationAuthenticator} hint={pt.activationMfaHint}>
              <input className="code-display" readOnly value={authenticatorKey} onFocus={event => event.target.select()} />
            </Label>
          </details>
        </fieldset>
        <fieldset className="activation-step">
          <legend><span className="step-number" aria-hidden="true">2</span>Seus dados</legend>
          <ProfileFields email={login.includes('@') ? login.trim() : undefined} />
        </fieldset>
        <fieldset className="activation-step">
          <legend><span className="step-number" aria-hidden="true">3</span>Crie sua senha</legend>
          <Label text={pt.newPassword} hint={pt.passwordRule}>
            <input type="password" autoComplete="new-password" minLength={12} maxLength={128}
              required value={password} onChange={event => setPassword(event.target.value)} />
          </Label>
          <Label text={pt.confirmNewPassword}>
            <input type="password" autoComplete="new-password" minLength={12} maxLength={128}
              required value={confirmation} onChange={event => setConfirmation(event.target.value)} />
          </Label>
          {mismatch && <p role="alert" className="feedback error">{pt.passwordMismatch}</p>}
        </fieldset>
        <fieldset className="activation-step">
          <legend><span className="step-number" aria-hidden="true">4</span>Confirme o autenticador</legend>
          <Label text={pt.code} hint="Digite o código de 6 dígitos exibido agora no aplicativo.">
            <input className="code-input" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}"
              maxLength={6} required value={code} onChange={event => setCode(event.target.value)} />
          </Label>
        </fieldset>
      </> : <>
        <p className="note compact">Use o e-mail e o código de ativação recebidos de quem convidou você.</p>
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

/** Reconfiguração do autenticador com código de uso único emitido pela equipe Multiclinica. */
export function AuthenticatorReset({ onAuthenticated }: { onAuthenticated: () => Promise<unknown> }) {
  const action = useAction();
  const [login, setLogin] = useState('');
  const [resetCode, setResetCode] = useState('');
  const [password, setPassword] = useState('');
  const [authenticatorKey, setAuthenticatorKey] = useState('');
  const [code, setCode] = useState('');

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const proof = { login: login.trim(), reset_code: resetCode.trim(), password };
    void action.run(async () => {
      if (!authenticatorKey) {
        const setup = await api<{ authenticator_key: string }>('/auth/mfa/reset/setup', proof);
        setAuthenticatorKey(setup.authenticator_key);
        return;
      }
      await api('/auth/mfa/reset', { ...proof, authenticator_key: authenticatorKey, code });
      setPassword(''); setResetCode(''); setCode(''); setAuthenticatorKey('');
      await onAuthenticated();
    });
  }

  return <>
    <Feedback action={action} />
    <form onSubmit={submit} className="activation-form">
      {authenticatorKey ? <>
        <fieldset className="activation-step">
          <legend><span className="step-number" aria-hidden="true">1</span>{pt.resetScanTitle}</legend>
          <p className="muted">{pt.resetScanHint}</p>
          <AuthenticatorQr login={login} secret={authenticatorKey} />
          <details className="manual-key">
            <summary>{pt.activationManual}</summary>
            <Label text={pt.activationAuthenticator} hint={pt.activationMfaHint}>
              <input className="code-display" readOnly value={authenticatorKey} onFocus={event => event.target.select()} />
            </Label>
          </details>
        </fieldset>
        <fieldset className="activation-step">
          <legend><span className="step-number" aria-hidden="true">2</span>{pt.resetConfirmTitle}</legend>
          <Label text={pt.code} hint={pt.resetConfirmHint}>
            <input className="code-input" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}"
              maxLength={6} required autoFocus value={code} onChange={event => setCode(event.target.value)} />
          </Label>
        </fieldset>
      </> : <>
        <p className="note compact">{pt.resetIntro}</p>
        <Label text={pt.login}>
          <input autoComplete="username" minLength={3} maxLength={254} required value={login} onChange={event => setLogin(event.target.value)} />
        </Label>
        <Label text={pt.password}>
          <input type="password" autoComplete="current-password" maxLength={128} required value={password} onChange={event => setPassword(event.target.value)} />
        </Label>
        <Label text={pt.resetCode} hint={pt.resetCodeHint}>
          <input autoComplete="off" spellCheck={false} minLength={20} maxLength={128} required value={resetCode} onChange={event => setResetCode(event.target.value)} />
        </Label>
      </>}
      <button className="full" disabled={action.busy}>
        {action.busy ? pt.loading : authenticatorKey ? pt.resetFinish : pt.activationStart}
      </button>
    </form>
  </>;
}
