# Documentação técnica

O portal atual está em [Multiclinica](https://multclinicai.vercel.app). Comece pelo [roteiro de implantação](integration-onboarding.md) e pelos [critérios de produção](release-runbook.md). Relatórios e decisões das fases iniciais são registros históricos.

## Guias de uso por perfil

- [Médicos](guia-medico.md)
- [Recepção](guia-recepcao.md)
- [Administradores da clínica](guia-admin-clinica.md)
- [Administradores da plataforma](guia-admin-plataforma.md)

## Referência técnica

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
| [Permissões](users-and-permissions.md) | Cargos e permissões por vínculo |
| [API](api.md) | Contratos e referência OpenAPI |
| [Segurança](security.md) | STRIDE e controles |
| [Configuração de IA](ai-provider-setup.md) | Escolha do provedor e do modelo, verificação da chave, limites de uso e cadastro de outros provedores |
| [Vínculo do WhatsApp](whatsapp-provider-setup.md) | Localização dos IDs na Meta, configuração do webhook e teste da primeira resposta |
| [Relatório das integrações](reports/integracoes-antes-e-depois.md) | Comparação antes e depois e resultados dos testes |
| [LGPD](lgpd.md) | Pendências e ciclo de dados |
| [Deploy](deployment-vercel-neon.md) | Restrições e fontes verificadas |
| [Testes](testing.md) | Critérios e rastreabilidade |
| [Operação](operations.md) | Operação e recuperação |

Execução local: seguir [fundação](foundation.md). Para rotas vigentes, consulte o OpenAPI.

## Continuidade autorizada

Ver [relatório F5-F8](reports/continuation-f5-f8.md), [mensageria](messaging-implementation.md), [privacidade/incidentes](privacy-operations.md), [release](release-runbook.md) e [OpenAPI](api/openapi.json). Validação local não equivale a deploy ou conformidade final.
