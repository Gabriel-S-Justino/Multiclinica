# Continuidade F5–F8

31/10/2026. O usuário aprovou a F4 e autorizou seguir sem novos gates com "aprove tudo". A autorização foi registrada em ADR 0006. Posteriormente foi publicado e verificado um staging Vercel/Neon gratuito, com autorização específica para o canal remoto exigido. Decisões clínicas/jurídicas e configuração de provedores continuam necessárias. Não houve push, envio WhatsApp ou chamada real de IA. Veja o [resultado remoto da F8](f8-staging.md).

## Estado por fase

| Fase | Implementado nesta continuidade | Limite restante |
|---|---|---|
| F5 | Webhook autenticado, deduplicação persistente, fila cifrada, worker serial, identidade técnica limitada ao contato, menus determinísticos, agendar/cancelar/remarcar, verificação manual, handoff, outbox, janela/opt-out, callbacks, retry/DLQ/unknown | Conta Meta, versão vigente, credenciais/configuração real e teste de entrega no destino; agendador com latência medida |
| F6 | Contrato independente de provedor, schema fechado, intenções sem executor de mutações, filtro determinístico, modo degradado, reserva atômica de tokens por clínica/conversa, metadados sem prompts, suíte adversarial | Adaptador de provedor escolhido e sua ligação ao fluxo, contrato/região/política D13, orçamento monetário, texto clínico fixo aprovado, chamadas reais/qualidade/custo. IA desabilitada |
| F7 | Análise estática, scans, auditorias atuais, testes de isolamento/concorrência/carga local, procedimento de privacidade/incidentes e ensaio de backup/restauração | Revisão clínica/jurídica, direitos/retenção automatizados, resolução de achados npm, carga e restauração no plano remoto; nenhuma certificação de conformidade |
| F8 | Staging Vercel/Neon publicado, runtime limitado, MFA, migrações, build remoto, HTTP e fluxo Chromium reais, acessibilidade desktop/mobile | Agendador/worker remoto, Meta/IA, carga/cold start, restauração no destino e critérios de produção clínica |

## Arquivos e decisões

Backend: novos módulos `webhooks`, `messaging_flow`, `messaging_worker`, `ai_boundary`, `ai_quota`, `whatsapp`, `messaging_models`, CLI e rotas; migrações 0004/0005. Motor F3 agora admite identidade interna de canal/contato com validação de conta técnica, sem ampliar privilégios do portal. Replay de idempotência verifica contato antes de devolver recibo.

Operação: [mensageria](../messaging-implementation.md), [release](../release-runbook.md), [privacidade](../privacy-operations.md), [OpenAPI](../api/openapi.json). ADRs [0006](../decisions/0006-whatsapp.md), [0007](../decisions/0007-ai-boundary.md), [0008](../decisions/0008-hardening-release.md) registram desenhos antes da implementação e condições de ativação.

## Verificação

Resultados finais: **148 testes Python aprovados (88 de integração e 60 unitários)**, **3 testes de componente** e **1 fluxo Chromium** aprovados. Ruff/formatação, mypy (52 módulos), Bandit, scan de segredos, ESLint, tipos, build e git diff passaram (`release-validation.txt`). Acessibilidade axe passou nas telas verificadas, sem equivaler a auditoria completa.

Backup/restauração com PostgreSQL 18.6 real passou, incluindo chave/cifra, schema, RLS e auditoria; o ciclo upgrade com dados/downgrade/upgrade passou. Processos de teste encerrados.

A amostra de carga autenticada usou 100 requisições e 10 workers: p95 de ACK local 247.34 ms, máximo 281.58 ms, 100 eventos persistidos. Isso não mede o worker, a entrega externa, cold start ou a latência do plano remoto.

Evidências: `release-integration.txt`, `release-pytest.xml`, `release-hypothesis.txt`, `release-load.json`, `final-python-audit.json`, `release-npm-audit.json`, `release-npm-production-audit.json`. Estatísticas Hypothesis foram extraídas de base64 para texto, preservando casos/resultados no XML. Auditoria npm restrita à produção: zero vulnerabilidades conhecidas na resposta; a consulta incluindo desenvolvimento conserva 11 moderadas.

O ensaio usa somente PostgreSQL local descartável e dados sintéticos. Testes do adaptador HTTP usam transporte simulado, distinguindo teste de contrato de teste real da Meta.

Auditoria Python consultou 72 dependências sem vulnerabilidades conhecidas na resposta recebida. A consulta npm passou no limiar alto/crítico, mas mantém 11 achados moderados na cadeia de ferramentas ESLint/minimatch. `npm audit fix` sem `--force` não resolveu; não foi aplicada sugestão de downgrade principal do ESLint. Auditorias são pontuais e não certificam segurança futura.

O problema de concorrência do webhook encontrado durante os testes foi corrigido: corpo bruto lido assincronamente, persistência síncrona executada fora do event loop, commit antes de ACK. Timeout de lock/statement no runner evita ensaio indefinido. Eventos duplicados não geram segunda operação. Em rede ambígua não há retry automático de envio.

## Próximas informações necessárias

Identificar conta Meta e provedor de IA aprovado, sem enviar segredos pelo chat. Neon e Vercel já foram configurados para staging; valores privados da aplicação foram configurados sem credenciais administrativas no runtime. Responsáveis precisam fornecer políticas clínicas/identidade/retenção, texto de emergência e avaliação D13. A continuidade está autorizada; nenhuma nova aprovação genérica é necessária. Os itens dependentes permanecem pendentes até existir informação verificável.
