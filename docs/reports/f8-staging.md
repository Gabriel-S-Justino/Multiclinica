# F8 — preparação e verificação de staging

Alvo confirmado: `clbrfrancaa/projeto-extensao-staging`, ID `prj_ncn1i5U1cQNjjLQxIeurJh54rtL1`, plano Hobby. Framework FastAPI, Node 24.x, Python 3.12 e região proposta de função `gru1`. Origem reservada verificada pela API: `https://projeto-extensao-staging.vercel.app`.

## Banco e configuração

Após o aceite de termos pelo usuário, o recurso Neon gratuito `projeto-extensao-staging-db` foi provisionado: projeto `soft-river-49089920`, recurso `store_xsKrSIdqzywOTpZ4`, plano `free_v3`, região `gru1`, sem Neon Auth/realtime. Banco inicialmente vazio; PostgreSQL remoto 18.6. Nenhum paciente real foi usado.

Papéis `clinic_migrator` e `clinic_runtime` foram criados por SQL, sem associação a `neon_superuser`, sem superuser/BYPASSRLS/CREATEROLE/CREATEDB. Migrações Alembic aplicadas por conexão direta ao revision `0005`. Verificação da conexão pooled real confirmou runtime sem propriedade de tabelas, sem CREATE no schema e sem UPDATE na auditoria.

A conexão automática da integração injetava credenciais de `neondb_owner`, que tem bypass de RLS. Depois de provisionar o banco e preparar os papéis, a injeção automática foi desconectada do projeto, preservando o recurso e os dados. O preview recebeu somente seis variáveis da aplicação: `APP_ENV=staging`, `PUBLIC_ORIGIN`, `MFA_REQUIRED=true` como configuração; `DATABASE_URL` do runtime, `TOKEN_KEY` e `FIELD_KEY` como Secret. Nenhuma URL de migração/admin foi enviada ao deploy. Valores privados permanecem somente em `.local/` ignorado; não foram exibidos.

Dry-run de deploy identificou FastAPI e confirmou exclusão de `.env.local`, `.local`, `.tools`, `.venv`, `.vercel`, testes e documentos. Artefatos gerados `frontend/dist`/`public` são recriados pelo build remoto para evitar enviar versões antigas. O script local de login foi corrigido para reconhecer tanto `loggedIn:false` quanto o retorno autenticado com `username`/`team`.

## Verificação e estado

Fases anteriores: 148 testes Python, 3 componentes e 1 fluxo Chromium aprovados; backup/restore real local aprovado. Isso é histórico local, não teste do destino remoto. Secret scan e sintaxe PowerShell passaram após a preparação de staging.

Deploy e verificações remotas serão registrados abaixo quando executados. Não há ativação de WhatsApp, IA nem produção clínica neste passo.

## Primeiro deploy — autorização específica pendente

O envio de Preview a partir do commit local `2f72fdb52658` foi recusado pela CLI com `first_deployment_production`: o primeiro deploy de um projeto Vercel deve usar o canal Production. Não ocorreu upload/deploy bem-sucedido.

Foi preparada a configuração do mesmo projeto isolado para esse canal, mantendo `APP_ENV=staging`, MFA e o banco de testes. A revisão automática rejeitou a gravação das seis variáveis em Production porque o escopo anterior era Preview e exigiu autorização explícita do usuário para a mudança material de ambiente/exposição. A ação não foi executada; uma leitura posterior confirmou zero variáveis nesse canal. Nenhum contorno da rejeição foi aplicado.

A aprovação necessária cobre gravar as seis variáveis da aplicação e fazer o primeiro deploy no canal Production **somente** de `clbrfrancaa/projeto-extensao-staging`, com a URL reservada deste staging. Isso não implica habilitar WhatsApp, IA, dados reais ou uma produção clínica. A continuidade de implementação permanece autorizada; esta aprovação específica é exigida pela revisão automática para o canal remoto diferente.

## Primeiro deploy e ajuste dos arquivos estáticos

O usuário aprovou especificamente o canal Production deste projeto isolado. As seis variáveis foram configuradas nesse canal com `APP_ENV=staging`; o primeiro deploy do commit `65fe8f2cf825` atingiu READY. A URL fixa respondeu `200` em `/v1/health` e `/v1/ready`, com sessão anônima rejeitada em `/v1/auth/session` (`401`). A URL imutável do deploy preservou a proteção da Vercel. Não houve desativação de proteção.

A página inicial retornou 404. Os logs comprovaram Python 3.12, instalação de dependências e build Vite executados, mas `public` constava da exclusão de publicação. A exclusão foi removida para permitir o CDN da Vercel; o preparador passou a remover apenas assets gerados obsoletos, validando os caminhos antes da remoção. O build local e a presença/hashes dos arquivos estáticos foram verificados antes do novo envio. O estado READY sozinho não foi tratado como validação ponta a ponta.

Foi criada uma clínica de demonstração claramente identificada como sintética, com administrador de MFA e parâmetros exclusivos de teste. Credenciais aleatórias permanecem em arquivo privado local, sem envio ao chat. Nenhuma configuração foi interpretada como política real de clínica.

## Fontes

Consultadas em 31/10/2026: [papéis Neon](https://github.com/neondatabase/website/blob/main/content/docs/manage/roles.md) — papéis criados por Console/API/CLI recebem `neon_superuser`; SQL permite papéis limitados; [acesso ao banco](https://github.com/neondatabase/website/blob/main/content/docs/manage/database-access.md); [regiões Vercel](https://vercel.com/docs/functions/configuring-functions/region); [referência de integração Vercel](https://vercel.com/docs/integrations/create-integration/vercel-api-integrations). Os limites do plano foram lidos da instalação real, sem upgrade ou contratação paga.
