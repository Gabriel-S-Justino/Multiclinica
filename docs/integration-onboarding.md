# Implantação assistida de uma clínica

Use [o portal Multiclinica](https://multclinicai.vercel.app) para demonstração e treinamento com dados fictícios. Faça a liberação para pacientes conforme o [roteiro de produção](release-runbook.md).

## Informações da clínica

| Área | Informação a confirmar |
|---|---|
| Cadastro | Nome fantasia, razão social, CNPJ, endereço, fuso horário e responsável |
| Equipe | Login do administrador, profissionais, recepção, horários e responsáveis pelas filas |
| Atendimento | Serviços, regras de agendamento, política de identificação, expediente e aviso fora do horário |
| WhatsApp | WABA ID, Phone Number ID, versão Graph, Access Token, App Secret e Verify Token |
| IA opcional | Chave OpenAI, modelo compatível, limites mensal e por conversa, referências da política de dados e do contrato |
| Operação | Contatos de suporte e incidentes, retenção, recuperação e critérios de liberação |

O administrador da clínica informa os segredos diretamente no portal. Compartilhe identificadores e referências pelo canal de implantação e mantenha tokens e chaves no gerenciador de segredos ou nos campos protegidos.

## Configurar e homologar

1. O Superadmin cadastra a clínica e convida o administrador. A pessoa ativa a conta com seu código, senha e MFA. O administrador cria unidades, profissionais, serviços e uma fila ativa com responsáveis e expediente.
2. Em **Integrações**, o administrador salva e verifica as credenciais do WhatsApp e vincula o número. Cadastre a URL exibida na Meta com o Verify Token e assine o evento `messages`.
3. A equipe Multiclinica inicia e monitora o [executor de filas](messaging-implementation.md). Com número e dados de teste, valide webhook assinado, mensagem recebida, processamento, encaminhamento humano e resposta registrada. Habilite o envio de teste com o comando documentado e confirme o retorno de entrega da Meta. Teste pausa, duplicata e recuperação de falha.
4. Para IA, siga o [guia da OpenAI](ai-provider-setup.md). Use frases fictícias para testar o direcionamento, a resposta inválida, a indisponibilidade e o limite de consumo.
5. Registre as evidências, o responsável pela aprovação e o procedimento de pausa. A clínica e a equipe liberam o canal para pacientes após a homologação e a revisão de privacidade.

Fontes: [WhatsApp Business Platform](https://developers.facebook.com/documentation/business-messaging/whatsapp/overview) e [OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create).
