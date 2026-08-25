"""Geração de embeddings de texto para o bônus de clusterização (Fase 4).

Modo real: usa o modelo de embeddings da Bedrock (Amazon Titan Embed Text v2) via
`invoke_model`. Modo local (sem credenciais AWS): usa TF-IDF do scikit-learn como
substituto determinístico e sem custo, só para permitir testar o pipeline de
clusterização (Elbow/Silhouette, K-Means, rotulagem) sem depender de rede/AWS.
"""

import json

import numpy as np

MODELO_EMBEDDING_PADRAO = "amazon.titan-embed-text-v2:0"
REGIAO_PADRAO = "us-east-1"

# Lista curta de stopwords em português, usada tanto no TF-IDF local quanto na
# rotulagem de clusters por palavra-chave (modo --sem-llm do script_cluster.py).
STOPWORDS_PT = [
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "é", "em", "um", "uma",
    "uns", "umas", "para", "por", "com", "sem", "que", "não", "sim", "no", "na", "nos",
    "nas", "ao", "aos", "à", "às", "me", "meu", "minha", "meus", "minhas", "eu", "você",
    "vocês", "ele", "ela", "eles", "elas", "isso", "essa", "esse", "esses", "essas",
    "está", "estou", "foi", "ser", "ter", "tem", "tenho", "mais", "muito", "também",
    "já", "só", "mas", "ou", "se", "quando", "como", "porque", "pois", "até", "desde",
    "sobre", "entre", "após", "antes", "isto", "aquele", "aquela", "este", "esta",
]


def gerar_embeddings_bedrock(textos, modelo_id=MODELO_EMBEDDING_PADRAO, regiao=REGIAO_PADRAO, max_workers=8):
    """Gera embeddings reais via Bedrock (Titan). Requer credenciais AWS configuradas."""
    import boto3
    from concurrent.futures import ThreadPoolExecutor, as_completed

    cliente = boto3.client("bedrock-runtime", region_name=regiao)

    def _gerar_um(texto: str) -> list[float]:
        corpo = json.dumps({"inputText": texto[:8000]})
        resposta = cliente.invoke_model(modelId=modelo_id, body=corpo)
        payload = json.loads(resposta["body"].read())
        return payload["embedding"]

    # Chamadas independentes de rede: paralelizar evita serializar centenas de round-trips.
    vetores: list[list[float] | None] = [None] * len(textos)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futuros = {executor.submit(_gerar_um, texto): indice for indice, texto in enumerate(textos)}
        for futuro in as_completed(futuros):
            vetores[futuros[futuro]] = futuro.result()

    return np.array(vetores)


def gerar_embeddings_locais(textos):
    """Fallback offline: TF-IDF como aproximação barata de embedding semântico."""
    from sklearn.feature_extraction.text import TfidfVectorizer

    vetorizador = TfidfVectorizer(max_features=300, stop_words=STOPWORDS_PT)
    matriz = vetorizador.fit_transform(textos)
    return matriz.toarray()
