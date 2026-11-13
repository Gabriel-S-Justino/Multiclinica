# F8 · staging publicado e verificação remota

Registro histórico. O estado vigente está no [guia de implantação](../integration-onboarding.md) e nas [permissões atuais](../users-and-permissions.md).

Alvo confirmado: `clbrfrancaa/projeto-extensao-staging`, ID `prj_ncn1i5U1cQNjjLQxIeurJh54rtL1`, plano Hobby. Framework FastAPI, Node 24.x, Python 3.12 e região proposta de função `gru1`. Origem reservada verificada pela API: `https://projeto-extensao-staging.vercel.app`.

## Banco e configuração

Após o aceite de termos pelo usuário, o recurso Neon gratuito `projeto-extensao-staging-db` foi provisionado: projeto `soft-river-49089920`, recurso `store_xsKrSIdqzywOTpZ4`, plano `free_v3`, região `gru1`, sem Neon Auth/realtime. Banco inicialmente vazio; PostgreSQL remoto 18.6. Nenhum paciente real foi usado.

Papéis `clinic_migrator` e `clinic_runtime` foram criados por SQL, sem associação a `neon_superuser`, sem superuser/BYPASSRLS/CREATEROLE/CREATEDB. Migrações Alembic aplicadas por conexão direta ao revision `0005`. Verificação da conexão pooled real confirmou runtime sem propriedade de tabelas, sem CREATE no schema e sem UPDATE na auditoria.

A conexão automática da integração injetava credenciais de `neondb_owner`, que tem bypass de RLS. Depois de provisionar o banco e preparar os papéis, a injeção automática foi desconectada do projeto, preservando o recurso e os dados. O preview recebeu somente seis variáveis da aplicação: `APP_ENV=staging`, `PUBLIC_ORIGIN`, `MFA_REQUIRED=true` como configuração; `DATABASE_URL` do runtime, `TOKEN_KEY` e `FIELD_KEY` como Secret. Nenhuma URL de migração/admin foi enviada ao deploy. Valores privados permanecem somente em `.local/` ignorado; não foram exibidos.

Dry-run de deploy identificou FastAPI e confirmou exclusão de `.env.local`, `.local`, `.tools`, `.venv`, `.vercel`, testes e documentos. O build recria `public` a partir do Vite; a publicação também inclui os três arquivos gerados locais, conferidos byte a byte com `frontend/dist`, para disponibilização no CDN. O script local de login foi corrigido para reconhecer tanto `loggedIn:false` quanto o retorno autenticado com `username`/`team`.

## Verificação e estado

Fases anteriores: 148 testes Python, 3 componentes e 1 fluxo Chromium aprovados; backup/restore real local aprovado. Isso é histórico local, não teste do destino remoto. Secret scan e sintaxe PowerShell passaram após a preparação de staging.

O histórico abaixo registra a autorização, o primeiro problema de publicação e sua resolução. A seção final contém a verificação remota concluída. Não há ativação de WhatsApp, IA nem produção clínica neste passo.

## Histórico do primeiro deploy · autorização específica posteriormente concedida

O envio de Preview a partir do commit local `2f72fdb52658` foi recusado pela CLI com `first_deployment_production`: o primeiro deploy de um projeto Vercel deve usar o canal Production. Não ocorreu upload/deploy bem-sucedido.

Foi preparada a configuração do mesmo projeto isolado para esse canal, mantendo `APP_ENV=staging`, MFA e o banco de testes. A revisão automática rejeitou a gravação das seis variáveis em Production porque o escopo anterior era Preview e exigiu autorização explícita do usuário para a mudança material de ambiente/exposição. A ação não foi executada; uma leitura posterior confirmou zero variáveis nesse canal. Nenhum contorno da rejeição foi aplicado.

A aprovação necessária cobre gravar as seis variáveis da aplicação e fazer o primeiro deploy no canal Production **somente** de `clbrfrancaa/projeto-extensao-staging`, com a URL reservada deste staging. Isso não implica habilitar WhatsApp, IA, dados reais ou uma produção clínica. A continuidade de implementação permanece autorizada; esta aprovação específica é exigida pela revisão automática para o canal remoto diferente.

## Primeiro deploy e ajuste dos arquivos estáticos

O usuário aprovou especificamente o canal Production deste projeto isolado. As seis variáveis foram configuradas nesse canal com `APP_ENV=staging`; o primeiro deploy do commit `65fe8f2cf825` atingiu READY. A URL fixa respondeu `200` em `/v1/health` e `/v1/ready`, com sessão anônima rejeitada em `/v1/auth/session` (`401`). A URL imutável do deploy preservou a proteção da Vercel. Não houve desativação de proteção.

