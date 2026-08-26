# Tarefa: Integrar Amazon Bedrock Guardrails oficial

## Objetivo

Implementar o Bedrock Guardrails oficial como primeira validação de entrada do pipeline, mantendo o filtro regex local como pré-filtro barato.

## Contexto atual

O grafo já começa em `guardrail_entrada`, mas esse nó usa somente regras locais em `finguard/guardrails.py`. O desafio exige o serviço Amazon Bedrock Guardrails no nível 3.

## Escopo

- Criar cliente/configuração para `apply_guardrail` do `bedrock-runtime`.
- Receber `guardrailIdentifier` e `guardrailVersion` por variável de ambiente ou configuração segura.
- Executar o pré-filtro local antes da chamada AWS e chamar o guardrail oficial para entradas não bloqueadas localmente.
- Bloquear prompt injection, jailbreak, extração de instruções, exfiltração, conteúdo fora do domínio e ameaças.
- Mapear `GUARDRAIL_INTERVENED` para o mesmo ramo `resposta_bloqueio` do grafo.
- Não enviar nem registrar conteúdo sensível desnecessário.
- Implementar modo explícito offline para testes, sem simular que o guardrail AWS foi executado.

## Critérios de aceite

- `guardrail_entrada` continua sendo o primeiro nó do grafo.
- Nenhuma entrada bloqueada pelo serviço oficial chega a `agente_triagem`.
- A resposta de bloqueio permanece educada, em português e sem detalhes internos.
- Ausência de configuração AWS produz erro operacional claro ou modo offline explícito, nunca um falso status de aprovação.
- Testes com cliente AWS mockado cobrem aprovação, intervenção, erro e timeout.
- Logs registram decisão, latência e status, sem armazenar a reclamação integral.
- A documentação de execução informa as variáveis, permissões IAM mínimas e procedimento de teste.

## Evidências esperadas

- Implementação no módulo de guardrails/cliente AWS.
- Testes automatizados do contrato de retorno.
- Exemplo de configuração sem credenciais reais.
- Log ou relatório de uma execução demonstrando PASS e BLOCK.

## Dependências

- Credenciais AWS de desenvolvimento.
- Guardrail criado e versionado na conta/região do desafio.
- Permissão IAM restrita ao guardrail e aos modelos utilizados.
