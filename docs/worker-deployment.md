# Processador de mensagens (worker sempre ligado)

O portal e a API rodam na Vercel. O processador de mensagens do WhatsApp roda à parte, num serviço que fica ligado o tempo todo. Sem ele, o webhook recebe as mensagens dos pacientes, mas ninguém responde: as mensagens ficam guardadas e as respostas da equipe ficam na fila.

## O que o processador faz

- Lê as mensagens recebidas pelo webhook, conduz o atendimento automático e consulta a IA quando a clínica ativou essa opção.
- Envia as respostas pelo WhatsApp de cada clínica com o envio ativo.
- Registra um sinal de vida a cada ciclo. A tela de Integrações usa esse sinal para avisar o dono da clínica quando o atendimento automático está fora do ar.
- A cada 10 minutos, apaga sessões, desafios de MFA, códigos de recuperação e contadores de tentativas que já venceram. Nenhum dado clínico é apagado nessa limpeza.

O processador não abre porta HTTP e não precisa de domínio.

## Configuração

Use os mesmos valores de produção da Vercel. Os quatro primeiros precisam ser idênticos aos do portal, senão o processador não consegue ler as credenciais cifradas.

| Variável | Valor |
|---|---|
| `DATABASE_URL` | Mesma URL de runtime usada pela Vercel (papel `clinic_runtime`) |
| `TOKEN_KEY` | Mesmo valor da Vercel |
| `FIELD_KEY` | Mesmo valor da Vercel |
| `PUBLIC_ORIGIN` | `https://multclinicai.vercel.app` |
| `APP_ENV` | `production` |

Nunca configure `MIGRATION_DATABASE_URL` no processador. Ele não precisa de permissões administrativas.

Rode uma única instância. O processador aguenta reinícios e execuções repetidas, mas uma instância basta e mantém a ordem das conversas simples de acompanhar.

## Implantar no Railway

1. Crie um projeto a partir do repositório no GitHub.
2. Em Settings, defina o Dockerfile como `Dockerfile.worker`.
3. Em Variables, cadastre as variáveis da tabela acima.
4. Em Settings, deixe a política de reinício como "Always".
5. Faça o deploy. O log deve mostrar "Processador de mensagens iniciado".

## Implantar no Render

1. Crie um Background Worker a partir do repositório.
2. Escolha Docker como ambiente e informe `Dockerfile.worker` como caminho do Dockerfile.
3. Cadastre as variáveis da tabela acima em Environment.
4. Faça o deploy e confira a mesma mensagem no log.

## Conferir se está funcionando

Na tela de Integrações de uma clínica com o WhatsApp vinculado, o aviso "O atendimento automático está fora do ar" deixa de aparecer em até 2 minutos depois que o processador sobe. Pela linha de comando, com as mesmas variáveis:

```sh
uv run --frozen --no-dev python -m backend.messaging_cli status
```

O comando lista, por canal, as mensagens recebidas e enviadas por estado e se o envio está ativo.

## Atualizações e reinícios

Ao publicar uma versão nova, a hospedagem envia SIGTERM. O processador termina o ciclo em andamento e encerra sem interromper uma transação no meio. Mensagens que chegarem nesse intervalo ficam guardadas e são tratadas assim que a nova versão subir.

Aplique as migrações do banco antes de atualizar o processador, como já é feito para o portal.
