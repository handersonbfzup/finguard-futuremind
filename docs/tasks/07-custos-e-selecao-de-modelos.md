# Tarefa: Consolidar custos e seleção de modelos

## Objetivo

Demonstrar, com métricas de custo e qualidade, a escolha do modelo adequado para cada etapa do nível 3.

## Contexto atual

O projeto registra tokens e custo estimado, mas o runtime usa `amazon.nova-lite-v1:0` tanto para triagem quanto para risco. O ADR prevê um modelo leve para triagem e um modelo mais robusto para análises complexas.

## Escopo

- Separar configurações de modelo para triagem, risco, rotulagem e embeddings.
- Comparar preço, latência, limite de contexto e qualidade dos modelos disponíveis na conta.
- Atualizar a tabela de preços com fonte e data de consulta.
- Medir custo por reclamação e por lote, incluindo retries e guardrail.
- Definir limites de orçamento e comportamento quando forem atingidos.
- Registrar no resultado qual modelo e modo foram usados.
- Documentar por que o modelo escolhido atende à complexidade de cada tarefa.

## Critérios de aceite

- O modelo de triagem pode ser alterado sem modificar o código dos agentes.
- Existe comparação quantitativa de custo/latência/qualidade.
- O dashboard distingue custo real estimado, custo de fallback local e chamadas bloqueadas antes do LLM.
- Preços e limitações estão datados e têm fonte identificável.
- A banca consegue reproduzir a justificativa a partir do ADR e dos logs.

## Evidências esperadas

- Configuração por ambiente/modelo.
- Tabela comparativa atualizada.
- Execução amostral com métricas por agente.
- Atualização do ADR e da documentação de comandos.
