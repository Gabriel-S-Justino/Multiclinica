# Relatório F0 — Descoberta

Data: 31/10/2026. Estado: documentação produzida; gate de aprovação pendente.

## Entrega

Escopo MVP e exclusões, D1–D16 propostas, metas não funcionais, perguntas bloqueantes, ambiguidades e resolução proposta. Não há aplicação, migrations, integrações ou testes de execução nesta fase.

## Arquivos

- `README.md`: entrada do projeto e estado real.
- `docs/discovery.md`: premissas, perguntas, metas e ambiguidades.
- `docs/decisions/0001-discovery-defaults.md`: D1–D16 com status e dependências.
- `docs/requirements.md`: escopo e rastreabilidade inicial por grupo.
- `docs/reports/f0-discovery.md`: este relatório.

## Evidências e validação

- Leitura de `C:\Users\Cleber\Downloads\Master.md` via `Get-Content -Raw`: sucesso.
- `git status --short --branch` antes da edição: `## main...origin/main`, sem alterações.
- `rg --files --hidden -g '!.git/**'` antes da edição: somente `README.md`.
- Validação documental e `git diff --check`: resultados em `docs/reports/f0-validation.txt`, gerado após a escrita.
- Testes de aplicação: não executados, pois não existe implementação. A F0 é documental.

## Riscos e pendências

Regras de identificação, vínculo com dependentes, políticas da clínica, orçamento, retenção, contratos, planos e regiões ainda não definidos. APIs, limites, preços, versões e capacidades externas estão **não verificados** nesta fase; a documentação não os apresenta como fatos. Serão consultadas fontes oficiais com data antes das respectivas implementações.

## Gate

Solicitar aprovação da F0 e dos padrões propostos para iniciar F1. Não avançar automaticamente. As perguntas com prazo posterior podem permanecer abertas durante partes independentes do design; não autorizam implementar a funcionalidade bloqueada.
