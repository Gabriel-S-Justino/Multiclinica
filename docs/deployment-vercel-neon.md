# Deploy e verificação de capacidades

O [portal Multiclinica](https://multclinicai.vercel.app) e os critérios de operação estão no [roteiro de release](release-runbook.md). A tabela a seguir registra as verificações históricas de design.

| Fonte oficial consultada | Evidência e consequência de design |
|---|---|
| [Vercel FastAPI](https://vercel.com/docs/frameworks/backend/fastapi) | Há suporte documentado a FastAPI; isso não comprova viabilidade da nossa dependência/build/worker. Validar entrypoint e limites no plano real na F2/F8 |
| [Neon connection pooling](https://neon.com/docs/connect/connection-pooling) | Pooling remoto documentado; desenhar transações curtas e não depender de estado de sessão entre transações |
| [PostgreSQL RLS](https://www.postgresql.org/docs/current/ddl-rowsecurity.html) | Políticas restringem linhas; owner normalmente pode contornar. Runtime separado, sem bypass, contexto por transação e testes de negação |
| [PostgreSQL ranges](https://www.postgresql.org/docs/current/rangetypes.html) | Tipos de intervalo e exclusão modelam sobreposição. DDL exato, extensão e concorrência serão testados em PostgreSQL real |

URLs `current` são mutáveis; a consulta retornou documentação PostgreSQL 18, sem fixar a versão do banco do projeto. Nenhuma compatibilidade de versão foi testada. Fontes acima fundamentam capacidades gerais, não limites numéricos nem preços.

Proposta: portal e `/v1` sob mesma origem pública com rewrite controlado; cookies host-only. Não depender de site compartilhado entre projetos `vercel.app`; comportamento de domínio e headers precisa de verificação antes da F2. API privada de consumidor autenticada separadamente. Frontend nunca recebe credenciais de banco/provedores.

Runtime usa URL pooled; migrations usam URL direta e usuário distinto. Variáveis propostas: `APP_ENV`, `DATABASE_URL`, `MIGRATION_DATABASE_URL`, `PUBLIC_ORIGIN`, referências de chaves de cifra/HMAC, configuração de sessão, WhatsApp e IA quando habilitados. Não expor URL de migração ao processo de requisições. Driver, prepared statements, Python suportado, versão de PostgreSQL e disponibilidade de btree_gist devem ser conferidos no ambiente real antes de fixar locks/migrations.

Pendências: tamanho/duração/payload de função, cold starts, cron por plano, região, limites de conexões, preços, PITR/retentiva e garantia de restauração. Não usar processo residente ou BackgroundTasks como garantia durável. Se fila/agendador não atender p95 e retries, propor serviço compatível antes de implementar F5. Build preview não é staging aprovado; ambientes precisam de credenciais e dados distintos.

Release futuro: checks CI → migração controlada compatível → staging → smoke/e2e/carga → revisão → produção autorizada. Rollback exige compatibilidade de schema; sem migration destrutiva automática em requisição.

## Atualização F2 · 31/10/2026

Fontes oficiais consultadas novamente em 31/10/2026: [runtime Python Vercel](https://vercel.com/docs/functions/runtimes/python), [versões FastAPI](https://fastapi.tiangolo.com/deployment/versions/), [dialeto SQLAlchemy/psycopg](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#psycopg), [prepared statements psycopg](https://www.psycopg.org/psycopg3/docs/advanced/prepare.html), [Neon pooling](https://neon.com/docs/connect/connection-pooling) e [Vite](https://vite.dev/guide/). Python 3.12 está listado no runtime Vercel; Neon documenta pooling em modo transação. prepare_threshold=None desabilita preparação automática no driver, escolha conservadora implementada. Isso não substitui teste real no destino, que continua pendente. Lockfiles e execução local comprovam apenas compatibilidade no ambiente testado.

Este documento conserva o design completo da F1. O subconjunto implementado e validado nesta fase, com limites e comandos, está em [foundation.md](foundation.md) e no [relatório F2](reports/f2-foundation.md). Funcionalidades futuras aqui descritas não foram declaradas implementadas.
