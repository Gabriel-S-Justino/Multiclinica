# Integrações de IA e WhatsApp · antes e depois

24 de novembro de 2026 · Comparação com o commit `efb1644` da branch `main`.

| Área | Antes | Depois |
|---|---|---|
| Escolha de IA | O formulário enviava OpenAI como valor fixo, e o servidor recusava outros provedores. | Cada clínica escolhe entre OpenAI, Anthropic, Google Gemini, OpenRouter e os serviços adicionais cadastrados pela equipe na API e no worker. |
| Chave e modelo | O campo aceitava um conjunto restrito de caracteres para o modelo e exigia chave de pelo menos 12 caracteres. | O modelo pode incluir identificadores como empresa/modelo:versão. A chave é vinculada ao destino selecionado. Trocar de empresa exige informar a chave desse destino e revisar o aceite antes de habilitar a IA. |
| Verificação | O portal consultava os metadados de um modelo da OpenAI. | O portal envia uma frase fictícia ao modelo escolhido e valida se a resposta segue o formato esperado pelo classificador. A verificação pode consumir créditos. |
| Atendimento | O worker chamava a OpenAI e registrava o consumo com esse nome fixo. | O worker chama o provedor escolhido e registra o nome e o modelo usados. As configurações OpenAI já salvas continuam utilizáveis. |
| Número de WhatsApp | O cadastro já tinha quatro etapas. O operador precisava deduzir parte da navegação na Meta e o guia sugeria gerar o token de verificação manualmente. | O portal indica qual aba abrir, onde buscar os IDs, qual credencial colar e quando escolher a fila. Para o webhook, mostra o par de valores que deve ser copiado e orienta a assinar o campo messages. Depois da ativação, explica como testar de outro celular. |

## Alcance da integração

A IA continua classificando texto para o menu. Agendamentos, confirmações, permissões, filtros e limites de consumo seguem o fluxo existente. A mudança dispensa migração de banco.

Para outra empresa, a equipe cadastra a URL HTTPS de confiança em AI_EXTRA_ENDPOINTS na API e no worker. O endpoint precisa aceitar Chat Completions com autenticação Bearer, responder ao pedido em texto JSON e informar o uso de tokens. Para APIs com protocolo ou autenticação próprios, é necessário um gateway compatível. A verificação usa uma frase sintética e não homologa todos os modelos de uma empresa.

[Configuração da IA](../ai-provider-setup.md) · [Passo a passo para vincular o WhatsApp](../whatsapp-provider-setup.md)

## Verificação local

- **Backend:** 178 testes aprovados, incluindo as suítes de agenda, permissões, cotas, mensageria e portal. O teste de integração do worker percorreu o menu com respostas simuladas de OpenAI e Gemini e conferiu o provedor registrado no consumo. O ciclo de atualização, reversão e reaplicação das migrações passou em PostgreSQL descartável.
- **Portal:** 13 testes aprovados. Os novos casos cobrem a troca de provedor e a consulta dos dados do webhook após sua confirmação. O build de produção e o ESLint passaram.
- **Análise do código:** Ruff, mypy e a verificação de diferenças do Git passaram.
- **Homologação externa:** a execução usou respostas simuladas dos provedores. A validação com a chave e o modelo escolhidos pela clínica e o teste de ida e volta com seu número real dependem das respectivas contas.
