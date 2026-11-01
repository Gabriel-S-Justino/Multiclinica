# Estratégia de testes e aceite

Matriz alvo criada na F1. Resultados reais da fundação F2 estão no relatório ao final; testes de agendamento/WhatsApp/IA continuam planejados para as próximas fases.

| Requisito | Casos obrigatórios planejados | Fase |
|---|---|---|
| RF-AG-01–08 | Elegibilidade, janela, feriado, buffers, duração, fuso/DST; propriedades de slots não sobrepostos; dependentes | F3 |
| RF-AG-09–13 | 50 confirmações simultâneas → exatamente 1 sucesso; holds concorrentes/expirados; remarcação rollback; idempotência e estados terminais | F3 |
| RF-CV-01–05 | Transições válidas/inválidas, dois eventos simultâneos, mensagem atrasada, retomada, silêncio no handoff e retorno explícito | F5 |
| RF-WA-01–10 | Corpo adulterado/assinatura inválida, replay, deduplicação por mensagem, status fora de ordem, janela/opt-out, paginação e não enumeração | F5 |
| RF-HU-01–04 | Assumir simultaneamente, fila não autorizada, prazo configurado, resposta durante handoff | F4/F5 |
| RF-PT | Matriz por endpoint: próprio, outro profissional, outro tenant, membership revogado, grant expirado | F2/F4 |
| RF-IA-01–07 | Schemas, configuração inválida, ferramentas chamadas diretamente com tenant/patient malicioso, operações sem confirmação | F6 |
| RF-IA-08–13 | Urgência determinística, texto fixo, minimização, cota concorrente, timeout/retry, modo degradado, não persistir prompts | F6 |
| SEC-01 sessões | CSRF/Origin/CORS, fixação, logout, recuperação/MFA, brute force | F2 |
| SEC-02 isolamento | RLS sem contexto, owner/runtime distintos, conexão reutilizada, FK entre tenants, jobs adulterados | F2/F5 |
| SEC-03 entradas | SQLi, XSS refletido/armazenado/DOM, SSRF, URL proibida, payload excessivo | F2–F7 |
| SEC-04 scans | Segredos, dependências e SAST sem alto/crítico não justificado | F2–F8 |
| OPS-01 recuperação | Restaurar backup, reaplicar descarte, medir RPO/RTO | F7 |
| UX-01 acessibilidade | Teclado, foco, estados loading/vazio/erro, axe, agenda/inbox responsivos | F4 |

RF-PT não tem sub-IDs na fonte; SEC/OPS/UX são IDs complementares de rastreabilidade. A F2 expandirá requisitos por endpoint e IDs de casos sem alegar cobertura antes de relatório. Banco real obrigatório para constraints, RLS, migrations e concorrência; SQLite não substitui.

Ferramentas propostas: pytest/Hypothesis, Vitest/Testing Library, Playwright/axe, Ruff, mypy, ESLint, tsc; scanners de dependências/segredos/SAST serão escolhidos e fixados em F2. Mock de IA em CI; golden conversations e corpus adversário versionados. Critério de injeção: zero violações de autorização/privacidade/segurança clínica, não apenas texto parecido com esperado.

CI a partir de F2: instalar dependências de lock → lint/formatação → tipos → unitários → PostgreSQL isolado/migrations/integração → build → segurança → e2e conforme superfície implementada. Guardar comandos, versões e relatórios, sem segredos. Nenhum token de produção em CI de contribuição externa.

## Atualização F2 — 31/10/2026

Este documento conserva o design completo da F1. O subconjunto implementado e validado nesta fase, com limites e comandos, está em [foundation.md](foundation.md) e no [relatório F2](reports/f2-foundation.md). Funcionalidades futuras aqui descritas não foram declaradas implementadas.


## Atualização F3 — 31/10/2026

A suíte de agendamento inclui disputas concorrentes em PostgreSQL real, SQL direto, rollback após gravações, propriedades Hypothesis, DST, vínculos e políticas explícitas. Resultados em [relatório F3](reports/f3-scheduling.md); não há testes ponta a ponta de WhatsApp ou benchmark de SLA.
