# ADR 0007 — IA sem autoridade sobre operações

31/10/2026. Autorizada a execução das partes independentes da F6. D13 (provedor/contrato/região/base e política de dados), orçamento e mensagem de emergência aprovada continuam sem definição. Não habilitar chamada externa ou processamento de texto de paciente por aprovação genérica de execução.

Contrato tipado de interpretação, entradas mínimas explicitamente aprovadas e saídas em enum: a saída do modelo nunca é código, SQL, prompt de sistema, identificador de paciente, chamada de ferramenta ou confirmação. Somente intenções não mutantes podem sugerir menu, busca ou humano. Confirmar/cancelar/remarcar continuam exclusivamente nas opções opacas da máquina F5, após autorização e confirmação humana explícita. Nenhuma saída livre do modelo é mostrada ao paciente.

Falha de configuração, timeout, cota, saída inválida, intenção fora do estado ou tentativa de ferramenta ⇒ menu determinístico. Não iniciar threads locais para interromper chamada: adaptador real precisará impor timeout HTTP e limites de tokens. Provider simulado testa o contrato, sem ser apresentado como integração real.

Regras determinísticas detectam linguagem clínica/urgência antes de qualquer modelo. Sem texto clínico fixo aprovado, automação de urgência permanece bloqueada para ativação; o código orienta apenas transferência e não cria diagnóstico/conselho médico. Cotas precisam ser persistidas e atômicas antes da ativação externa, com custo verificado para o modelo escolhido. Nenhum preço ou orçamento será inventado.

Validação: corpus adversarial, esquema fechado, tool names/IDs/SQL rejeitados, proibição de mutação por inferência, ausência de envio sem consentimento/política, modo degradado. Integração real e medição de qualidade/custo ficam pendentes da escolha fornecida pelo responsável.
