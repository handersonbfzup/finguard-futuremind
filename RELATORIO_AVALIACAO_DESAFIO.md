# Relatório de avaliação — FinGuard / Future Minds 3

**Data da avaliação:** 26/08/2026  
**Escopo:** código-fonte, documentação, artefatos JSON/HTML, logs e conteúdo versionado do projeto.  
**Critério:** requisitos descritos no desafio para os níveis 1 a 4.

## 1. Resumo executivo

| Área | Avaliação |
|---|---|
| Nível 1 — Classificador Inteligente | **Atendido**, com ressalva sobre a qualidade da classificação offline e sobre a ausência de testes-fonte versionados |
| Nível 2 — Orquestrador de Análise | **Atendido** no desenho e na execução do pipeline |
| Nível 3 — Arquiteto da Solução | **Parcial**: guardrails locais, saída sanitizada e ADR existem; o Bedrock Guardrails oficial, obrigatório, não está integrado |
| Nível 4 — Cientista de Dados | **Parcial como bônus**: há embeddings TF-IDF, K-Means e Silhouette; não há treino/deploy no SageMaker |
| Entregáveis | **Majoritariamente atendidos**: CLI, JSON, dashboards, logs, ADR e documentação estão presentes |
| Prontidão para produção | **Ainda não demonstrada**: faltam testes automatizados, guardrail gerenciado, controles operacionais e validação de qualidade com ground truth |

**Conclusão:** o projeto demonstra uma solução funcional e bem estruturada para os níveis 1 e 2, além de uma boa base de segurança determinística e observabilidade. Para declarar conformidade integral com o desafio avançado, o ponto bloqueador é a integração real do **Amazon Bedrock Guardrails** como primeiro nó de proteção. O bônus de ML é uma implementação local útil, mas não atende à modalidade funcional SageMaker descrita no enunciado.

## 2. Evidências principais

