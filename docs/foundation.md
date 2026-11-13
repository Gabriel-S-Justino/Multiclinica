# Fundação implementada · F2

Data: 31/10/2026. Estado: base local implementada; não é MVP completo nem deploy de produção. Ver [relatório F2](reports/f2-foundation.md).

## Dependências e justificativas

Python 3.12, FastAPI/Pydantic para contratos e validação; SQLAlchemy 2.0 + psycopg síncronos, NullPool e prepare_threshold=None para conexões curtas; Alembic para schema congelado e versionado. Argon2id para senhas, pyotp para TOTP e Fernet para segredo MFA. Conteúdo de pacientes ainda não existe: a cifra de mensagens/contexto por tenant será implementada nas fases correspondentes.

React/TypeScript strict + SCSS; TanStack Query para estado remoto e invalidação. Vite para build e HTTPS local; roteador adiado porque a fundação só tem uma tela. Vitest/Testing Library verificam UI; Playwright/axe verificam login completo em navegador. Ruff/mypy/Bandit/detect-secrets/pip-audit e ESLint/npm audit compõem os checks. Versões resolvidas estão em `uv.lock` e `frontend/package-lock.json`; não instalar sem locks em CI.

## Preparação local

Pré-requisitos: Python 3.12, uv, Node 24 e PostgreSQL 17/18. A execução desta sessão usou Python 3.12.14, Node 24.20.0, uv 0.13.5 e PostgreSQL 18.6. Binários temporários de teste ficam em `.tools`, ignorados pelo Git; não são dependência distribuída da aplicação. No Windows foi necessário disponibilizar as DLLs de runtime C++ junto aos binários de teste.

Na raiz:

```powershell
uv sync --frozen --python 3.12
npm --prefix frontend ci --ignore-scripts
Copy-Item .env.example .env
```

Substituir placeholders somente no `.env` privado. Gerar TOKEN_KEY com `secrets.token_hex(32)` e FIELD_KEY com `Fernet.generate_key()` em processo local privado; não colar valores em chat/log/commit. Usar origens HTTPS exatas sem barra final.

No PostgreSQL dedicado de desenvolvimento, provisionar `clinic_migrator` como dono do banco/schema e `clinic_runtime` como LOGIN NOSUPERUSER NOBYPASSRLS, sem herança do papel migrador. Senhas via canal administrativo seguro. A migração pressupõe a existência do papel `clinic_runtime` e deve ser executada pelo migrador, nunca pelo runtime. Não aplicar em banco compartilhado com outros projetos.

```powershell
# Definir MIGRATION_DATABASE_URL apenas no processo controlado de migração.
uv run --frozen alembic upgrade head
```

O Alembic lê essa variável do processo; não carrega `.env` automaticamente. O app lê `.env` via Settings, mas não usa a URL de migração. Em produção, separar completamente as credenciais nos processos/deploys.

Bootstrap operador: `uv run --frozen python -m backend.manage bootstrap --login SEU_LOGIN --tenant-name NOME`. Senha, segredo TOTP provisionado e código são solicitados sem eco. Não há autoinscrição pública. Demais papéis/atribuições serão administrados no portal F4; nenhum usuário padrão é criado.

```powershell
# PUBLIC_ORIGIN=https://localhost:5173 e MFA_REQUIRED=true no ambiente local.
uv run --frozen uvicorn backend.asgi:app --host 127.0.0.1 --port 8000 --no-access-log
# Em outro terminal:
npm --prefix frontend run dev
```

Abrir `https://localhost:5173`. O certificado local é de desenvolvimento; nunca reutilizá-lo em produção. Cookie host-only Secure/HttpOnly para sessão; CSRF em cookie separado legível e header. API via proxy na mesma origem, sem CORS permissivo. Contrato efetivo em `/openapi.json`; não confundir rotas planejadas em api.md com implementadas.

## Dados e permissões desta fase

Migração inicial cria users, tenants, memberships, units, resources (capacidade 1), professionals, professional_assignments, portal_sessions, mfa_challenges, recovery_tokens, rate_limit_buckets e audit_logs. RLS/FORCE para unidades, recursos, profissionais, atribuições e auditoria; contexto transacional, default deny sem tenant. Identidade/sessões/memberships e roteamento administrativo são globais restritos, acessíveis apenas por casos de uso de autenticação. Catálogo de papéis nesta fase é enum verificado no banco/código, sem editor de permissões customizadas.

Runtime não cria/altera clínicas, papéis ou profissionais; só atualiza hash de senha e passo TOTP na identidade. Auditoria não aceita UPDATE/DELETE/TRUNCATE pelo runtime. Acesso de Superadmin a dados profissionais/pacientes permanece negado. Break-glass não está exposto; será implementado com aprovação da clínica em F4.

Sessão: 30 min inativa/8 h absoluta, token opaco HMAC no banco, rotação ao selecionar clínica, revogação no logout/recuperação, MFA obrigatório fora dos testes. Tokens de recuperação de 15 min/uso único podem ser emitidos por CLI operador após verificar identidade: `python -m backend.manage issue-recovery --login SEU_LOGIN`. Saída em arquivo privado fora do repositório, nunca em stdout. Entrega automatizada por e-mail ainda não configurada; endpoint público informa contato com administrador, sem fingir envio.

Limites compartilhados: janela fixa de 5 min, 30 tentativas por IP/escopo e 8 por identidade/desafio/escopo. Contadores commitam mesmo se autenticação falhar. IP vem da conexão direta; validar proxy confiável antes de produção. Limpeza de sessões/desafios/tokens/buckets expirados é pendência operacional antes de produção; não depende dela para negar uso expirado.

## Testes

```powershell
uv run --frozen ruff check backend tests scripts
uv run --frozen ruff format --check backend tests scripts
uv run --frozen mypy backend
uv run --frozen bandit -r backend -q
uv run --frozen python scripts/check_secrets.py
npm --prefix frontend run build
npm --prefix frontend run lint
npm --prefix frontend test
$env:PG_BIN='CAMINHO_DOS_BINARIOS_POSTGRESQL'
$env:RUN_E2E='1'
npm --prefix frontend exec -- playwright install chromium
uv run --frozen python scripts/run_integration.py
```

Runner usa porta livre em loopback, cluster novo e senhas aleatórias, desliga PostgreSQL ao terminar; dados sintéticos ficam em `.local` para inspeção. Requer permissão de iniciar processos/conexões locais. Não usar credenciais reais. Sem TEST_ADMIN_URL, testes de integração são pulados localmente; em CI a ausência falha. Não chamar esse caso de suíte completa.

CI configurado para executar checks, dependências, migrations, banco e navegador em push/PR. Não foi executado no GitHub nesta sessão, pois não houve push. Runner Linux configurado para PostgreSQL 17; o resultado local em Windows/18 não é prova de execução Linux.

## Atualização F3 · 31/10/2026

F2 aprovada. O motor de agendamento F3 e os novos contratos/migrations estão em [scheduling-implementation.md](scheduling-implementation.md). Este documento preserva o escopo da fundação.
