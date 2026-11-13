# Relatório F1 · Design

Data: 31/10/2026. F0 aprovada pelo usuário nesta sessão. F1 documentada, aguardando gate; não houve implementação funcional, provisionamento ou deploy.

## Escopo entregue

Arquitetura/camadas e transações; modelo lógico com entidades/constraints; fluxo determinístico; ciclo de agendamento e locks; RBAC e break-glass; contratos propostos de API e provedores; STRIDE; privacidade, operação, deploy e matriz de testes. D1-D16 mantidos; ADR 0002 propõe escolhas técnicas e resolve ambiguidades da F0 para revisão.

Arquivos criados: `docs/README.md`, `architecture.md`, `data-model.md`, `scheduling.md`, `whatsapp-flow.md`, `users-and-permissions.md`, `api.md`, `security.md`, `ai-provider-setup.md`, `whatsapp-provider-setup.md`, `lgpd.md`, `deployment-vercel-neon.md`, `testing.md`, `operations.md`, `decisions/0002-design.md`, este relatório e `reports/f1-validation.txt`. Alterados: README raiz e status histórico do ADR 0001. Relatório F0 preservado como registro da fase anterior.

## Verificação

Leitura de git status e ADR anterior; consulta oficial de Vercel/FastAPI, Neon/pooling, PostgreSQL/RLS e ranges em 31/10/2026, com links e limites de conclusão registrados no documento de deploy. Validação de presença de documentos, links locais e IDs D1-D16, além de `git diff --check`: resultados em `f1-validation.txt`.

Testes de aplicação/banco não executados: F1 não tem código executável. Nenhuma declaração de concorrência, isolamento, segurança ou deploy validado.

## Pendências e riscos

Gate F1 deve revisar RLS, estratégia sync/NullPool, semântica hold/appointment, locks, RBAC, sessão e break-glass. D6 exige escolha final de fila antes de F5; D3/D9/D12/D13/D15 e políticas de clínica permanecem abertas. Prepared statements, versões/lockfiles e deploy real ainda não verificados. O design de entrega não promete exatamente uma vez no provedor externo.

## Próximo passo proposto

Após aprovação, F2 cria a fundação e CI, fixa versões, implementa configuração/logs, migrações iniciais, autenticação/RBAC/RLS e testes reais de isolamento. Integrações externas e regras clínicas ainda abertas não serão inventadas. Parar no gate F1 conforme seção 0 do Master.md.