- O grafo usa `guardrail_entrada` como ponto de entrada, roteia bloqueios para `resposta_bloqueio` e leva entradas aceitas por triagem, risco, relatório e `guardrail_saida` em [finguard/grafo.py](finguard/grafo.py#L26-L52).
- Os enums e o modelo Pydantic cobrem as categorias, produtos, sentimentos e urgências do Nível 1 em [finguard/schemas.py](finguard/schemas.py#L8-L63).
- O filtro de entrada é local, baseado em regex, e o próprio módulo declara que é independente do Bedrock Guardrails oficial em [finguard/guardrails.py](finguard/guardrails.py#L1-L10). A saída mascara CPF, conta, telefone e linguagem ofensiva em [finguard/guardrails.py](finguard/guardrails.py#L78-L103).
- A execução em lote lê CSV, usa `ThreadPoolExecutor`, grava JSON e renderiza dashboards em [main.py](main.py#L39-L175).
- O cliente Bedrock usa `converse`, modelos configuráveis e retry para throttling em [finguard/bedrock_client.py](finguard/bedrock_client.py#L27-L67). O runtime atual usa `amazon.nova-lite-v1:0` tanto na triagem quanto no risco em [finguard/bedrock_client.py](finguard/bedrock_client.py#L31-L36).
- O logging estruturado é JSONL, com `execucao_id`, ação, status, duração, reclamação e detalhes em [finguard/logging_config.py](finguard/logging_config.py#L20-L62).
- Há documentação do fluxo, comandos e decisões em [docs/readme.md](docs/readme.md), [docs/processo.md](docs/processo.md) e [adr_finguard.html](adr_finguard.html).
- A implementação de clusterização local está em [finguard/embeddings.py](finguard/embeddings.py), [finguard/clustering.py](finguard/clustering.py) e [script_cluster.py](script_cluster.py). O próprio código diferencia TF-IDF local do caminho Bedrock/Titan.

## 3. Matriz de atendimento por nível

### 3.1 Nível 1 — O Classificador Inteligente

| Requisito | Status | Evidência e avaliação |
|---|---|---|
| Receber reclamações em texto livre | **Atendido** | A CLI lê o campo `texto_reclamacao` do CSV e processa cada registro; o fluxo está documentado em [docs/readme.md](docs/readme.md). |
| Categoria nas seis opções exigidas | **Atendido** | Enum completo em [finguard/schemas.py](finguard/schemas.py#L8-L15). |
| Produto nas seis opções exigidas | **Atendido** | Enum completo, incluindo `Não Identificado`, em [finguard/schemas.py](finguard/schemas.py#L17-L24). |
| Sentimento nas quatro opções exigidas | **Atendido** | Enum em [finguard/schemas.py](finguard/schemas.py#L26-L31). |
| Urgência nas quatro opções exigidas | **Atendido** | Enum em [finguard/schemas.py](finguard/schemas.py#L33-L38). |
| Resumo padronizado de 2–3 linhas/frases | **Parcial** | O prompt exige 2–3 frases em [finguard/bedrock_client.py](finguard/bedrock_client.py#L90-L109), mas o fallback offline usa valores padrão e não demonstra resumo sem LLM. Não há teste de aderência ao tamanho/qualidade do resumo. |
| Ofuscar/remover linguagem imprópria | **Atendido** | Máscara de palavras ofensivas na saída em [finguard/guardrails.py](finguard/guardrails.py#L82-L103). A cobertura é uma lista finita, portanto deve ser tratada como proteção complementar. |
| Saída estruturada JSON/CSV | **Atendido** | `ResultadoReclamacao` é validado por Pydantic e salvo como JSON em [main.py](main.py#L132-L175). |
| Aplicação demonstrável | **Atendido** | CLI com modo Bedrock e `--sem-llm`, parâmetros de lote e caminhos de saída em [main.py](main.py#L177-L260). |
| RAG para política interna | **Pendente** | Não foi encontrada implementação-fonte de RAG nem a fonte `KS_POLITICA_INTERNA.pdf` no workspace. A política aparece embutida como texto de prompt em [finguard/bedrock_client.py](finguard/bedrock_client.py#L80-L88), o que não substitui acesso contextual por RAG. |

### 3.2 Nível 2 — O Orquestrador de Análise

| Requisito | Status | Evidência e avaliação |
|---|---|---|
| Framework de orquestração | **Atendido** | `StateGraph` com nós e arestas condicionais em [finguard/grafo.py](finguard/grafo.py#L13-L52). |
| Recepção e estruturação | **Atendido** | `no_agente_triagem` produz a classificação estruturada em [finguard/agentes.py](finguard/agentes.py#L84-L109). |
| Análise de fraude, regulação, reputação e escalação | **Parcial** | Há heurística de risco por canal e gatilhos, seguida de refinamento LLM em [finguard/agentes.py](finguard/agentes.py#L112-L138). A cobertura das regras é implementada, mas não há suíte de testes nem matriz de casos esperados para demonstrar precisão. |
| Relatório gerencial e recomendações | **Atendido** | Ação recomendada e escalação para risco alto/crítico em [finguard/agentes.py](finguard/agentes.py#L141-L151); dashboard e lista de críticos em [main.py](main.py#L137-L174). |
| Processamento paralelo | **Atendido** | A CLI oferece `--workers` e processamento concorrente por reclamação em [main.py](main.py#L90-L130). |
| Logs de entrada, saída e tempo por agente | **Atendido** | Cada nó cria log com agente, resumo, saída e duração; o estado acumula logs em [finguard/state.py](finguard/state.py#L7-L28) e [finguard/agentes.py](finguard/agentes.py#L31-L54). |
| Rastreabilidade do fluxo | **Atendido** | O `execucao_id`, `reclamacao_id`, ação e status são persistidos no JSONL em [finguard/logging_config.py](finguard/logging_config.py#L33-L62). |
| Relatório final em arquivo | **Atendido** | JSON, dashboard funcional, dashboard de logs e arquivo JSONL são gerados pela CLI em [main.py](main.py#L209-L257). |
| Resiliência | **Parcial** | Retry exponencial para throttling em [finguard/bedrock_client.py](finguard/bedrock_client.py#L54-L67). Não há timeout total, circuit breaker ou política explícita de fallback após falhas permanentes do Bedrock. |

### 3.3 Nível 3 — O Arquiteto da Solução

| Requisito | Status | Evidência e avaliação |
|---|---|---|
| Bedrock Guardrails oficial como primeiro nó | **Pendente crítico** | O primeiro nó é um guardrail regex local, mas não há chamada `apply_guardrail`/identificador de guardrail da AWS. O módulo declara a independência do serviço oficial em [finguard/guardrails.py](finguard/guardrails.py#L1-L5), e o ADR registra a integração como pendente em [adr_finguard.html](adr_finguard.html). |
| Bloquear prompt injection, abuso e ameaças | **Parcial** | Os padrões locais cobrem extração de prompt, jailbreak, exfiltração e ameaças em [finguard/guardrails.py](finguard/guardrails.py#L17-L45). O mecanismo não fornece a cobertura gerenciada exigida pelo nível avançado e não há teste automatizado versionado. |
| Resposta de bloqueio educada, em português e sem detalhes internos | **Atendido** | Texto fixo e genérico em [finguard/guardrails.py](finguard/guardrails.py#L68-L73), conectado ao ramo de bloqueio em [finguard/grafo.py](finguard/grafo.py#L41-L50). |
| Guardrail de saída contra PII | **Parcial** | CPF, padrões de conta e telefone são mascarados em [finguard/guardrails.py](finguard/guardrails.py#L78-L103) e aplicado aos campos produzidos em [finguard/agentes.py](finguard/agentes.py#L154-L184). Não cobre de forma demonstrada todas as PII pedidas no desafio, como nome, e-mail, endereço e identificadores variados. |
| Tom profissional e neutro | **Parcial** | O prompt e a máscara de ofensas ajudam, mas não há validador semântico de tom nem testes de regressão. |
| ADR navegável | **Atendido** | [adr_finguard.html](adr_finguard.html) contém contexto, alternativas, decisão, consequências, custos e segurança. |
| Pelo menos duas alternativas arquiteturais | **Atendido** | Comparação registrada no ADR, incluindo opção monolítica, pipeline simples e multiagente. |
| Justificativa técnica e financeira | **Atendido com ressalva** | Há comparação de modelos e custo estimado no ADR e dashboard de tokens em [finguard/dashboard_logs.py](finguard/dashboard_logs.py#L22-L31). Os preços são referências estáticas e devem ser atualizados antes de uma decisão financeira real. |
| Proteção contra persistência de dados sensíveis | **Parcial** | A sanitização ocorre em campos textuais finais, mas os logs de entrada usam resumo truncado em vez de uma garantia formal de redaction para todo conteúdo. Não há criptografia/retention policy implementadas. |
| IAM, credenciais temporárias e orçamento | **Documentado, não implementado** | Recomendações aparecem no ADR, porém não há IaC, AWS Budgets, alarmes ou integração STS no projeto. |

### 3.4 Nível 4 — O Cientista de Dados (bônus)

| Requisito | Status | Evidência e avaliação |
|---|---|---|
| Pipeline de embeddings | **Parcial** | TF-IDF local funciona sem custo; caminho Titan/Bedrock está previsto em [finguard/embeddings.py](finguard/embeddings.py). Não há evidência de execução real do Titan no ambiente avaliado. |
| Agrupamento não supervisionado | **Atendido localmente** | K-Means e seleção de `k` por Silhouette estão implementados em [finguard/clustering.py](finguard/clustering.py) e acionados por [script_cluster.py](script_cluster.py). |
| Métrica de avaliação | **Atendido** | O pipeline calcula inércia e Silhouette para os valores de `k` testados; existe artefato [resultado_clusters.json](resultado_clusters.json). |
| Interpretação/rotulagem dos clusters | **Parcial** | Há rotulagem por fallback local e função LLM prevista. A qualidade dos rótulos LLM não está demonstrada por execução ou teste. |
| Treino no SageMaker | **Pendente** | O K-Means roda localmente; não há script de treinamento SageMaker nem artefato de modelo versionado em S3. |
| Deploy em endpoint SageMaker | **Pendente** | [script_cleanup.py](script_cleanup.py) apenas lista/remove recursos existentes; não cria nem integra um endpoint ao pipeline. |
| Remoção do endpoint ao final | **Parcial** | Existe limpeza explícita com `--confirm` em [script_cleanup.py](script_cleanup.py#L45-L92), mas não há endpoint criado pelo projeto nem automação pós-execução. |
| Processar dataset completo em menos de 10 minutos | **Não comprovado** | Há documentação de execuções e modo paralelo, mas não existe benchmark reproduzível específico do pipeline de embeddings completo com critério de 10 minutos. |
| Comparação crítica com categorias pré-definidas | **Parcial** | O ADR/documentos justificam o uso local e exibem resultados, mas não há análise quantitativa clara de concordância entre clusters e categorias. |

## 4. Entregáveis encontrados

| Entregável esperado | Status |
|---|---|
| Código funcional | **Atendido** |
| CLI para execução | **Atendido** |
| JSON de resultados | **Atendido**: [resultado_analise.json](resultado_analise.json) |
| Dashboard HTML | **Atendido**: [dashboard.html](dashboard.html) |
| Dashboard de logs, latência, tokens e custo | **Atendido**: [dashboard_logs.html](dashboard_logs.html) e [finguard/dashboard_logs.py](finguard/dashboard_logs.py) |
| Logs estruturados por execução | **Atendido**: [logs](logs) |
| ADR HTML navegável | **Atendido**: [adr_finguard.html](adr_finguard.html) |
| Documentação de execução | **Atendido**: [docs/readme.md](docs/readme.md), [docs/processo.md](docs/processo.md), [docs/comandos.md](docs/comandos.md) |
| Prompts/responsabilidades dos agentes | **Atendido como documentação**: [agents](agents) |
| Resultado de clusterização | **Atendido localmente**: [resultado_clusters.json](resultado_clusters.json) |
| Testes automatizados versionados | **Pendente**: a pasta `tests/` não contém arquivos-fonte de teste; há apenas um artefato `__pycache__` compilado |
| Política interna/RAG entregue | **Pendente**: não há fonte RAG ou documento de política identificável no workspace |

## 5. Pontos fortes

1. O primeiro nó do grafo é uma barreira de entrada e há caminho de bloqueio explícito, conforme exigido pelo desenho do nível 3.
2. A separação entre triagem, risco, relatório e sanitização facilita auditoria e evolução.
3. O modo `--sem-llm` permite demonstrar o fluxo localmente sem credenciais ou custo de inferência.
4. O projeto registra execução, agente, duração, status, tokens e custo estimado, o que favorece a apresentação para a banca.
5. O uso de Pydantic restringe os valores dos campos principais e reduz saídas fora do contrato.
6. A clusterização local inclui seleção de `k` e métricas, indo além de uma simples contagem por categoria.
7. O ADR é direto sobre trade-offs, modelos temporários e a limitação atual do Bedrock Guardrails, o que é melhor do que declarar como pronto um componente ausente.

## 6. Pontos a atender antes da entrega final

### Prioridade alta

1. Integrar o **Amazon Bedrock Guardrails oficial** via API do runtime, com configuração por ambiente, identificador/versão, tratamento de bloqueio e logs sem conteúdo sensível. O filtro regex pode permanecer como pré-filtro barato.
2. Criar testes-fonte versionados para guardrails de entrada/saída, schemas, roteamento do grafo, bloqueios, PII, ofensas, fallback sem LLM e parsing das respostas do Bedrock.
3. Entregar ou implementar o RAG da política interna, com fonte, chunking, recuperação, metadados e testes que provem que as regras usadas pelo risco vêm do contexto recuperado.
4. Definir uma avaliação de qualidade com casos esperados ou conjunto rotulado: acurácia/F1 por categoria, produto, sentimento e urgência; cobertura de bloqueios; falsos positivos; qualidade do resumo e dos rótulos de cluster.

### Prioridade média

1. Completar a sanitização de PII para e-mail, nome, endereço, IDs e formatos alternativos, inclusive em logs e mensagens de erro.
2. Adicionar timeout total, limite de concorrência configurável, circuit breaker e fallback explícito para erros permanentes do Bedrock.
3. Implementar ou documentar operacionalmente retenção e criptografia dos logs, IAM de menor privilégio, credenciais temporárias, AWS Budgets/CloudWatch e procedimento de desprovisionamento.
4. Separar modelo leve para triagem e modelo mais robusto somente para risco quando a disponibilidade permitir, medindo custo e qualidade da combinação.
5. Para reivindicar o bônus funcional, criar pipeline SageMaker de treino, versionamento em S3, endpoint, integração com o grafo e remoção automatizada ao final. Caso o time opte pela modalidade arquitetural, explicitar no ADR que a entrega é um projeto de integração, não uma implementação funcional.

### Prioridade baixa, mas recomendada

1. Remover artefatos compilados de `tests/__pycache__` e manter apenas testes-fonte reproduzíveis.
2. Fixar versões de dependências em [requirements.txt](requirements.txt) para melhorar reprodutibilidade.
3. Corrigir a validação de logs para aceitar o nome de execução atual e tornar o benchmark reproduzível a partir de um comando único.
4. Incluir no dashboard uma indicação visível do modo de execução (`--sem-llm` ou Bedrock), da cobertura de bloqueios e da qualidade conhecida, evitando que resultados heurísticos sejam confundidos com resultados LLM.

## 7. Parecer final para a banca

O FinGuard está em condição de demonstrar um **MVP sólido de níveis 1 e 2**, com uma base avançada de segurança local, rastreabilidade e análise exploratória de clusters. A alegação de atendimento integral ao **nível 3 não é sustentada** enquanto o Bedrock Guardrails oficial não estiver conectado. O nível 4 deve ser apresentado honestamente como **bônus parcial local**, pois o requisito SageMaker funcional não foi implementado.

Na apresentação, recomenda-se declarar explicitamente: quais resultados foram gerados com Bedrock, quais foram gerados com `--sem-llm`, que a proteção oficial ainda é uma pendência técnica e que o SageMaker foi substituído por uma alternativa local por custo/escopo. Isso preserva a credibilidade da solução e torna claros os próximos passos.
