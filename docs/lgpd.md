# Plano de privacidade · pendente de validação

Este documento é inventário técnico proposto; não afirma conformidade ou define base legal. D12/D13 dependem da clínica/jurídico. Não há pacientes reais neste repositório.

| Dados | Finalidade proposta | Minimização / destino |
|---|---|---|
| Contato e telefone | Comunicação e vínculo | Cifra + HMAC; não enviar telefone ao modelo |
| Nome e nascimento quando necessário | Cadastro/identificação | Campos mínimos, acesso por escopo; não repetir em logs |
| Serviço, profissional e horário | Agendar e operar agenda | Pode revelar informação sensível; acesso restrito |
| Texto de mensagens | Atendimento e handoff | Cifra, retenção por política; texto livre pode conter dado sensível |
| Metadados e auditoria | Segurança e operação | Sem payload clínico; identificadores opacos |
| Senha/MFA/sessões | Controle de acesso | Hash de senha/token, segredo MFA cifrado |

Confirmar controlador/operador, encarregado e contatos, finalidade/base por tratamento, avisos, vínculo de dependentes e menores, retenção/descarte e obrigações de preservação. Consentimento de WhatsApp e base de tratamento são conceitos distintos.

Mapear contratos/suboperadores Meta/BSP, IA, Neon, Vercel, fila, observabilidade e e-mail de recuperação; confirmar regiões, transferência internacional e controles antes de produção. RIPD, canal de direitos e incidentes ficam a cargo dos responsáveis indicados, com implementação técnica em F7.

Direitos: solicitação autenticada → validação de identidade → análise de escopo/preservação → exportação mínima ou correção/anônimização → auditoria sem conteúdo exportado. Nunca exportar por contato não verificado. Backup exige política de expiração e reaplicação de tombstones ao restaurar; apagar no primário sozinho não resolve descarte.

Prazos legais de comunicação, retenção e respostas estão não verificados; consultar fontes oficiais/jurídico na F7. Produção bloqueada sem política aprovada e mecanismo de execução/teste.

## Atualização F2 · 31/10/2026

Este documento conserva o design completo da F1. O subconjunto implementado e validado nesta fase, com limites e comandos, está em [foundation.md](foundation.md) e no [relatório F2](reports/f2-foundation.md). Funcionalidades futuras aqui descritas não foram declaradas implementadas.
