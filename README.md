# ProjetoExtensao

Plataforma multi-clínica de atendimento por WhatsApp e gestão de agendamentos.

Status: portal de demonstração publicado e verificado em [staging](https://projeto-extensao-staging.vercel.app), com Neon e MFA obrigatório. Login, agendamento, remarcação, cancelamento, atendimento humano e logout passaram no ambiente remoto com dados sintéticos. WhatsApp, IA e produção clínica permanecem pendentes de configuração e políticas aprovadas. [Evidências e limitações da F8](docs/reports/f8-staging.md).

- [Escopo e requisitos](docs/requirements.md)
- [Descoberta e perguntas](docs/discovery.md)
- [Decisões D1–D16](docs/decisions/0001-discovery-defaults.md)
- [Relatório da F0](docs/reports/f0-discovery.md)
- [Índice do design F1](docs/README.md)
- [Relatório da F1](docs/reports/f1-design.md)
- [Executar a fundação local](docs/foundation.md)
- [Relatório da F2](docs/reports/f2-foundation.md)
- [Motor de agendamento F3](docs/scheduling-implementation.md)
- [Relatório da F3](docs/reports/f3-scheduling.md)
- [API e portal F4](docs/portal-implementation.md)
- [Relatório da F4](docs/reports/f4-portal.md)

A execução segue F0 descoberta → F1 design → F2 fundação → F3 agendamento → F4 portal → F5 WhatsApp determinístico → F6 IA → F7 hardening → F8 deploy, com aprovação ao final de cada fase.

- [Continuidade F5–F8 e pendências](docs/reports/continuation-f5-f8.md)
- [Operar mensageria](docs/messaging-implementation.md)
- [Preparar release](docs/release-runbook.md)
