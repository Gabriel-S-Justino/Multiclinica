import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, render, screen, fireEvent, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { App } from './App';
import { MemoryRouter } from 'react-router-dom';

function mount(path = '/') {return render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></QueryClientProvider>);}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
test('exibe login acessível e falha sem revelar a resposta do servidor', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response('{}', { status: 401 })).mockResolvedValueOnce(new Response('{"secret":"private"}', { status: 401 }))); // pragma: allowlist secret (resposta sintética)
  mount();
  fireEvent.change(await screen.findByLabelText('Identificação'), {target:{value:'operator'}});
  fireEvent.change(screen.getByLabelText('Senha'), {target:{value:'incorrect'}});
  fireEvent.click(screen.getByRole('button', {name:'Entrar'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível concluir');
  expect(screen.queryByText('private')).not.toBeInTheDocument();
});

test('renderiza nome externo como texto e não como HTML', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url:string)=>new Response(JSON.stringify(url.endsWith('/auth/session')?{user_id:'u',active_membership_id:'m',memberships:[{id:'m',tenant_id:'t',role:'collaborator',capabilities:['agenda.read']}]}:url.endsWith('/portal/catalog')?{timezone:'America/Sao_Paulo',services:[],professionals:[],units:[],resources:[]}:url.endsWith('/professionals')?{items:[{id:'p',display_name:'<img src=x onerror=alert(1)>',active:true}]}:{items:[]}))));
  const view = mount();
  expect(await screen.findByText('<img src=x onerror=alert(1)>')).toBeInTheDocument();
  expect(view.container.querySelector('img')).toBeNull();
});

test('oculta rotas administrativas quando o servidor não concede a capacidade', async()=>{
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.endsWith('/auth/session')?{user_id:'u',active_membership_id:'m',memberships:[{id:'m',tenant_id:'t',role:'admin',capabilities:[]}]}:{items:[]}))));
  mount();
  expect(await screen.findByRole('heading',{name:'Este acesso não está disponível para o seu perfil.'})).toBeInTheDocument();
  expect(screen.queryByRole('link',{name:'Serviços'})).not.toBeInTheDocument();
});

test('abre as seções da plataforma pelo menu lateral do Superadmin', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(
    url.endsWith('/auth/session')
      ? {user_id:'u', active_membership_id:null, memberships:[], platform_access:true}
      : {items:[]}
  ))));
  mount('/clinics');
  const sidebar = await screen.findByRole('navigation', {name:'Administração da plataforma'});
  await screen.findByRole('heading', {name:'Visão geral', level:1});
  for (const section of ['Clínicas', 'Usuários', 'Auditoria']) {
    const link = within(sidebar).getByRole('link', {name:section});
    fireEvent.click(link);
    expect(await screen.findByRole('heading', {name:section, level:1})).toBeInTheDocument();
    expect(link).toHaveAttribute('aria-current', 'page');
    if (section === 'Usuários') {
      expect(screen.getByRole('button', {name:'Cadastrar Superadmin'})).toBeInTheDocument();
    }
  }
});
