# Documentação técnica

F0–F4 aprovadas em 31/10/2026. Documentos de design preservam o plano completo; a base entregue está em [foundation.md](foundation.md) e o motor F3 em [scheduling-implementation.md](scheduling-implementation.md). Ainda sem MVP completo ou deploy.

| Documento | Conteúdo |
|---|---|
| [Especificação original](master.md) | Master.md fornecido pelo usuário, preservado como fonte |
| [Fundação local](foundation.md) | Funcionalidades entregues e comandos F2 |
| [Agendamento implementado](scheduling-implementation.md) | Casos de uso, concorrência e limites F3 |
| [Arquitetura](architecture.md) | Componentes, camadas e estrutura futura |
| [Decisões técnicas](decisions/0002-design.md) | Resolução de ambiguidades e escolhas para F2 |
| [Dados](data-model.md) | Entidades, vínculos e constraints |
| [Agendamento](scheduling.md) | Disponibilidade e transações |
| [Conversa](whatsapp-flow.md) | Estados e eventos |
| [Permissões](users-and-permissions.md) | RBAC e break-glass |
| [API](api.md) | Contratos propostos |
| [Segurança](security.md) | STRIDE e controles |
| [IA](ai-provider-setup.md) | Interfaces e guardrails |
| [WhatsApp](whatsapp-provider-setup.md) | Fronteira de integração |
| [LGPD](lgpd.md) | Pendências e ciclo de dados |
| [Deploy](deployment-vercel-neon.md) | Restrições e fontes verificadas |
| [Testes](testing.md) | Critérios e rastreabilidade |
| [Operação](operations.md) | Runbooks propostos |

Execução local: seguir [fundação](foundation.md). Revisão dos documentos não exige credenciais. Não confundir funcionalidades planejadas com endpoints entregues nesta fase.

## Continuidade autorizada

Ver [relatório F5–F8](reports/continuation-f5-f8.md), [mensageria](messaging-implementation.md), [privacidade/incidentes](privacy-operations.md), [release](release-runbook.md) e [OpenAPI](api/openapi.json). Validação local não equivale a deploy ou conformidade final.
