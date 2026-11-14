import { afterEach, expect, test, vi } from 'vitest';
import { act, cleanup, render, screen, fireEvent, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider, focusManager } from '@tanstack/react-query';
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

test('Minha conta mantém a navegação da plataforma e permite salvar o perfil', async () => {
  const profile = {
    login: 'operator@test.invalid',
    has_photo: false,
    details: {full_name:'Ana Souza', email:'operator@test.invalid', phone:'85999990000'},
  };
  const fetch = vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith('/auth/session')) {
      return Response.json({user_id:'u', active_membership_id:null, memberships:[], platform_access:true});
    }
    if (url.endsWith('/auth/profile') && options?.method === 'PUT') {
      profile.details = JSON.parse(String(options.body));
      return new Response(null, {status:204});
    }
    if (url.endsWith('/auth/profile')) return Response.json(profile);
    return Response.json({items:[]});
  });
  vi.stubGlobal('fetch', fetch);
  mount('/admin/users');
  fireEvent.click(await screen.findByRole('link', {name:'Minha conta'}));
  expect(await screen.findByRole('heading', {name:'Ana Souza'})).toBeInTheDocument();
  expect(screen.getByRole('navigation', {name:'Administração da plataforma'})).toBeInTheDocument();
  expect(screen.getByText('Superadmin')).toBeInTheDocument();
  expect(screen.getByRole('button', {name:'Alterar senha'})).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Nome completo'), {target:{value:'Ana Lima'}});
  fireEvent.click(screen.getByRole('button', {name:'Salvar dados pessoais'}));
  expect(await screen.findByRole('heading', {name:'Ana Lima'})).toBeInTheDocument();
  expect(await screen.findByText('Dados pessoais salvos.')).toBeInTheDocument();
});

test('alterna da clínica para a administração da plataforma pelo seletor lateral', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => Response.json(
    url.endsWith('/auth/session')
      ? {user_id:'u', active_membership_id:'m', platform_access:true, memberships:[{id:'m', tenant_id:'t', role:'admin', clinic_name:'Clínica Teste', capabilities:['agenda.read']}]}
      : url.endsWith('/portal/catalog') ? {timezone:'America/Sao_Paulo', services:[], professionals:[], units:[], resources:[]}
      : url.endsWith('/platform/overview') ? {clinics:1, active_clinics:1, users:2, active_users:2, operators:1}
      : {items:[]}
  )));
  mount('/agenda');
  const select = await screen.findByRole('combobox', {name:'Selecionar clínica'});
  expect(within(select).getByRole('option', {name:'Plataforma'})).toBeInTheDocument();
  fireEvent.change(select, {target:{value:'__platform'}});
  expect(await screen.findByRole('heading', {name:'Visão geral', level:1})).toBeInTheDocument();
  expect(await screen.findByText('1 ativa · 0 inativas')).toBeInTheDocument();
});

test('voltar à aba durante o login mantém a etapa do autenticador e os dados digitados', async () => {
  const delayed401 = () => new Promise<Response>(resolve => setTimeout(() => resolve(new Response('{}', {status:401})), 20));
  vi.stubGlobal('fetch', vi.fn(async (url: string) => url.endsWith('/auth/login')
    ? Response.json({status:'mfa_required', challenge:'c1'})
    : delayed401()));
  mount();
  fireEvent.change(await screen.findByLabelText('Identificação'), {target:{value:'ana@clinica.test'}});
  fireEvent.change(screen.getByLabelText('Senha'), {target:{value:'senha-sintetica-longa'}}); // pragma: allowlist secret (dado sintético)
  fireEvent.click(screen.getByRole('button', {name:'Entrar'}));
  fireEvent.change(await screen.findByLabelText('Código do autenticador'), {target:{value:'123'}});
  await act(async () => {
    focusManager.setFocused(false);
    focusManager.setFocused(true);
    await new Promise(resolve => setTimeout(resolve, 100));
  });
  expect(screen.getByLabelText('Código do autenticador')).toHaveValue('123');
  focusManager.setFocused(undefined);
});

test('pede confirmação antes de descartar alterações de um formulário', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => Response.json(
    url.endsWith('/auth/session')
      ? {user_id:'u', active_membership_id:null, memberships:[], platform_access:true}
      : url.includes('/platform/tenants') ? {items:[{id:'t', name:'Clínica Teste', timezone:'America/Sao_Paulo', active:true, version:1, registration:null}]}
      : {items:[]}
  )));
  mount('/admin/clinics');
  fireEvent.click(await screen.findByRole('button', {name:'Editar'}));
  fireEvent.change(screen.getByLabelText('Nome fantasia'), {target:{value:'Outro nome'}});
  fireEvent.click(screen.getByRole('button', {name:'Cancelar'}));
  expect(await screen.findByRole('heading', {name:'Descartar alterações?'})).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name:'Continuar editando'}));
  expect(screen.getByLabelText('Nome fantasia')).toHaveValue('Outro nome');
  fireEvent.click(screen.getByRole('button', {name:'Cancelar'}));
  fireEvent.click(await screen.findByRole('button', {name:'Descartar'}));
  expect(screen.queryByLabelText('Nome fantasia')).not.toBeInTheDocument();
});
