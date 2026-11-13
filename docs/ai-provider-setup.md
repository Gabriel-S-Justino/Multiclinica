# Configuração e homologação da IA

A IA é opcional e começa desligada. Em **Integrações**, o administrador escolhe OpenAI, informa a chave da clínica e o identificador de um modelo compatível com Chat Completions e Structured Outputs. **Verificar credenciais** consulta o modelo. Valide a geração estruturada durante a homologação.

Para habilitar o classificador, informe as referências da política de dados e do contrato, defina o limite mensal e o limite por conversa e marque **Usar IA para interpretar opções do menu**. O limite por conversa deve caber no mensal. Cada tentativa reserva 4096 tokens de forma conservadora, inclusive em caso de falha. A aplicação registra o consumo informado pelo provedor quando disponível. Defina também limites de gastos na conta da clínica.

O executor envia ao modelo somente a frase elegível e as opções de classificação. Telefones, identificadores estruturados e histórico do sistema ficam fora da requisição. O filtro local bloqueia frases com números, links, e-mails e termos clínicos reconhecidos, mas texto livre ainda pode incluir nomes ou informações sensíveis. A política da clínica precisa cobrir esse tratamento antes de habilitar IA com pacientes. O adaptador pede `store: false`; confirme as condições de retenção da conta com o provedor.

A IA pode abrir o menu, mostrar serviços ou encaminhar para atendimento humano. A confirmação e as mudanças de agendamento passam pelo fluxo normal. Em caso de falha, saída inválida, baixa confiança ou cota insuficiente, o atendimento continua com as opções do menu. Prompts e respostas do provedor não entram no registro de consumo.

Homologue com frases fictícias que representem cada intenção, entradas bloqueadas e respostas inválidas. Registre o modelo testado e o resultado. O teste automatizado usa resposta simulada. O teste real depende da chave e do modelo da clínica.

[OpenAI Docs: Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) · [Controles de dados da API](https://developers.openai.com/api/docs/guides/your-data)
