# Relatório F2 · Fundação

Data: 31/10/2026. F1 aprovada pelo usuário. Entrega local, sujeita ao gate F2; sem push ou deploy.

## Entregue

- Backend em camadas com configuração validada, erros genéricos, limite de payload, headers e logs sem conteúdo sensível.
- PostgreSQL/SQLAlchemy/psycopg, migração Alembic congelada, papéis de runtime/migração separados, RLS e FKs compostas. Unidades/recursos já modelados.
- Login Argon2id, TOTP com proteção contra reutilização, sessão segura, CSRF/Origin, rotação, expiração, logout e recuperação de uso único por procedimento operacional.
- RBAC por clínica/profissional/atribuição, Superadmin sem acesso padrão; auditoria append-only com evento de seleção de clínica.
- Portal mínimo em pt-BR com login/MFA, seleção de clínica, profissionais autorizados, erro/loading/vazio e logout. Ainda sem agenda/inbox/CRUD F4.
- Lockfiles, CI, lint/tipos/testes/SAST, scans de dependências e de segredos. Consulte [execução e decisões](../foundation.md).

## Arquivos

Novos: `backend/`, `frontend/`, `tests/`, `scripts/`, `.github/workflows/ci.yml`, `pyproject.toml`, `uv.lock`, `alembic.ini`, `.env.example`, `.gitignore`, documentação F2 e evidências. README, ADR 0002 e índice/requisitos/testes/deploy são atualizados com o estado real. `.tools`, `.venv`, `.local`, node_modules e certificados de teste ficam ignorados.

## Evidências

Rodada final: **28 testes Python aprovados** (15 casos de integração e 13 unitários); **2 testes de componente** aprovados; **1 e2e real no Chromium** aprovado, incluindo axe com zero violações na tela exercitada. Lint, formatação, tipos, build, SAST e scan de segredos passaram. PostgreSQL real 18.6; migrações passaram. Dependências Python: 71 auditadas sem vulnerabilidades conhecidas; frontend: 11 alertas moderados e nenhum alto/crítico.

Resultados reproduzíveis em `f2-validation.txt` e `f2-integration.txt`. Testes cobrem configuração, senha/HMAC, matriz de papéis, RLS sem contexto e após reutilização de conexão, FK cruzada, negação de alteração de auditoria, CSRF, revogação, MFA/replay, rate limit atômico, recuperação, headers/payload e recusa de runtime privilegiado. Navegador usa API e PostgreSQL reais; axe verifica a tela exercitada, sem alegar conformidade integral WCAG.

Migrações: upgrade do zero, repetição de upgrade com dados preservados, downgrade em banco descartável e novo upgrade. Como só existe uma revisão, não há atualização de schema legado anterior para testar ainda. Falha inicial no SQL do contador e conflito de dependências foram corrigidos antes do relatório final.

## Limitações e riscos

MVP não pronto: agenda/holds/transações F3, portal completo F4, WhatsApp F5 e IA F6 não implementados. Nenhum dado real usado. Nenhum serviço contratado/provisionado; Neon/Vercel continuam sem verificação real. D3/D6/D9/D12/D13/D15 seguem com valores/contratos pendentes. Recuperação automatizada depende de canal verificado; MFA reset exige procedimento futuro, sem bypass web.

Scans: relatório final informa contagem e severidades; alertas moderados de desenvolvimento devem ser acompanhados, sem serem chamados de ausência de vulnerabilidades. Scanner de segredos tem exceções inline restritas a URLs fictícias, rótulo pt-BR e fixtures sintéticas; lockfiles com hashes públicos são excluídos. Scans não certificam segurança. CI foi escrito, não disparado no GitHub. Há aviso de depreciação do adaptador httpx no TestClient; não afeta resultado atual, migração deve ser avaliada em atualização de tooling.

Os 11 alertas moderados vêm de minimatch e dependentes da cadeia ESLint/typescript-eslint, ferramentas de desenvolvimento. Fonte: [GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249), consultada pelo npm audit em 31/10/2026. Não aplicar o downgrade automático sugerido para ESLint 4; acompanhar correção compatível. CI bloqueia alto/crítico, mantendo os moderados visíveis. Relatórios: `f2-python-audit.json` e `f2-frontend-audit.json`.

## Próximo gate

Solicitar aprovação da F2 para F3. Antes de implementar regras dependentes, obter política de identificação/dependentes (D3), antecedências/duração/limite de remarcações por serviço (D9) e validar janela da estratégia LeastFutureLoad. Partes independentes do motor podem usar dados sintéticos explícitos, sem definir política clínica real.
