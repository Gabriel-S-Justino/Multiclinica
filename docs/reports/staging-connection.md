# Verificação de conexão para staging

31/10/2026. O usuário informou a conclusão da instalação dos plugins. A consulta confirmou Neon e Vercel instalados. Nenhuma ferramenta MCP de acesso às contas foi disponibilizada nesta sessão; foi preparada a alternativa por CLI local, dentro de `.tools/`, ignorada pelo Git.

- Vercel CLI 65.9.0: `whoami --non-interactive --json` retornou `loggedIn: false`, `linkedProject: null`.
- Neon CLI 8.16.0: `profile list -o json` retornou apenas DEFAULT, account `-`, file `missing`.
- Nenhuma variável `NEON_*` ou `VERCEL_*` foi encontrada no processo. Nenhum valor de segredo foi exibido.
- Não foram criados projetos, bancos, branches, recursos pagos, configurações remotas ou deploys.

O script [connect-staging.ps1](../../scripts/connect-staging.ps1) permite ao usuário concluir o login interativo nos dois serviços. Não cria infraestrutura, não solicita tokens pelo chat e não sobrescreve perfis existentes autenticados. Sua sintaxe foi validada pelo parser PowerShell; o login não foi executado pelo agente.

Depois do login: inspecionar times/projetos e confirmar alvo por evidência antes de vincular; preparar staging isolado e verificar variáveis antes de aplicar migrações. A autorização geral de continuidade permanece válida.

Origem da etapa humana: skill Neon determina “An unattended agent must not launch browser authentication.” A skill Vercel CLI orienta que o usuário conclua deliberadamente o fluxo de autenticação. Isso é autenticação de conta, não uma nova aprovação de implementação.

## Correção do assistente de login

Na verificação seguinte, ambas as CLIs continuaram sem autenticação. Foi identificado um erro no script: `vercel whoami --non-interactive --json` devolve código 1 junto de um JSON válido com `loggedIn:false`. O script tratava isso como erro e terminava antes de executar `vercel login`. Corrigido para reconhecer esse estado e prosseguir para login interativo. Sintaxe e decisão de entrada foram verificadas contra a saída real da CLI, sem iniciar autenticação pelo agente. É necessário executar novamente o script corrigido.

Durante essa verificação, as ferramentas do plugin Neon apareceram na sessão, mas `list_projects` e `list_organizations` falharam no conector com `-32001: Unknown tool`. Isso não comprova falha de autenticação da conta conectada; indica que a integração não pôde ser usada nesta sessão. Nenhuma ferramenta Vercel foi disponibilizada. A alternativa CLI permanece preparada, com o tratamento de login corrigido.

## Vercel autenticada e staging vinculado

Verificação seguinte: a CLI Vercel autenticou no escopo `clbrfrancaa`, plano Hobby. O retorno autenticado usa `username`/`team`, sem campo `loggedIn`; o helper foi ajustado para reconhecer os dois formatos, sem repetir login já concluído. Neon CLI permanece sem perfil; o conector MCP continua retornando `Unknown tool`.

O único projeto previamente encontrado era um currículo, sem relação com a aplicação. Foi criado e vinculado um projeto separado, `clbrfrancaa/projeto-extensao-staging`, ID `prj_ncn1i5U1cQNjjLQxIeurJh54rtL1`, na raiz deste checkout. Inspeção posterior confirmou o alvo. Framework FastAPI e Node 24.x foram configurados para corresponder à aplicação testada. `.vercel/project.json` e `.env.local` estão ignorados pelo Git; nenhum valor de credencial foi exibido. Não há deploy.

Foi tentado provisionar a integração Neon com plano `free_v3`, recurso `projeto-extensao-staging-db`, somente ambiente `preview`, região `gru1`, sem Neon Auth/realtime e sem puxar variáveis automaticamente. A CLI devolveu `action_required / integration_terms_acceptance_required`; nenhum banco foi provisionado. O serviço exige aceite humano em [Vercel/Neon](https://vercel.com/clbrfrancaa/~/integrations/accept-terms/neon?source=cli), com links para o adendo do marketplace, política de privacidade e termos Neon. A autorização de execução não foi usada como aceite automático de contrato.

`vercel.json` foi preparado com uma única região `gru1`, próxima ao banco proposto. Fonte oficial consultada em 31/10/2026: [regiões de Functions](https://vercel.com/docs/functions/configuring-functions/region), que documenta configuração por `regions` e uma região no Hobby. Isso é configuração preparada, não evidência de execução remota.

Próximo passo: após o usuário concluir o aceite no navegador, verificar a instalação e repetir o provisionamento gratuito com o mesmo nome/alvo. Somente depois configurar papéis, variáveis privadas e migrações de staging. Não é necessário refazer o login Vercel.
