# Operação

O portal e a API expõem `/v1/health` e `/v1/ready`. A prontidão verifica a conexão de runtime e suas restrições. O executor de mensagens roda em serviço supervisionado, conforme o [guia de mensageria](messaging-implementation.md).

| Evento | Procedimento |
|---|---|
| API ou banco indisponível | Verifique a prontidão, o deploy e a conexão do runtime. Confirme o retorno do webhook e deduplicação após a recuperação. |
| Executor parado ou fila atrasada | Confira o processo e o atraso de entrada e saída. Reinicie o executor supervisionado e confirme que a fila volta a avançar. |
| Falha definitiva ou entrega desconhecida | Consulte o código operacional e reconcilie com a Meta. Use o mesmo identificador ao reprocessar um evento elegível. |
| IA indisponível ou cota excedida | O menu permanece disponível. Confirme o modelo, a chave e os limites da clínica. |
| Segredo comprometido | Revogue ou rotacione no provedor, atualize em Integrações e confira a operação com dados fictícios. |
| Incidente de dados | Siga o [procedimento de privacidade e incidentes](privacy-operations.md). |
| Falha de release | Promova uma versão compatível com o esquema. Suspenda o envio do canal quando necessário. |

Registre metadados de operação e correlação. Acompanhe idade da fila, falhas, retentativas e confirmação de entrega. Defina responsáveis e limiares com base no ensaio de implantação.

A restauração deve ocorrer num destino isolado, com executor e webhooks desligados. Valide a revisão do banco, regras de acesso, chaves de cifra e leitura dos dados recuperados. Compare contagens e meça a perda admissível e o tempo de recuperação. Antes de redirecionar a aplicação, reconcilie entregas e aplique as decisões de descarte aprovadas.

[Preparação e liberação](release-runbook.md)