A página inicial retornou 404. Os logs comprovaram Python 3.12, instalação de dependências e build Vite executados, mas `public` constava da exclusão de publicação. A exclusão foi removida para permitir o CDN da Vercel; o preparador passou a remover apenas assets gerados obsoletos, validando os caminhos antes da remoção. O build local e a presença/hashes dos arquivos estáticos foram verificados antes do novo envio. O estado READY sozinho não foi tratado como validação ponta a ponta.

Foi criada uma clínica de demonstração claramente identificada como sintética, com administrador de MFA e parâmetros exclusivos de teste. Credenciais aleatórias permanecem em arquivo privado local, sem envio ao chat. Nenhuma configuração foi interpretada como política real de clínica.

## Resultado remoto · 31/10/2026

URL de demonstração: **https://projeto-extensao-staging.vercel.app**. Deploy `dpl_Gpsvo82nQwDS5rJSsQ74XXDZEFQY`, estado READY, fonte `e3c29f3b90cec2232a9026ff4467c986b973647b`. O canal Vercel é Production somente porque o serviço exige esse canal para iniciar o projeto; a aplicação e o banco continuam exclusivamente de staging (`APP_ENV=staging`).

HTTP real confirmou página HTML, JavaScript e CSS com `200`, tipos de conteúdo corretos, nosniff e CSP com scripts da própria origem, sem unsafe-inline. Health/readiness retornaram `200`; sessão anônima, `401`. A URL imutável preservou redirecionamento à autenticação Vercel (`302`). A URL fixa apresenta o login da aplicação. Evidência: [staging-http-checks.json](staging-http-checks.json).

Um fluxo Chromium isolado executou contra a aplicação publicada e o Neon real, sem mocks: senha → desafio obrigatório MFA → seleção de clínica → revisão e confirmação de agendamento → verificação manual de vínculo sintético → remarcação → cancelamento. Leituras autenticadas confirmaram no banco os estados `rescheduled` e `canceled`. Também passou registrar atendimento, assumir conversa, registrar resposta na outbox, devolver ao bot e consultar auditoria. Nenhuma mensagem foi enviada a um provedor.

O primeiro ensaio encontrou um seletor de teste ambíguo entre feedback e carregamento; somente o teste foi ajustado. Outro ensaio foi corretamente bloqueado pela fila sintética sem expediente; o seed foi corrigido para horários de demonstração, sem alterar regras da aplicação. O fluxo final passou por completo, com zero respostas API de erro durante as operações. Registros sintéticos dos ensaios permanecem na clínica de demonstração.

Logout invalidou a sessão (`401` posterior), com localStorage vazio. Axe WCAG 2 A/AA e 2.1 AA não encontrou violações nas telas verificadas: agenda desktop, revisão e agenda mobile (390 × 844). Isso não equivale a auditoria completa de acessibilidade. Evidência: [staging-smoke-evidence.json](staging-smoke-evidence.json); capturas [desktop](staging-agenda-desktop.png), [revisão](staging-review.png) e [mobile](staging-agenda-mobile.png).

As instruções de acesso, senha aleatória e segredo para cadastrar o autenticador estão somente no arquivo privado local `.local/staging-access.md`, ignorado pelo Git e pelo deploy. Não copiar seu conteúdo para issues, documentação pública ou chat. Código e relatórios estão em commits locais da branch `codex/staging-delivery`; não houve push para GitHub nesta etapa.

## Limitações e próximos passos de operação

- O portal de demonstração foi verificado; o produto completo ainda não atende os critérios de produção clínica.
- WhatsApp não tem canal/credenciais Meta nem entrega externa verificada. A resposta da inbox fica na fila. Worker durável e agendamento com latência medida continuam pendentes de implantação/configuração.
- IA continua desligada; faltam provedor, modelo, contrato, orçamento e políticas aprovadas.
- Permanecem revisão clínica/jurídica, retenção/direitos automatizados, backup/restauração no destino, carga/cold start remoto e confirmação dos limites operacionais do plano. O ensaio de restauração anterior foi local.
- Os 11 achados moderados de ferramentas npm continuam registrados; a auditoria de dependências de produção retornou zero achados na consulta realizada. Nenhuma certificação de segurança ou conformidade é afirmada.

## Fontes

Consultadas em 31/10/2026: [papéis Neon](https://github.com/neondatabase/website/blob/main/content/docs/manage/roles.md) · papéis criados por Console/API/CLI recebem `neon_superuser`; SQL permite papéis limitados; [acesso ao banco](https://github.com/neondatabase/website/blob/main/content/docs/manage/database-access.md); [regiões Vercel](https://vercel.com/docs/functions/configuring-functions/region); [referência de integração Vercel](https://vercel.com/docs/integrations/create-integration/vercel-api-integrations). Os limites do plano foram lidos da instalação real, sem upgrade ou contratação paga.
