"""Fase 4 (bônus) — clusterização das reclamações por similaridade semântica.

Agrupa as reclamações do dataset usando embeddings + K-Means, escolhe o número de
clusters (k) automaticamente via Silhouette Score, e rotula cada cluster com um resumo
curto do tema comum.

Uso:
  python3 script_cluster.py --sem-llm         # embeddings TF-IDF locais, rotulagem por palavra-chave
  python3 script_cluster.py                   # embeddings reais via Bedrock Titan + rotulagem via LLM (Haiku)
"""

import argparse
import json
import re
from collections import Counter

import pandas as pd

from finguard.bedrock_client import rotular_cluster
from finguard.clustering import avaliar_k, escolher_k_otimo, treinar_kmeans
from finguard.embeddings import STOPWORDS_PT, gerar_embeddings_bedrock, gerar_embeddings_locais
from finguard.logging_config import iniciar_execucao, registrar


def rotular_localmente(textos_amostra: list[str]) -> str:
    """Fallback sem LLM: usa as palavras mais frequentes na amostra como rótulo."""
    contagem = Counter()
    for texto in textos_amostra:
        for palavra in re.findall(r"[a-zA-ZÀ-ÿ]{4,}", texto.lower()):
            if palavra not in STOPWORDS_PT:
                contagem[palavra] += 1
    mais_comuns = [palavra for palavra, _ in contagem.most_common(3)]
    return " / ".join(mais_comuns) if mais_comuns else "Cluster sem padrão claro"


def processar_clusters(caminho_csv: str, usar_llm: bool, k_forcado: int | None):
    df = pd.read_csv(caminho_csv)
    textos = df["texto_reclamacao"].fillna("").tolist()
    ids = df["id"].tolist()

    if usar_llm:
        vetores = gerar_embeddings_bedrock(textos)
    else:
        vetores = gerar_embeddings_locais(textos)

    avaliacao = avaliar_k(vetores)
    k = k_forcado or escolher_k_otimo(avaliacao)
    _, rotulos_indice = treinar_kmeans(vetores, k)

    grupos: dict[int, list[dict]] = {}
    for reclamacao_id, texto, indice_cluster in zip(ids, textos, rotulos_indice):
        grupos.setdefault(int(indice_cluster), []).append({"id": reclamacao_id, "texto": texto})

    clusters = []
    for cluster_id, itens in sorted(grupos.items()):
        amostra = [item["texto"] for item in itens[:8]]
        rotulo = rotular_cluster(amostra) if usar_llm else rotular_localmente(amostra)
        registrar(
            acao="cluster_rotulagem",
            detalhes={"cluster_id": cluster_id, "tamanho": len(itens), "rotulo": rotulo},
        )
        clusters.append(
            {
                "cluster_id": cluster_id,
                "rotulo": rotulo,
                "tamanho": len(itens),
                "ids_exemplo": [item["id"] for item in itens[:5]],
            }
        )

    return {"k_escolhido": k, "avaliacao_k": avaliacao, "clusters": clusters}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default="dataset_finguard_desafio_3 (5).csv")
    parser.add_argument("--sem-llm", action="store_true", help="usa TF-IDF local em vez de chamar o Bedrock")
    parser.add_argument("--k", type=int, default=None, help="força um k específico; por padrão escolhe pelo Silhouette Score")
    parser.add_argument("--out-json", default="resultado_clusters.json")
    args = parser.parse_args()

    iniciar_execucao(prefixo="cluster")
    resultado = processar_clusters(args.csv, usar_llm=not args.sem_llm, k_forcado=args.k)

    with open(args.out_json, "w", encoding="utf-8") as arquivo:
        json.dump(resultado, arquivo, ensure_ascii=False, indent=2)

    print(f"K escolhido: {resultado['k_escolhido']} (Silhouette Score de cada k testado em '{args.out_json}')")
    for cluster in resultado["clusters"]:
        print(f"  Cluster {cluster['cluster_id']}: {cluster['rotulo']} ({cluster['tamanho']} reclamações)")
    print(f"JSON salvo em: {args.out_json}")


if __name__ == "__main__":
    main()
