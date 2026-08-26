# Tarefa: Completar privacidade e sanitização de saída

## Objetivo

Garantir que nenhuma saída de agente, relatório, log ou mensagem de erro exponha dados pessoais ou linguagem imprópria.

## Contexto atual

O projeto mascara CPF, conta, telefone e algumas palavras ofensivas em `finguard/guardrails.py`. O desafio também exige proteção contra dados pessoais em todas as saídas, e a avaliação identificou lacunas para nome, e-mail, endereço, identificadores e formatos alternativos.

## Escopo

- Expandir detecção/redação para e-mail, nome quando identificável, endereço, dados de cartão, chaves, IDs e formatos comuns de conta/telefone.
- Aplicar sanitização centralizada a resumo, justificativa, ação, fontes RAG, erros e metadados exportados.
- Sanitizar dados antes de qualquer log persistente.
- Evitar guardar a reclamação original em dashboards e arquivos de resultado.
- Definir política para falsos positivos e preservar somente o mínimo necessário para auditoria.
- Manter tom profissional e neutro nas respostas geradas.

## Critérios de aceite

- Testes confirmam que cada tipo de PII fica mascarado em todos os campos de saída.
- Logs não contêm texto original ou valores sensíveis em claro.
- A sanitização ocorre mesmo quando o modelo retorna JSON inválido, conteúdo ofensivo ou erro parcial.
- A resposta de bloqueio não revela padrões detectados nem detalhes do guardrail.
- Há testes de regressão para acentos, pontuação, quebras de linha e formatos alternativos.
- A documentação descreve limites conhecidos da detecção.

## Evidências esperadas

- Função/pipeline único de redaction usado por agentes, persistência e logs.
- Fixtures com PII fictícia.
- Relatório de cobertura dos testes de sanitização.

## Dependências

- Tarefa de testes automatizados.
- Definição de política de retenção e campos permitidos no relatório.
