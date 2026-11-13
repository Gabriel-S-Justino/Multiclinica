# Design de agendamento

RF-AG-01-13. Este é o desenho F1; a implementação e os testes F3 estão em [scheduling-implementation.md](scheduling-implementation.md). A granularidade de lock por profissional descrita abaixo foi substituída por lock transacional por clínica no ADR 0004.

Disponibilidade é calculada por timezone IANA da clínica, expediente e vigência, exceções, feriados, bloqueios, habilitação e atividade, duração e buffers, antecedências e janela (30 dias por padrão, limitada pela clínica). Intervalos ocupados são `[start,end)`, permitindo slots adjacentes. Datas locais ambíguas/inexistentes por mudança de fuso precisam de resolução explícita; rejeitar entrada ambígua sem offset. Persistir UTC e timezone aplicado. Alterar agenda usa os mesmos locks de ocupação para não invalidar confirmação concorrente.

Sem preferência: calcular carga futura em horas para cada elegível na janela pesquisada, menor primeiro horário e UUID como desempate estável; registrar versão da estratégia e critérios sem PII. Consulta é informativa, slot pode deixar de existir.

## Transações

1. **Hold:** validar tenant/permissão/habilitação e janela; bloquear linhas de profissionais e recursos em ordem global estável; expirar logicamente holds por relógio do banco; consultar appointments e holds sobrepostos; inserir hold com TTL 10 min. Duplicação de chave retorna mesmo resultado, payload divergente dá conflito.
2. **Confirmar:** bloquear conversa (se aplicável), depois profissionais/recursos em ordem estável, depois hold; revalidar posse, verificação, prazo, políticas e ocupação; criar paciente se necessário; inserir appointment scheduled e recursos; consumir hold; gravar transição, idempotência, auditoria, estado da conversa e outbox; commit único. Exclusion constraint é última barreira; conflito retorna 409, nunca sucesso parcial.
3. **Remarcar:** bloquear conversa e conjunto ordenado de profissionais/recursos antigos e novos; revalidar política e posse do hold novo; excluir da checagem apenas o appointment antigo autorizado; marcar antigo rescheduled, criar novo e vínculo, consumir hold e gravar eventos em um commit. Qualquer falha desfaz ambos.
4. **Cancelar:** lock/versão do appointment, validar política/escopo, mudar status, liberar ocupação derivada de recursos, auditar e outbox. Retry com mesma chave não duplica efeitos.

Todos os escritores de agenda, bloqueios, holds e recursos seguem a mesma ordem de locks. Retry limitado para deadlock/serialização somente com idempotência. Nenhuma chamada de IA/WhatsApp dentro dos locks. Expiração não depende do job de limpeza; hold expirado não bloqueia consulta.

## Ciclo de vida

`held` existe no hold: pode expirar, ser liberado ou consumido. Appointment: scheduled → confirmed/completed/canceled/no_show/rescheduled; confirmed → completed/canceled/no_show/rescheduled. completed, canceled, no_show e rescheduled são terminais. completed/no_show exigem início atingido e permissão operacional; confirmed manual no MVP, confirmação proativa fica para fase posterior. Uma mudança inválida dá conflito e não grava transição.

Recursos têm slots unitários; reservas com múltiplos recursos são all-or-nothing. Exclusion constraints de appointments não protegem contra holds de outra tabela: por isso todos os caminhos passam por locks e revalidação. Testes devem tentar também escrita direta com papel runtime; privilégios/repositórios precisam impedir caminhos não autorizados.

## Atualização F2 · 31/10/2026

Este documento conserva o design completo da F1. O subconjunto implementado e validado nesta fase, com limites e comandos, está em [foundation.md](foundation.md) e no [relatório F2](reports/f2-foundation.md). Funcionalidades futuras aqui descritas não foram declaradas implementadas.
