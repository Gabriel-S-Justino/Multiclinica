# Preparação de WhatsApp e IA na Multiclínica

Este documento descreve o fluxo disponível no painel de Integrações. Cadastrar as informações não ativa automaticamente o envio pelo WhatsApp nem a IA.

## Passos de configuração

1. Em Configurações, crie uma fila ativa de atendimento com expediente e atendentes.
2. Na Meta Cloud API obtenha a identificação da WABA, Phone Number ID, versão atual do Graph API, Access Token e App Secret. Crie um Verify Token forte.
3. Em Integrações → WhatsApp, informe os sete campos e clique em Salvar configuração. Os três segredos são criptografados e não retornam na leitura.
4. Clique em Verificar credenciais para uma consulta de metadados à Meta. Isso não prova recebimento do webhook ou capacidade de envio.
5. Clique em Vincular número à clínica. A operação cria um canal e uma conta técnica com menor privilégio. O envio começa desligado.
6. Copie a URL de webhook exibida, cadastre-a na Meta com o Verify Token e assine o evento messages.
7. Implemente um executor durável de mensagens para invocar process e send do módulo backend.messaging_cli. O painel sozinho não agenda workers. O Vercel Hobby não suporta cron a cada minuto.
8. Após testes reais e revisão clínica, de segurança e de privacidade, execute um procedimento aprovado para habilitar o envio. Nunca faça isso apenas para simular sucesso.

## Inteligência artificial

1. Em Integrações → Inteligência artificial, escolha OpenAI, informe o identificador exato do modelo e a API key em um campo protegido.
2. Clique em Verificar credenciais. O botão consulta apenas metadados do modelo; não há geração de respostas.
3. A IA continua desativada: faltam adaptador de produção, avaliação de qualidade, política de dados, orçamento e fluxo clínico aprovado. A fronteira atual permite apenas classificação restrita de intenções, sem diagnóstico nem mutações de consultas.

## Limitações de operação

- Nesta versão, cada clínica admite um canal de WhatsApp; a troca de número exige rotação controlada.
- O número precisa estar autorizado e registrado na Meta. A coexistência com WhatsApp Business App depende das opções oficiais disponíveis para a conta.
- Um canal provisionado recebe webhook com verificação de assinatura, mas não processa nem envia mensagens automaticamente sem worker externo.
- Não use dados reais de pacientes antes da homologação e da aprovação de privacidade, retenção e resposta a incidentes.
- Nenhuma credencial deve ser compartilhada por chat, logs, código ou repositórios.
- A função administrativa de provisionamento está na migração 0006. A aplicação usa MFA recente, valida fila ativa, isolamento da clínica, hash de senha técnica aleatória e envio desativado por padrão.
