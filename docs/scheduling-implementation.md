# Agendamento implementado · F3

Data: 31/10/2026. Backend implementado por casos de uso; endpoints/telas de agenda pertencem à F4. WhatsApp/IA não são chamados. Nenhuma clínica real, credencial externa ou dado de paciente foi usado.

## Contratos efetivos

`Scheduler` fica em `backend/application/scheduling.py`; comandos Pydantic em `backend/application/scheduling_commands.py`. Domínio puro em `domain/scheduling.py` e `domain/selection.py`. Persistência em `infrastructure/scheduling_models.py`; revisão Alembic `0002` contém DDL congelado, políticas, constraints e triggers. `0001` foi preservada.

| Caso de uso | Entrada | Resultado / garantia |
|---|---|---|
| register_contact | Telefone E.164 e chave idempotente | Contato mínimo, telefone cifrado/HMAC; não revela paciente |
| availability | Serviço, unidade, profissional opcional, intervalo de datas e página | Slots UTC por profissional; consulta informativa |
| create_hold | Slot, contato, recursos, preferência opcional, conversa/versão opcionais | Hold com TTL; escolha determinística auditável |
| confirm | Hold, contato e paciente verificado OU dados mínimos novos | Paciente quando necessário, consumo de hold, appointment, recursos, conversa, auditoria e outbox em uma transação |
| cancel | Appointment, contato, versão e chave | Políticas e vínculo verificados; liberação de ocupação |
| reschedule | Appointment/versão e hold explicitamente vinculado ao original | Original rescheduled + novo scheduled, ou rollback integral |
| transition | Appointment/versão e confirmed/completed/no_show | Transição autorizada; conclusão/falta só após início |
| release_hold | Hold próprio, contato e chave | Libera ocupação, preservando histórico; conversa retorna à seleção quando aplicável |

O chamador deve abrir `Session` e `db.begin()` e deixar exceções provocarem rollback. O serviço faz flush para validar constraints, **nunca commit**. Rotas F4 só podem responder sucesso após o commit. Principal deve vir da sessão autenticada no servidor; não construir com tenant/papel recebido do cliente. A aplicação revalida membership/usuário/clínica e MFA configurado, inclusive após esperar pelo lock.

## Disponibilidade e seleção

Fuso IANA da clínica; expediente semanal por profissional/unidade e vigência; exceções substituem o expediente do dia (fechamento prevalece); feriados por clínica/unidade; bloqueios, habilitação/atividade, duração por serviço ou override do profissional, buffers, antecedência e horizonte máximo. Recursos obrigatórios são unidos aos opcionais solicitados e nunca podem ser omitidos. Recursos precisam estar ativos na unidade.

Slots usam intervalo `[início,fim)`, duração real em UTC e grade local configurada. Buffers precisam caber no expediente e não colidir com outra ocupação. Horas locais inexistentes/ambíguas e consultas que atravessam uma mudança do relógio não são ofertadas automaticamente: decisão conservadora para evitar interpretação silenciosa de DST. Isso pode reduzir oferta em dias de transição.

Consulta aceita até 31 dias por chamada, páginas até 100 slots e offset limitado. O canal WhatsApp fará agrupamento/paginação na F5 conforme limites oficiais. Uma página não mantém snapshot estável durante novas reservas; confirmação sempre revalida.

`SelectionStrategy` permite injetar estratégias no servidor. Padrão implementado `LeastFutureLoad/v1`: carga ativa futura (scheduled/confirmed) da consulta até o horizonte do serviço, primeiro slot elegível do dia escolhido e UUID. Histórico concluído não pesa. A seleção ocorre entre profissionais autorizados e elegíveis para o horário solicitado. Critérios e ordenação com IDs opacos ficam no recibo idempotente do hold, ligado ao evento de auditoria `hold.created`; sem nomes ou dados de paciente. Não há seletor de estratégia vindo do modelo/cliente.

## Concorrência e banco

Todas as mutações adquirem `pg_advisory_xact_lock` com chave derivada da clínica. É uma simplificação registrada no [ADR 0004](decisions/0004-scheduling.md): serializa mutações da mesma clínica e protege recursos compartilhados; paralelismo por profissional ficou adiado. Não afirmar latência/SLA de produção a partir de testes funcionais.

Triggers de holds/appointments/recursos repetem lock e checagens para impedir bypass por SQL direto com papel runtime. Configuração de agenda também participa do lock. Funções são invoker, com search_path fixado para evitar sombra por objetos temporários; RLS continua aplicada. Intervalos de appointments ativos têm exclusion constraint GiST com btree_gist; recursos possuem FKs compostas e destino exclusivo (hold ou appointment). Timestamps/duração/buffers são consistentes por CHECK; identificadores e intervalos da reserva são imutáveis.

Holds ativos bloqueiam junto com appointments; vencidos deixam de bloquear pelo relógio do banco sem esperar job. TTL não pode ser estendido por UPDATE do runtime. Limpeza futura é apenas higiene. Registros são mantidos para auditoria; runtime não recebe DELETE nas novas tabelas. A implementação não usa locks persistentes de sessão.

