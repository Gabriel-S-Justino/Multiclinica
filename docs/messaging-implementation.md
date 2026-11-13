# Operação do WhatsApp

O Admin configura credenciais e vincula o número no portal. O webhook valida a assinatura antes de ler o JSON, confere a conta e o número, deduplica eventos e confirma recebimento depois de persistir o evento cifrado. Consulte o [roteiro assistido](integration-onboarding.md).

## Executor

Execute em um serviço supervisionado, com reinício automático e as mesmas configurações de runtime do portal. Configure `DATABASE_URL`, `PUBLIC_ORIGIN`, `APP_ENV`, `TOKEN_KEY` e `FIELD_KEY` no gerenciador de segredos. Use a role de runtime. O executor consulta os canais ativos em cada ciclo.

```sh
uv sync --frozen --no-dev --python 3.12
uv run --frozen --no-dev python -m backend.messaging_cli worker --interval 5 --limit 10
```

A aplicação HTTP e o executor são processos separados. Os comandos `process` e `send` com `--channel-id` continuam disponíveis para diagnóstico pontual.

Execute `uv run --frozen --no-dev python -m backend.messaging_cli status` para ver os totais de entrada e saída por canal e se o envio está habilitado. A saída contém somente identificadores de canal e metadados operacionais.

Em infraestrutura de contêineres, construa a imagem com `docker build -f Dockerfile.worker -t multiclinica-worker .` e configure as variáveis de runtime no serviço. Configure reinício automático e encaminhamento dos logs para o monitoramento da equipe. O processo não expõe porta HTTP.

## Ativar ou pausar envio

A equipe usa o comando abaixo com `MIGRATION_DATABASE_URL` apenas no ambiente de administração, após conferir o webhook e os dados do canal. Habilite primeiro com número e destinatários de teste.

```sh
uv run --frozen python -m backend.messaging_cli enable --channel-id UUID_DO_CANAL
uv run --frozen python -m backend.messaging_cli disable --channel-id UUID_DO_CANAL
```

O canal começa com envio desligado. A habilitação confere credenciais presentes, fila ativa e correspondência dos identificadores. Confirme a entrega pelo retorno da Meta. Durante a pausa, o processamento de entrada continua e o envio pendente aguarda a retomada, sujeito à janela e à preferência do contato.

## Falhas e limites

Monitore atraso, jobs com falha, entregas de estado desconhecido e parada do executor. A reconciliação de entregas desconhecidas é feita com a Meta antes de qualquer reenvio. Falhas transitórias elegíveis têm retentativas limitadas. Fora da janela de atendimento, o sistema bloqueia texto livre. O projeto ainda não oferece templates proativos.

Cada clínica tem um canal. A troca de conta, número ou fila exige rotação acompanhada. O comando legado `provision` fica disponível para operação administrativa. Para o fluxo habitual, vincule o canal no portal.
