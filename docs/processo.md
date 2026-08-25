# Processo de Execução e Validação

Este documento descreve o processo operacional para rodar, validar e apresentar resultados do FinGuard.

## 1. Preparação

1. Garantir que as dependências estejam instaladas na venv.
2. Confirmar dataset de entrada (exemplo: dados/dataset_finguard_desafio_3 (5).csv).
3. Para execução com Bedrock, validar profile/região AWS antes do run.

## 2. Fluxo do pipeline

Ordem dos nós no processamento principal:

1. guardrail_entrada
2. agente_triagem
3. agente_risco
4. agente_relatorio
5. guardrail_saida

Desvio condicional:

- Se guardrail_entrada bloquear: resposta_bloqueio e fim.

## 3. Execução recomendada

### 3.1 Validação funcional sem LLM

```bash
venv/bin/python3 main.py --csv "dados/dataset_finguard_desafio_3 (5).csv" --sem-llm
```

Objetivo: validar fluxo, guardrails, roteamento e estrutura de saída sem custo de inferência.

### 3.2 Execução completa com LLM

```bash
venv/bin/python3 main.py --csv "dados/dataset_finguard_desafio_3 (5).csv" --aws-profile bedrock --aws-region us-east-1
```

Parâmetros de controle:

- --workers 16 (default atual).
- --limit para amostras rápidas.
- --out-json, --out-html e --out-html-logs para personalizar artefatos.

## 4. Evidências de execução

Após cada run, verificar:

1. resultado_analise.json
2. dashboard.html
3. dashboard_logs.html
4. logs/execucao_*.jsonl

Critérios mínimos de sucesso:

1. Execução finaliza sem exceções globais.
2. Existe ao menos uma entrada processada ou bloqueada.
3. Dashboard funcional abre corretamente.
4. Dashboard de logs apresenta métricas de latência e status.

## 5. Clusterização (bônus)

### 5.1 Sem LLM

```bash
venv/bin/python3 script_cluster.py --csv "dados/dataset_finguard_desafio_3 (5).csv" --sem-llm
```

### 5.2 Com LLM

```bash
venv/bin/python3 script_cluster.py --csv "dados/dataset_finguard_desafio_3 (5).csv"
```

Resultado esperado: arquivo resultado_clusters.json com k escolhido, avaliação e rótulos.

## 6. Observações de modelos

Defaults atuais no cliente Bedrock:

- triagem: amazon.nova-lite-v1:0
- risco: amazon.nova-lite-v1:0

Se houver mudança de disponibilidade de modelos, atualizar finguard/bedrock_client.py e refletir neste documento.

## 7. Checklist de fechamento

1. Arquivos de saída gerados e acessíveis.
2. Logs sem volume relevante de erro_pipeline.
3. Métricas de tokens e custo estimado (quando aplicável) visíveis no dashboard de logs.
4. Documentação alinhada com os parâmetros atuais da CLI.
