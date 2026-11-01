# Conversa determinística

RF-CV-01–05; RF-WA-03–10. Cada evento usa estado/versionamento persistido, contexto mínimo validado por schema e ações de domínio autorizadas.

| Estado | Entrada válida | Próximo estado / efeito |
|---|---|---|
| MENU | serviço, minhas consultas, humano | SELECT_PROFESSIONAL, VERIFY_CONTACT ou HUMAN_HANDOFF |
| SELECT_PROFESSIONAL | preferência ou sem preferência | SELECT_DATE |
| SELECT_DATE | data elegível | SELECT_TIME |
| SELECT_TIME | slot elegível | IDENTIFY_PATIENT; criar hold |
| IDENTIFY_PATIENT | próprio/dependente, dados mínimos e vínculo | REVIEW após validação; verificação humana se insuficiente |
| VERIFY_CONTACT | prova aprovada na política | MANAGE_APPOINTMENT; falha genérica, limites e humano |
| MANAGE_APPOINTMENT | consulta autorizada, cancelar/remarcar | confirmação de ação ou SELECT_DATE para novo hold |
| REVIEW | confirmar resumo | DONE somente após commit de domínio |
| DONE | novo atendimento | MENU |
| HUMAN_HANDOFF | ação autenticada do atendente | MENU apenas ao liberar explicitamente ou expiração configurada |
| RESUME | aceite de retomada após inatividade | ponto salvo revalidado ou MENU |

Resumo: serviço, profissional, data/hora local, unidade, duração e paciente mínimo, sem CPF/telefone/nascimento. Menu semana → dia → horário com paginação server-side e cursor vinculado à conversa; quantidade de itens depende dos limites oficiais a verificar em F5.

Voltar preserva dados confirmados quando válidos e libera hold se muda slot. Reiniciar libera hold e contexto temporário, sem cancelar appointment existente. Cancelar fluxo é distinto de cancelar consulta e requer texto inequívoco. Hold expirado em REVIEW volta à escolha de horário, sem confirmação fictícia. Tentativas ambíguas limitadas por configuração antes de oferecer menu/humano.

## Ordenação e idempotência

Deduplicar envelope e cada mensagem por identificador autenticado. Criar sequência local na ingestão e processar uma conversa por vez com lock transacional. Timestamp externo não garante ordem causal; evento atrasado que não se aplica ao estado atual pede reconfirmação e não executa ação sensível. Ações de botões carregam token opaco de estado/versão; token obsoleto não executa operação. Callbacks de entrega usam transições monotônicas, permitindo lido antes de entregue sem regredir estado.

Durante handoff o bot fica silencioso. Atendente deve assumir com compare-and-swap para impedir dois responsáveis; acesso por fila e clínica. Fora do horário registra solicitação; só informa prazo previamente configurado. Mídia fora de handoff recebe orientação de texto/humano sem download.

## Atualização F2 — 31/10/2026

Este documento conserva o design completo da F1. O subconjunto implementado e validado nesta fase, com limites e comandos, está em [foundation.md](foundation.md) e no [relatório F2](reports/f2-foundation.md). Funcionalidades futuras aqui descritas não foram declaradas implementadas.
