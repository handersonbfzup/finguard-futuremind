source venv/bin/activate

python3 main.py --sem-llm, que processa tudo sem chamar o Bedrock — não gasta nada e não precisa de credenciais)

python3 main.py --csv "dados/dataset_finguard_desafio_3 (5).csv" --aws-profile bedrock --aws-region us-east-1 --limit 100

# Processamento em lote (--batch-size): agrupa N reclamações por chamada ao Bedrock (triagem
# e risco) em vez de 1 por chamada, reduzindo custo/latência — ver docs/tasks/09-processamento-em-lote-llm.md
python3 main.py --csv "dados/dataset_finguard_desafio_3 (5).csv" --aws-profile bedrock --aws-region us-east-1 --batch-size 15

# Lote + limite de registros (teste rápido, ex.: 50 registros em lotes de 15)
python3 main.py --csv "dados/dataset_finguard_desafio_3 (5).csv" --aws-profile bedrock --aws-region us-east-1 --batch-size 15 --limit 50

# Lote + workers (paraleliza as chamadas de lote entre si; default de --workers é 16)
python3 main.py --csv "dados/dataset_finguard_desafio_3 (5).csv" --aws-profile bedrock --aws-region us-east-1 --batch-size 15 --workers 8

# --batch-size é ignorado (com aviso) se combinado com --sem-llm, pois não há chamada ao Bedrock para agrupar
python3 main.py --sem-llm --batch-size 15


aws sso login --profile bedrock

# 1. Sonnet 5 (candidato a substituir o Sonnet no agente de risco)
aws bedrock-runtime converse \
  --model-id global.anthropic.claude-sonnet-5 \
  --messages '[{"role":"user","content":[{"text":"diga oi"}]}]' \
  --region us-east-1 --profile bedrock

# 2. Sonnet 4.5 direto (sem inference profile), caso a SCP só bloqueie o Haiku 4.5
aws bedrock-runtime converse \
  --model-id anthropic.claude-sonnet-4-5-20250929-v1:0 \
  --messages '[{"role":"user","content":[{"text":"diga oi"}]}]' \
  --region us-east-1 --profile bedrock

# 3. Amazon Nova Lite (modelo próprio da AWS, alternativa barata caso a SCP restrinja só modelos Anthropic novos)
aws bedrock-runtime converse \
  --model-id amazon.nova-lite-v1:0 \
  --messages '[{"role":"user","content":[{"text":"diga oi"}]}]' \
  --region us-east-1 --profile bedrock


Comando 1 — IDs dos foundation models Claude
  aws bedrock list-foundation-models --region us-east-1 --profile bedrock \
  --query "modelSummaries[?contains(modelId,'claude')].{id:modelId,onDemand:inferenceTypesSupported}" \
  --output table

Comando 2 — IDs de inference profile (provavelmente o que falta)

  aws bedrock list-inference-profiles --region us-east-1 --profile bedrock \
  --query "inferenceProfileSummaries[?contains(inferenceProfileId,'claude')].{id:inferenceProfileId,name:inferenceProfileName}" \
  --output table