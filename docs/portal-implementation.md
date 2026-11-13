# API e portal — F4

O portal local usa React/TypeScript, React Router, TanStack Query e SCSS. A API FastAPI reutiliza as transações e o motor F3. Executar a fundação conforme [foundation.md](foundation.md); aplicar `alembic upgrade head` antes de iniciar API e frontend. Nenhuma integração externa é ativada nesta fase.

## Operação

1. Para o primeiro acesso administrativo, executar o bootstrap pelo terminal. Para as demais contas, criar um convite pelo portal e compartilhar o código de ativação em particular com o destinatário.
2. Entrar, validar o autenticador e selecionar a clínica. Os menus dependem das capacidades retornadas pelo servidor; a autorização é repetida em cada operação.
3. Configurar unidades, profissionais, habilitações, serviços, horários e políticas aprovadas pela clínica. Serviços sem validação não oferecem agendamento.
4. Na agenda, cadastrar o contato e o paciente mínimo, selecionar horário, revisar o hold e confirmar. Uma reserva temporária não equivale a consulta confirmada.
5. Verificar vínculos conforme procedimento aprovado antes das operações que exigem identidade. A referência registrada não deve conter dados pessoais.
6. Atribuir membros às filas. No atendimento humano, assumir a conversa antes de responder. Respostas ficam cifradas e enfileiradas; envio WhatsApp será implementado na F5.

Quem já tem conta aceita o convite após entrar. Para uma conta nova, o destinatário abre **Ativar conta** na tela de login, informa seu login e o código do convite, configura o autenticador e escolhe a senha. A ativação cria a conta e aceita o convite na mesma transação. O código vale por sete dias e é compartilhado pelo administrador. Credenciais de integrações são somente de escrita; salvar não verifica o provedor.

O operador de plataforma precisa de registro adicional e MFA. Acesso excepcional exige aprovação de outro administrador da clínica, expira em até 15 minutos e permite ler somente a consulta especificada, com auditoria e notificação. Não concede edição clínica.

## Contratos e verificação

As mutações clínicas usam `Idempotency-Key` igual ao campo `idempotency_key`; alterações usam versão otimista. Paginação usa cursores assinados vinculados ao ator, clínica e filtros. Conflitos retornam códigos genéricos sem valores pessoais ou credenciais. Cookies seguros, CSRF, RLS e auditoria continuam obrigatórios.

`scripts/verify.ps1 -Phase f4` verifica código, tipos, segurança estática, segredos e frontend. `scripts/run_integration.py` usa PostgreSQL real descartável; `RUN_E2E=1` adiciona Chromium com API real. Não usar os fixtures sintéticos em produção.

## Fontes oficiais

Consultadas em 31/10/2026: [FastAPI: dependências e transação](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/), [SQLAlchemy: controle de versão](https://docs.sqlalchemy.org/en/20/orm/versioning.html), [W3C: diálogo modal](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/), [React Router](https://reactrouter.com/start/declarative/installation) e [HashRouter](https://reactrouter.com/api/declarative-routers/HashRouter).
