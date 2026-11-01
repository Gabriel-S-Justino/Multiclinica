# Permissões e identidade

Proposta F1. Cada endpoint valida membership ativo, tenant no servidor e permissão no recurso. Ocultação de UI não autoriza.

| Ação | Colaborador | Recepção | Admin | Superadmin |
|---|---|---|---|---|
| Ver/operar agenda | Própria, ações concedidas | Profissionais atribuídos | Clínica | Negado |
| Configurar expediente/bloqueios | Próprio, se autorizado | Se concedido | Clínica | Negado |
| Consultar paciente | Mínimo ligado à agenda própria | Mínimo para agenda atribuída/fila | Necessidade operacional na clínica | Negado |
| Inbox/responder | Negado por padrão | Filas atribuídas | Filas autorizadas | Negado |
| Serviços/colaboradores | Leitura mínima | Leitura mínima | Gerenciar clínica | Negado |
| Integrações | Negado | Negado | Escrever/rotacionar; nunca ler segredo | Negado |
| Auditoria | Negado | Negado | Clínica, sem payload sensível | Plataforma, sem pacientes |
| Gerenciar clínicas/admins | Negado | Negado | Negado | Permitido e auditado |

Permissões nominais propostas: `appointments.read/create/cancel/reschedule`, `schedules.write`, `patients.read_minimal`, `inbox.claim/reply/release`, `services.write`, `memberships.write`, `integrations.write`, `audit.read`, `tenants.manage`. Escopo próprio/atribuído/clínica é verificado adicionalmente ao papel.

Sessões opacas, hash do token no banco, cookie Secure/HttpOnly/SameSite=Lax, CSRF para mutações e verificação de Origin. Proposta: expiração inativa 30 min e absoluta 8 h, sujeita a validação; MFA obrigatório para Admin/Superadmin e operações sensíveis, recuperação de uso único com resposta não enumerável. Argon2id com parâmetros medidos na F2. Revogar sessões após recuperação, mudança de privilégios e logout; nunca guardar token no localStorage.

Break-glass: MFA recente, justificativa obrigatória, tenant/recursos/ações especificados e duração proposta máxima de 15 min; aprovação por responsável da clínica antes do acesso, notificação durável e auditoria de solicitação/uso/revogação. Sem aprovação não há bypass. Expiração checada em toda requisição; grant não concede leitura de segredos nem exportação ampla. Processo e prazo dependem de validação na F1; testes negativos fazem parte da F2/F4.

Verificação de paciente permanece decisão de negócio D3: nascimento isolado não é garantia. Sem política aprovada, consulta/alteração de appointment via WhatsApp deve encaminhar para verificação humana, sem revelar existência de cadastro. Agendamento novo exige dados mínimos e autorização de dependente; não vincular automaticamente por nome/nascimento.

## Atualização F2 — 31/10/2026

Este documento conserva o design completo da F1. O subconjunto implementado e validado nesta fase, com limites e comandos, está em [foundation.md](foundation.md) e no [relatório F2](reports/f2-foundation.md). Funcionalidades futuras aqui descritas não foram declaradas implementadas.
