# ADR 0005 · F4: API e portal

Registro histórico. O estado vigente está no [guia de implantação](../integration-onboarding.md) e nas [permissões atuais](../users-and-permissions.md).

Data: 31/10/2026. F3 aprovada; desenho apresentado antes da implementação. Estado: em execução, sujeito ao gate F4.

## Fronteiras

Rotas finas autenticam por cookie/CSRF, resolvem Principal no servidor e delegam a casos de uso. Dependência de banco com scope=function mantém commit antes da resposta. API versionada /v1, schemas sem campos extras, respostas minimizadas, erros genéricos e limites de página/período. JSON OpenAPI será exportado a partir do app efetivo.

O portal React/TypeScript/SCSS reutiliza a fundação e o Scheduler F3. Navegação por páginas: agenda dia/semana, agendamento com revisão, horários/exceções/bloqueios, serviços, colaboradores, inbox, auditoria e integrações. Gestão de clínicas é exclusiva de operador da plataforma. Interface em pt-BR, loading/vazio/erro, teclado e foco, cache separado e descartado em troca de clínica/logout.

## Identidade e administração

Contas com MFA continuam provisionadas pelo operador, sem simular e-mail. Convites para vínculos de clínica exigem aceite pelo usuário autenticado destinatário; admin não pode anexar conta alheia silenciosamente. Admin da clínica não concede papel de Superadmin. Um registro global PlatformOperator, provisionado fora da API, é requisito adicional para gestão da plataforma. Mudanças de papel/estado revogam sessões afetadas e não podem remover o último Admin ativo.

Serviços/políticas e horários são configurados no portal. Serviços sem política validada continuam bloqueados. Identificação/dependentes usa política manual explícita da clínica, referência de procedimento e validade configurada, sem padrão clínico inventado. Verificação de vínculo exige operador autorizado, MFA recente e declaração de verificação/autoridade; sem política aprovada não é habilitada.

## Inbox e integrações

Filas têm expediente explícito, classificação e integrantes. Recepção/Admin só acessam conversas das filas atribuídas; assumir usa versão/lock para impedir concorrência. Resposta é cifrada e entra na outbox; UI informa que está registrada para envio, sem alegar entrega. O transporte WhatsApp é F5. Enquanto handoff ativo não há transição automática para bot; liberação explícita determina retorno.

Integrações têm segredos somente de escrita, cifrados por tenant. GET retorna configured/version/estado não verificado, nunca valores. Salvar não testa uma integração nem ativa envio externo. Não serão chamadas URLs arbitrárias.

## Break-glass

Superadmin não recebe listagem ou acesso normal de pacientes. Pedido exige tenant, ID exato de appointment, justificativa e duração até 15 minutos; não revela existência antes da aprovação. Admin da clínica com MFA recente aprova e notificação/auditoria são persistidas. Só o solicitante pode ler o recurso específico durante o prazo; sem mutações, exportação ampla, inbox ou segredos. Não é permitido aprovar o próprio pedido.

## Plano de validação

Migração 0002→0003 com dados e downgrade; matriz de endpoints por papel/tenant/profissional/fila, CSRF/MFA, IDOR, segredos write-only, status e idempotência; concorrência no inbox; aprovação/expiração/revogação de acesso excepcional; e2e reais de agendar/remarcar/cancelar e atendimento humano, além de acessibilidade responsiva. Testes F2/F3 permanecem na suíte. Sem publicação nesta fase: deploy permanece F8.