Remarcação sobreposta ao original: o hold carrega referência explícita ao appointment original e só ignora essa ocupação específica. A aplicação exige vínculo verificado, versão, mesmo serviço e limites antes de criar o hold. Consumo/novo appointment exigem que o original esteja rescheduled e aponte para o novo ID, com FK diferida até commit. Outras consultas e holds continuam bloqueando.

Falhas SQL de integridade são convertidas em erros de domínio sem parâmetros pessoais. Não há retry cego: quem reexecuta deve reutilizar a chave idempotente. Timeout/deadlock pode ser repetido pelo futuro adaptador somente após rollback e com chave estável; retry automático de transporte não foi implementado nesta fase.

## Paciente e privacidade

As decisões reais D3/D9 não foram preenchidas pela aprovação da fase. Serviço sem `policy_validated` fica bloqueado. Duração, antecedências, buffers, horizonte, remarcações e campos mínimos são configuração explícita; não existe seed de política clínica de produção.

Paciente existente exige vínculo contato-paciente registrado manualmente pela clínica: método manual_clinic, responsável, instante, validade e ausência de revogação. Telefone/nascimento isolados não verificam ninguém. Vínculo pode representar dependente, mas o procedimento/evidência exigidos pela clínica ainda precisam ser definidos. Sem verificação não há consulta/alteração automatizada; erros de operação não expõem se um appointment existe.

Paciente novo: finalidade reconhecida, nome validado; nascimento só é aceito se exigido no serviço e não pode ser futuro na data local da clínica. Nome não é usado para deduplicar ou vincular automaticamente a pessoa existente. Novo vínculo é declarado e fica **não verificado** para futuras alterações; encaminhamento humano será conectado nas próximas fases. Não há CPF.

Telefone e campos de paciente usam AES-GCM da biblioteca cryptography, nonce aleatório e AAD por tenant/entidade/linha/campo. Chave específica derivada de FIELD_KEY por HKDF; HMAC do telefone usa TOKEN_KEY distinto. Valores pessoais não são gravados em logs, auditoria, outbox ou recibos idempotentes. Rotação operacional das chaves e política de retenção permanecem em F7; a versão atual da cifra é v1.

## Atomicidade e conversa

Idempotência por `(tenant_id,key)`, operação, ator e HMAC do comando. Mesmo comando devolve recibo original; payload/ator/operação divergentes geram conflito. Recibo é histórico, não consulta do status atual; inclui expiração do hold. Não purgar chaves sem política de replay validada na F5.

Quando uma conversa é informada: SELECT_TIME + versão → REVIEW com hold_id; confirmação exige REVIEW/versão/mesmo hold e grava DONE com appointment_id. Handoff e versões obsoletas não são transições válidas para esses comandos. A máquina completa e serialização de mensagens são F5.

Outbox contém eventos transacionais com IDs opacos/versionamento e status pending. Ela ainda não é um serviço de entrega; D6 continua pendente. Falha externa nunca será tratada como confirmação de agenda nesta fase.

## Verificação e reprodução

Seguir pré-requisitos e instalação da [fundação](foundation.md). Com as dependências de `uv.lock` sincronizadas e binários PostgreSQL em PG_BIN:

```powershell
./scripts/verify.ps1 -Phase f3
$env:PG_BIN='CAMINHO_DOS_BINARIOS_POSTGRESQL'
$env:RUN_E2E='1'
uv run --frozen python scripts/run_integration.py
```

Runner prepara PostgreSQL novo, migra até 0001, insere dado de prova, sobe para 0002 e verifica preservação; executa testes reais, regressão opcional de navegador, downgrade e novo upgrade. Desliga o servidor no finally. Nunca usar banco/credenciais de produção. Restauração de backup/PITR não é equivalente a esse teste e continua pendente em F7.

Evidências finais e limitações: [relatório F3](reports/f3-scheduling.md). Testes de concorrência não substituem testes de carga nem comprovam o comportamento no pool Neon real.

## Fontes oficiais consultadas em 31/10/2026

- [PostgreSQL: locks explícitos](https://www.postgresql.org/docs/current/explicit-locking.html): distingue locks de sessão e de transação; usamos apenas estes últimos.
- [PostgreSQL: ranges](https://www.postgresql.org/docs/current/rangetypes.html): intervalos e exclusão sustentam a constraint de não sobreposição.
- [PostgreSQL: triggers](https://www.postgresql.org/docs/current/trigger-definition.html): base para validação automática das escritas; comportamento concorrente também testado localmente.
- [Python: zoneinfo](https://docs.python.org/3/library/zoneinfo.html): suporte IANA/fold; política de rejeitar horários ambíguos é escolha desta aplicação, não regra clínica.
- [cryptography: AEAD](https://cryptography.io/en/latest/hazmat/primitives/aead/): uso de nonce e associated data da biblioteca, sem criação de algoritmo próprio.

As páginas atuais são mutáveis; o runtime efetivamente testado foi Python 3.12.14/PostgreSQL 18.6 e versões fixadas no lock. Compatibilidade com pool remoto e planos de hospedagem continua sem teste real.
