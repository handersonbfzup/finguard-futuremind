# Tarefa: Processamento em lote (batch) nas chamadas ao Bedrock

## Objetivo

Agrupar N reclamações por chamada ao LLM (triagem e risco), em vez de 1 chamada por
reclamação, para reduzir custo e latência do pipeline, preservando corretude e
rastreabilidade por registro.

## Contexto atual

- O pipeline processa uma reclamação por vez: cada linha percorre o grafo
  (`guardrail_entrada -> agente_triagem -> agente_risco -> agente_relatorio ->
  guardrail_saida`), com 2 chamadas Bedrock por reclamação (triagem e risco).
- A paralelização atual é entre reclamações (`--workers`, default 16, via
  `ThreadPoolExecutor` em `main.py`), não dentro de uma chamada.
- O prompt de sistema da triagem (regras de categoria/produto/sentimento/urgência,
  `_REGRAS_POL_SAC_001`) é reenviado por inteiro em cada uma das ~500 chamadas — overhead
  fixo multiplicado pelo número de registros.
- 500 registros no dataset de referência → ~1000 chamadas Bedrock (triagem + risco) na
  execução completa hoje.

## Por que lote reduz custo/latência

- O overhead de rede (round-trip) e do prompt de sistema fixo é diluído por N itens em
  vez de repetido por registro (ex.: ~500 chamadas de triagem viram ~5-20 chamadas,
  dependendo do tamanho de lote viável).
- Menos chamadas reduz o risco de enfileiramento/throttling em picos.
- Tokens de entrada específicos de cada reclamação (o texto em si) não diminuem — o
  ganho vem do prompt de sistema e do overhead de chamada, não do conteúdo variável.

## Riscos e limitações a validar antes de fixar `--batch-size`

1. **Limite de tokens de saída do modelo.** A família Amazon Nova (Micro/Lite/Pro) tem
   teto **fixo de 5.000 tokens** em `maxTokens` por resposta (limite da API, documentado
   em docs.aws.amazon.com/nova — não é configuração nossa, não dá para contornar). Um lote
   de 100 itens retornando categoria/produto/sentimento/urgência/resumo por item estoura
   esse teto e trunca o JSON.

   Telemetria real já coletada neste projeto (`logs/*.jsonl`, `tokens_saida` por chamada
   individual) dá uma base concreta para dimensionar o lote em vez de estimar:

   | Agente  | n chamadas | média | p90 | máximo |
   |---|---|---|---|---|
   | triagem | 1036 | 113,9 | 131 | 177 |
   | risco   | 1029 | 149,6 | 180 | 251 |

   O agente de risco é o mais caro em tokens de saída (justificativa mais longa que o
   resumo da triagem) e deve ser o fator limitante do tamanho de lote. Recomendação
   inicial: `maxTokens` do lote em ~4500 (90% do teto, com margem) e orçamento de ~300
   tokens/item (acima do máximo já observado de 251, para cobrir variância) — resulta em
   `batch_size ≈ 4500 / 300 ≈ 15`. Começar com `--batch-size` entre 15 e 20 e recalibrar
   com medição real, não assumir 100. Se for necessário lote maior, encurtar
   `resumo`/`justificativa` no modo lote (ex.: 1 frase em vez de 2–3) para reduzir
   tokens/item.
2. **Detecção de truncamento não pode depender só da contagem de tokens.** O sinal
   definitivo de corte é o campo `stopReason` retornado pelo `converse()` (`"max_tokens"`
   quando a resposta foi cortada) — o fallback por bissecção deve checar esse campo, além
   de tentar o parse do JSON.
3. **Fragilidade de parsing cresce com o tamanho da resposta.** Um erro de formatação em
   1 item não pode derrubar o lote inteiro.
4. **Contaminação/injeção cruzada entre itens do lote.** Uma reclamação maliciosa dentro
   do lote pode tentar influenciar a classificação de outras reclamações do mesmo lote —
   o prompt precisa reforçar isolamento explícito por item (cada reclamação é avaliada de
   forma independente; instruções em uma não alteram o julgamento de outra).
5. **Rastreabilidade e custo por reclamação.** Hoje `registrar()` grava 1 chamada = 1
   `reclamacao_id`. Em lote, 1 chamada cobre N ids. `finguard/dashboard_logs.py`
   (`_agregar_tokens`) precisa ratear tokens/custo do lote entre as reclamações ou expor
   métricas agregadas por lote sem quebrar o dashboard atual.
6. **Agente de risco depende de RAG por item.** O contexto de política
   (`recuperar_contexto_politica`) é local/determinístico mas específico por reclamação
   (depende da classificação e do canal) — precisa ser calculado por item antes de montar
   o prompt de lote do agente de risco.
