# Threat model STRIDE

F1: controles planejados, sem alegação de segurança validada. Fronteiras: internet→webhook/API, portal→sessão, API→banco, dispatcher→consumidor, backend→provedores e Superadmin→tenant.

| Classe | Ameaça | Controle proposto | Evidência requerida |
|---|---|---|---|
| Spoofing | Sessão roubada, webhook forjado, dependente falso | MFA, rotação, assinatura corpo bruto, vínculo verificado | Sessão revogada; assinatura inválida; dependente sem vínculo negado |
| Tampering | tenant_id/papel alterado, slot adulterado, replay | Contexto servidor, schemas extra=forbid, RBAC/RLS, idempotência e versões | BOLA por endpoint, payload divergente e replay |
| Repudiation | Alteração de agenda ou break-glass sem autoria | Auditoria append-only e correlation ID, exportação protegida | Runtime não atualiza/apaga auditoria; ações rastreáveis |
| Information disclosure | Logs/IA/cache revelam PII, clínica cruzada | Minimização, cifra de campo, no-store, RLS, cache escopado, segredos write-only | Canary de segredo, isolamento, payload do modelo minimizado |
| Denial of service | Spam, brute force, filas/custos sem limite | Rate limit compartilhado, payload limitado, quotas, timeout, retry limitado e DLQ | Carga, bloqueio de autenticação, cota concorrente |
| Elevation of privilege | Prompt injection, bypass de papéis, owner de banco | Ferramentas por estado, autorização independente, runtime sem privilégios elevados | Chamadas maliciosas diretas e suíte adversária com zero violações |

ORM/SQL parametrizado e allowlists de ordenação; nenhuma execução de código/shell a partir de entrada. Renderizar texto React, sem HTML de paciente. CSP sem scripts arbitrários, nosniff, Referrer-Policy e frame-ancestors; política exata será ajustada ao build. URLs de integração fixas por adaptador; sem fetch de URL livre, redirects desabilitados ou destinos revalidados. Sem uploads no MVP.

Sessões/CSRF/CORS seguem [permissões](users-and-permissions.md). Sem CORS wildcard com credenciais. Cookies não são usados para autenticar jobs/webhooks. RLS não substitui escopo de profissional/fila. Todas as tabelas clínicas e jobs devem testar tenant ausente, inválido e reutilização de conexão.

Criptografia proposta: AEAD com nonce único e associated data contendo tenant/tabela/id; key_version e rotação por ambiente. Busca por HMAC normalizado com chave separada, nunca hash simples de telefone/CPF. Provedor de chaves e biblioteca serão escolhidos na F2/F7; não implementar criptografia própria. Logs excluem payload, tokens, cookies, senhas e dados clínicos. `.env` ignorado; exemplos apenas fictícios.

Riscos residuais: prova de identidade e autorização de dependentes ainda não aprovadas; fornecedor com entrega ambígua pode duplicar mensagem; nenhum teste elimina todos os riscos de IA; políticas legais/backup/retentivas ainda pendentes. Scans sem achados não equivalem a certificação.

## Atualização F2 — 31/10/2026

Este documento conserva o design completo da F1. O subconjunto implementado e validado nesta fase, com limites e comandos, está em [foundation.md](foundation.md) e no [relatório F2](reports/f2-foundation.md). Funcionalidades futuras aqui descritas não foram declaradas implementadas.


## Atualização F3 — 31/10/2026

A F3 acrescenta exclusão de intervalos, triggers/locks transacionais, search_path fixo em funções, RLS nas novas entidades, cifra AEAD vinculada ao tenant e validação independente dos casos de uso. Ver [evidências F3](reports/f3-scheduling.md). Não representa certificação ou teste de produção.
