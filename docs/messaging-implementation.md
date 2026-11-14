# Operação do WhatsApp

O Admin configura credenciais e vincula o número no portal. O webhook valida a assinatura antes de ler o JSON, confere a conta e o número, deduplica eventos e confirma recebimento depois de persistir o evento cifrado. Consulte o [roteiro assistido](integration-onboarding.md).

## Executor

O passo a passo de implantação está em [processador de mensagens](worker-deployment.md). Execute em um serviço supervisionado, com reinício automático e as mesmas configurações de runtime do portal. Configure `DATABASE_URL`, `PUBLIC_ORIGIN`, `APP_ENV`, `TOKEN_KEY` e `FIELD_KEY` no gerenciador de segredos. Use a role de runtime. O executor consulta os canais ativos em cada ciclo.

```sh
uv sync --frozen --no-dev --python 3.12
uv run --frozen --no-dev python -m backend.messaging_cli worker --interval 5 --limit 10
```

A aplicação HTTP e o executor são processos separados. Os comandos `process` e `send` com `--channel-id` continuam disponíveis para diagnóstico pontual.

Execute `uv run --frozen --no-dev python -m backend.messaging_cli status` para ver os totais de entrada e saída por canal e se o envio está habilitado. A saída contém somente identificadores de canal e metadados operacionais.

Em infraestrutura de contêineres, construa a imagem com `docker build -f Dockerfile.worker -t multiclinica-worker .` e configure as variáveis de runtime no serviço. Configure reinício automático e encaminhamento dos logs para o monitoramento da equipe. O processo não expõe porta HTTP.

## Ativar ou pausar envio

O admin da clínica ativa e pausa o envio na tela de Integrações. Ativar só é possível depois que a Meta confirmou a conexão e o webhook. Pausar é sempre permitido e é o caminho para trocar um token: pause, informe o token novo, verifique e ative de novo. Durante a pausa, as mensagens recebidas continuam guardadas e as respostas pendentes aguardam a retomada.

Os comandos `enable` e `disable` continuam disponíveis para a equipe Multiclinica, com `MIGRATION_DATABASE_URL`, apenas em situações excepcionais.

## Falhas e limites

Monitore atraso, jobs com falha, entregas de estado desconhecido e parada do executor. Falhas de conexão antes de chegar à Meta são reenviadas automaticamente. Entregas de estado desconhecido não são reenviadas, para não duplicar mensagens; a tela de Integrações mostra a quantidade de falhas dos últimos 7 dias. Falhas transitórias elegíveis têm retentativas limitadas. Fora da janela de atendimento, o sistema bloqueia texto livre. O projeto ainda não oferece templates proativos.

Cada clínica tem um canal. A troca de conta, número ou fila exige rotação acompanhada. O número é vinculado pelo portal, depois da verificação na Meta.
