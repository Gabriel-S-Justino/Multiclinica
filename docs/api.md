# Contratos de API propostos

Contratos alvo F1. Na F2 estão executáveis autenticação/MFA/sessão/seleção de clínica/logout/recuperação, leitura de profissionais e auditoria, health e ready; OpenAPI efetivo em `/openapi.json`. Demais rotas da tabela permanecem planejadas. Base `/v1`; JSON com campos extras proibidos em comandos sensíveis. IDs UUID; normalização clínica será implementada com cada caso de uso. Tenant nunca vem de body/query: sessão ativa ou roteamento autenticado de integração.

| Método / rota relativa | Entrada / saída principal | Autorização |
|---|---|---|
| POST /auth/login | login/password → desafio MFA ou sessão | Anônimo com rate limit e erro genérico |
| POST /auth/mfa/verify | challenge_id/code → sessão rotacionada | Desafio temporário |
| POST /auth/recovery/request, /confirm | login; token/password → 202 ou 204 | Uso único e anti-enumeração |
| GET /auth/session; POST /auth/logout | identidade mínima; revogar | Sessão |
| POST /auth/active-membership | membership_id → contexto rotacionado | Membership do usuário |
| GET /services, /professionals, /units, /resources | filtros permitidos → página | Membership com escopo |
| POST/PATCH /services[/{id}] | nome, requires_professional, duração, ordem, ativo e políticas | services.write |
| GET/POST/PATCH /professionals[/{id}] | cadastro operacional mínimo e habilitações | memberships.write ou leitura autorizada |
| GET/POST/PATCH /schedules[/{id}] | vigência, dia, horários e unit | schedules.write no profissional |
| POST/DELETE /blocked-periods[/{id}] | intervalo e motivo operacional mínimo | schedules.write |
| GET /availability | service_id, professional_id opcional, from/to, cursor → slots e próximo cursor | appointments.read/create no escopo |
| POST /holds | service_id, slot opaco, professional_id opcional → hold_id/expires_at | appointments.create; idempotência |
| DELETE /holds/{id} | liberar reserva própria → 204 | Dono/operador autorizado |
| POST /appointments | hold_id, patient_id autorizado ou patient mínimo, contact_link → scheduled | appointments.create; idempotência |
| GET /appointments[/{id}] | período/status/cursor → agenda mínima | appointments.read no recurso |
| POST /appointments/{id}/cancel | reason_code, version → canceled | appointments.cancel; idempotência |
| POST /appointments/{id}/reschedule | hold_id, version → antigo/novo IDs | appointments.reschedule; idempotência |
| POST /appointments/{id}/transitions | target_status, version → estado | Permissão operacional e domínio |
| GET /inbox; GET /conversations/{id}/messages | fila/cursor → página minimizada | Fila atribuída |
| POST /handoffs/{id}/claim, /release, /close | version; ação → estado | inbox.claim/release e propriedade |
| POST /conversations/{id}/replies | text, version → queued | inbox.reply; handoff ativo; idempotência |
| GET /audit | ação/período/cursor → metadados | audit.read |
| PUT /integrations/{provider} | campos secretos → configured=true | integrations.write + MFA; nunca retornar valores |
| POST/PATCH /tenants[/{id}] | cadastro administrativo | tenants.manage; sem payload de pacientes |
| POST /break-glass/requests, /{id}/approve | escopo/motivo; decisão → grant | Superadmin solicita; Admin da clínica aprova |
| GET/POST /webhooks/whatsapp | challenge; corpo bruto → ACK | Verificação/assinatura do provedor, não cookie |
| POST /internal/jobs/{event_id}/execute | referência opaca → resultado | Identidade de dispatcher, proteção replay |
| GET /health | status genérico | Público, sem detalhes |

Criação de membership, atribuição de papéis/filas/profissionais, exceções/feriados e unidades/recursos terão CRUD administrativo com as mesmas regras de tenant, versão e auditoria; OpenAPI detalhará esses schemas na F2/F4 antes da implementação de cada tela.

## Schemas e limites propostos

`AppointmentCreate`: hold_id UUID, patient_id XOR new_patient, sem tenant/status escolhido pelo cliente. `new_patient`: display_name até 120 caracteres, birth_date somente se exigida; campos adicionais somente após política. CPF não coletado por padrão. `HoldCreate`: token de slot validado no servidor, sem duração livre. Mensagem de portal: 1–4.000 caracteres (limite interno proposto, não afirmação de limite WhatsApp). Página padrão 25, máximo 100; janelas de agenda até 31 dias; body interno até 64 KiB, webhook com limite próprio a verificar. UTC e fuso são revalidados, nunca confiar no token de slot como garantia.

`Idempotency-Key` obrigatório em comandos de negócio repetíveis: hash do payload canônico + tenant/ator/operação; chave repetida com payload diferente → 409. Resultado e efeitos confirmados no mesmo commit. TTL precisa cobrir janela de retries do provedor, a verificar em F5; expiração não remove unicidade dos eventos externos.

Erros: `{error:{code,message,correlation_id,fields?}}`, sem PII/stack trace. 401 sessão ausente; 403 ação negada; 404 recurso ausente ou fora do escopo; 409 conflito/versão/hold expirado; 422 formato inválido; 429 limite; 503 dependência indisponível. Login/recuperação e contato não verificado usam respostas uniformes. Paginação por cursor assinado/escopado e ordenação allowlisted. Respostas sensíveis `Cache-Control: no-store`.

## Atualização F2 — 31/10/2026

Este documento conserva o design completo da F1. O subconjunto implementado e validado nesta fase, com limites e comandos, está em [foundation.md](foundation.md) e no [relatório F2](reports/f2-foundation.md). Funcionalidades futuras aqui descritas não foram declaradas implementadas.


## Atualização F3 — 31/10/2026

A F3 entrega contratos tipados e casos de uso internos, não novas rotas HTTP. Endpoints/telas de agenda permanecem para F4. Os comandos rejeitam tenant livre, limitam payloads e exigem versão/idempotência. Ver [contratos F3](scheduling-implementation.md).
