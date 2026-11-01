# ADR 0003 — Detalhes da fundação F2

Data: 31/10/2026. Status: implementado localmente, submetido ao gate F2.

- Python 3.12 e SQLAlchemy 2.0 estável, dependências exatas nos locks. Sync/NullPool, prepare_threshold=None conforme ADR 0002; testes reais executados em PostgreSQL local, sem alegar validação de pool Neon.
- Papéis fixos do MVP são enum/check constraint e funções de autorização explícitas. Editor/catálogo dinâmico de permissões fica adiado; F4 mantém os mesmos papéis e não ganha permissão implicitamente.
- Unidades e recursos entram na primeira migração, capacidade unitária validada por constraint. CRUD de gestão é posterior.
- Cookies Secure com prefixo __Host e CSRF. HTTPS local via plugin de desenvolvimento; origem única. Não depender de compartilhamento de cookies entre projetos vercel.app.
- Sem provedor de e-mail definido, recuperação é operacional: token emitido por CLI após verificação humana e entregue por canal privado. Endpoint não alega envio; confirmação é transacional, expira e revoga sessões. Não habilitar reset de MFA por senha apenas.
- Roteador frontend adiado até existir segunda página; TanStack Query já implementado. Evita dependência sem uso.
- Testes podem desabilitar MFA somente com APP_ENV=test; ambientes reais recusam configuração desabilitada. Cenário de MFA/replay é testado separadamente no backend.
- CI incluído, mas sem push nesta fase. Resultado Linux e checks remotos permanecem não executados.