7. **Guardrail de entrada continua individual.** É heurístico e local (sem LLM); deve
   continuar rodando por registro, filtrando quem entra no lote de triagem (não faz
   sentido nem é seguro incluir reclamações já bloqueadas no lote).
8. **Retry parcial.** Se um lote falhar no parse ou a contagem de ids não bater com o
   esperado, a estratégia deve bissectar o lote (dividir ao meio) e tentar de novo, até o
   nível de chamada individual se necessário — nunca descartar o lote inteiro silenciosamente.

## Escopo (fases sugeridas)

### Fase 1 — Cliente Bedrock em lote

- Novas funções em `finguard/bedrock_client.py`: `classificar_reclamacoes_lote(itens:
  list[{id, texto}]) -> dict[id, ClassificacaoReclamacao]` e `analisar_risco_lote(itens)
  -> dict[id, (nivel, justificativa)]`.
- Prompt de sistema dedicado ao lote: entrada é um array JSON `[{"id": ..., "texto":
  ...}]`; saída deve ser um array JSON do mesmo tamanho, com todos os `id`s de entrada
  presentes na saída; reforçar isolamento entre itens e anti-injeção cruzada.
- Parsing tolerante: validar que todos os ids pedidos vieram na resposta; ids
  faltantes/inválidos viram erro individual daquele item, sem invalidar o restante do lote.
- Fallback recursivo (bissecção) para lotes que falham no parse ou têm resposta truncada.

### Fase 2 — Orquestração em `main.py`

- Novo parâmetro `--batch-size` (default `None`/0 = modo atual sem lote; compatibilidade
  total com o comportamento hoje documentado).
- Rodar `guardrail_entrada` localmente (sem LLM) para todas as linhas antes de montar os
  lotes, separando bloqueadas de não-bloqueadas.
- Dividir as não-bloqueadas em lotes de `--batch-size` e chamar
  `classificar_reclamacoes_lote` por lote (lotes podem ser processados em paralelo entre
  si, análogo ao `--workers` atual).
- Calcular o contexto de política (RAG) por item localmente a partir da classificação
  retornada, depois chamar `analisar_risco_lote` por lote.
- Popular o estado inicial de cada linha com os valores pré-computados
  (`_classificacao_precomputada`, `_risco_precomputado`) e invocar o grafo normalmente por
  linha — `agente_relatorio` e `guardrail_saida` continuam sem alteração.

### Fase 3 — Ajustes em `finguard/state.py` / `finguard/agentes.py`

- Adicionar campos opcionais ao `FinGuardState` para os valores pré-computados do lote.
- `no_agente_triagem` / `no_agente_risco`: se o valor pré-computado existir no estado,
  usar direto (sem chamar Bedrock); caso contrário, manter o comportamento atual
  (individual com LLM ou heurístico em `--sem-llm`).

### Fase 4 — Logging e dashboard

- Novas ações de log (`chamada_bedrock_triagem_lote` / `chamada_bedrock_risco_lote`) com
  `reclamacoes_ids: list[str]` e uso de tokens agregado do lote inteiro.
- Atualizar `_agregar_tokens` em `finguard/dashboard_logs.py` para ratear tokens/custo do
  lote entre as reclamações (ex.: dividir por N) nas métricas por agente, e exibir no
  dashboard quantas chamadas foram economizadas versus o modo individual.

### Fase 5 — Testes e validação

- Testes unitários com mocks do Bedrock cobrindo: lote ok, lote com 1 item malformado,
  resposta truncada (aciona bissecção), ids faltantes, ids extras/inesperados, tentativa
  de injeção cruzada entre itens do mesmo lote.
- Benchmark real no dataset de 500 registros comparando modo atual vs. `--batch-size`
  (candidatos: 10, 25, 50, 100), medindo tempo total, nº de chamadas Bedrock, tokens
  totais e custo estimado — sem estimar números sem medir de fato.

## Critérios de aceite

- `--batch-size` é opcional; sem o parâmetro, comportamento e saída são idênticos aos
  atuais (regressão zero no modo individual).
- Falha de parsing em um item do lote não derruba os demais itens do mesmo lote.
- Rastreabilidade por reclamação é preservada no dashboard de logs mesmo em modo lote.
- Ganho real de custo/latência é medido (não estimado) com o dataset de 500 registros e
  documentado.
- Uma reclamação dentro de um lote não consegue alterar a classificação/risco de outra
  reclamação do mesmo lote (coberto por teste de injeção cruzada).

## Evidências esperadas

- Execução comparativa (mesmo dataset, mesmo modelo) com e sem `--batch-size`, com
  métricas de tempo total, nº de chamadas Bedrock, tokens totais e custo estimado.
- Testes automatizados cobrindo parsing tolerante e bissecção de lote.
- Atualização de `docs/processo.md` com o novo parâmetro e o tamanho de lote recomendado
  a partir da medição real.
