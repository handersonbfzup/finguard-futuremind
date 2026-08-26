# Tarefa: Implementar resiliência e controle de chamadas Bedrock

## Objetivo

Evitar travamentos, custos inesperados e degradação em cascata durante falhas ou limitação do Bedrock.

## Contexto atual

O cliente possui retry com backoff para throttling, mas não possui timeout total, circuit breaker ou política explícita para falhas permanentes.

## Escopo

- Adicionar timeout por chamada e limite de tempo total por reclamação/lote.
- Diferenciar erros transitórios, erros de configuração, recusas de guardrail e respostas inválidas.
- Implementar limite de concorrência e backpressure configuráveis.
- Adicionar circuit breaker ou mecanismo equivalente para falhas repetidas.
- Definir fallback seguro e observável para triagem/risco quando o LLM estiver indisponível.
- Garantir que retries não dupliquem registros nem custos sem controle.
- Registrar tentativa, motivo, duração e resultado sem PII.

## Critérios de aceite

- Nenhuma chamada pode bloquear indefinidamente.
- O lote termina com status por reclamação mesmo quando parte das chamadas falha.
- Erros permanentes não são repetidos pelo mecanismo de retry.
- O fallback não inventa uma classificação LLM e fica identificado no resultado.
- Testes cobrem throttling, timeout, erro de autenticação, resposta inválida e recuperação do circuito.
- O dashboard mostra falhas, retries e uso do fallback.

## Evidências esperadas

- Configuração de timeout/retry/circuit breaker.
- Testes com mocks temporizados e respostas de erro.
- Execução de demonstração com falha controlada.
