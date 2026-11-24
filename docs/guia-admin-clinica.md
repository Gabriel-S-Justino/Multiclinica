# Guia do administrador da clínica

## Prepare a primeira agenda

1. **Entre pela clínica correta.** Use o convite da plataforma em **Ativar conta**, configure a senha e o autenticador e selecione sua clínica. Quem já tem uma conta pode aceitar o convite após entrar. Confira o nome da clínica no seletor antes de alterar um cadastro.
2. **Organize o local de atendimento.** Em **Configurações**, cadastre as unidades e os recursos que os serviços utilizam, como uma sala ou equipamento. Crie uma fila de atendimento humano, defina o expediente e escreva um aviso fora de horário que diga quando a equipe poderá responder.
3. **Combine como a equipe identifica pacientes.** Ainda em **Configurações**, registre a referência do procedimento aprovado pela clínica e a validade da verificação. Explique à recepção como conferir a identidade de um responsável antes de vinculá-lo a um paciente.
4. **Cadastre os serviços.** Em **Serviços**, crie cada atendimento com a duração, o intervalo entre opções de horário, os tempos de preparo, os recursos e a antecedência permitida. Configure o prazo e o limite de remarcações. Revise e valide a política para liberar o serviço para agendamento. Por exemplo, um limite de zero impede remarcações daquele serviço.
5. **Monte a equipe.** Em **Equipe**, convide cada pessoa com seu e-mail e cargo. Entregue o código de ativação em particular. Cadastre o profissional, confira o nome que o paciente deve ver e associe seus serviços. Revise também o vínculo de acesso. Para a recepção, atribua os profissionais e as filas que ela atenderá. Libere edição de horários apenas a quem cuidará dessa rotina.
6. **Abra a disponibilidade.** Em **Horários e bloqueios**, selecione o profissional e configure intervalos de expediente por unidade, as datas de validade e eventuais exceções. Na agenda, simule a procura de um horário. Se nenhum aparecer, confira serviço validado, associação ao profissional, unidade, expediente, bloqueios e recursos disponíveis.
7. **Faça um ensaio com a equipe.** Use um paciente de teste autorizado para percorrer cadastro, reserva, confirmação e remarcação. Confira o dia e a hora no fuso da clínica. Peça à recepção para repetir o fluxo usando o próprio acesso.

## Prepare o WhatsApp para os avisos

1. Abra **Integrações → WhatsApp**. Separe os identificadores da conta e do telefone, o token de acesso e o segredo do app. Siga o guia para verificar os dados, vincular o número, configurar o webhook, assinar mensagens e ativar o envio. [Vincular o número passo a passo](whatsapp-provider-setup.md)
2. Para avisar pacientes que não escreveram nas últimas 24 horas, peça a aprovação do modelo **consulta_remarcada**, em português do Brasil, na conta empresarial da clínica. O guia do WhatsApp traz o texto e a ordem das três variáveis. Confirme com a equipe técnica que a migração está aplicada e o worker está em execução.
3. Oriente a equipe a registrar a autorização da pessoa no momento da revisão, quando ela existir. Faça dois testes com o número combinado: um após o contato escrever para a clínica e outro fora da janela com autorização e modelo aprovado. Confira o recebimento no celular e o status nos detalhes da nova consulta.
4. Se houver falhas, consulte **Integrações** para verificar se o envio está ativo, o executor está online e as credenciais são aceitas. Se o aviso ficar bloqueado ou a entrega estiver incerta, combine com a recepção quem fará o contato por outro canal.
5. A IA é opcional para o menu. Para habilitá-la, escolha um provedor, verifique chave e modelo e configure os limites e a política de dados. Os avisos de remarcação usam o texto da clínica independentemente da IA. [Configurar a IA](ai-provider-setup.md)

## Cuide da operação após a abertura

- **Mudança de escala.** Atualize a disponibilidade e revise as consultas já marcadas no período. A equipe remarca cada consulta afetada e acompanha o aviso.
- **Troca de funcionário.** Em **Equipe**, revise cargo, vínculo, profissionais e filas. Ao encerrar um vínculo, confira a pessoa e a clínica. Preserve a cobertura da recepção e pelo menos um administrador ativo.
- **Problema de acesso.** Verifique se a pessoa aceitou o convite e escolheu a clínica correta. Para pedidos de suporte sobre uma consulta, abra **Acesso excepcional**, confira recurso, justificativa e duração e aprove ou rejeite. Se a necessidade terminar antes, revogue a autorização.
- **Conferência.** Em **Auditoria**, procure a ação e o recurso associados à alteração. Para saber se o paciente recebeu o aviso, consulte também o estado do WhatsApp na nova consulta. O registro da remarcação e o retorno de entrega são acontecimentos distintos.

[Guia da recepção](guia-recepcao.md) · [Guia do médico](guia-medico.md) · [Roteiro de liberação](release-runbook.md)
