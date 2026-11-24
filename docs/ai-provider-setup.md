# Configuração e homologação da IA

A IA é opcional e começa desligada. Em **Integrações**, selecione o provedor, cole uma chave emitida para essa conta e informe o identificador exato do modelo de texto. **Salvar e verificar** envia a frase fictícia “Voltar ao menu” e valida a estrutura da resposta. Essa chamada pode consumir créditos na conta do provedor.

OpenAI, Anthropic (Claude com chave de workspace), Google Gemini e OpenRouter aparecem inicialmente no seletor. Para cadastrar outra empresa, configure a variável abaixo com o mesmo valor na API e no worker, e reinicie ambos. Cada entrada contém um nome único e a URL base HTTPS de confiança. A clínica então seleciona esse nome no portal. Ao mudar de provedor, informe a chave e revise o aceite dos termos.

~~~dotenv
AI_EXTRA_ENDPOINTS='{"meu-provedor":"https://ia.example.org/v1"}'
~~~

O adaptador acrescenta /chat/completions à URL, autentica com Bearer e usa o modelo informado pela clínica. O serviço precisa receber mensagens de texto e devolver choices[0].message.content com a classificação em JSON e usage.total_tokens para a cota. Para APIs com outro protocolo ou autenticação, cadastre um gateway que faça essa tradução. Modelos exclusivos de imagem ou áudio não executam a classificação de texto.

Para habilitar o classificador, informe as referências da política de dados e do contrato, defina o limite mensal e o limite por conversa e marque **Usar IA para interpretar opções do menu**. O limite por conversa deve caber no mensal. Cada tentativa reserva 4096 tokens de forma conservadora, inclusive em caso de falha. A aplicação registra o consumo informado pelo provedor quando disponível. Defina também limites de gastos na conta da clínica.

O executor envia ao modelo somente a frase elegível e as opções de classificação. Telefones, identificadores estruturados e histórico do sistema ficam fora da requisição. O filtro local bloqueia frases com números, links, e-mails e termos clínicos reconhecidos, mas texto livre ainda pode incluir nomes ou informações sensíveis. A política da clínica precisa cobrir esse tratamento antes de habilitar IA com pacientes. Para OpenAI o adaptador pede `store: false`; confirme as condições de retenção da conta com o provedor.

A IA pode abrir o menu, mostrar serviços ou encaminhar para atendimento humano. A confirmação e as mudanças de agendamento passam pelo fluxo normal. Em caso de falha, saída inválida, baixa confiança ou cota insuficiente, o atendimento continua com as opções do menu. Prompts e respostas do provedor não entram no registro de consumo.

Homologue com frases fictícias que representem cada intenção, entradas bloqueadas e respostas inválidas. Registre o modelo testado e o resultado. O teste automatizado usa resposta simulada. O teste real depende da chave e do modelo da clínica.

[OpenAI Docs: Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) · [Controles de dados da API](https://developers.openai.com/api/docs/guides/your-data) · [Compatibilidade do Claude](https://platform.claude.com/docs/en/cli-sdks-libraries/libraries/openai-sdk) · [Compatibilidade do Gemini](https://ai.google.dev/gemini-api/docs/openai) · [API do OpenRouter](https://openrouter.ai/docs/api/reference/overview)
