"""Treinamento e avaliação de K-Means para agrupar reclamações por similaridade
semântica (bônus Fase 4).

Usa scikit-learn localmente. O SageMaker (SDK de treino gerenciado) foi avaliado e
descartado nesta entrega por custo/complexidade de infraestrutura desnecessários para
o volume do dataset (500 linhas) — ver adr_finguard.html para a justificativa completa.
"""

from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score


def avaliar_k(vetores, k_min=2, k_max=10):
    """Roda K-Means para cada k no intervalo e devolve inércia (Elbow) e Silhouette Score
    de cada um, para permitir escolher o k mais adequado com base em métrica, não em achismo.
    """
    k_max = min(k_max, len(vetores) - 1)
    resultados = []
    for k in range(k_min, k_max + 1):
        modelo = KMeans(n_clusters=k, random_state=42, n_init=10)
        rotulos = modelo.fit_predict(vetores)
        silhueta = silhouette_score(vetores, rotulos)
        resultados.append({"k": k, "inercia": float(modelo.inertia_), "silhouette": float(silhueta)})
    return resultados


def escolher_k_otimo(resultados):
    """Escolhe o k com maior Silhouette Score (mais próximo de 1 = clusters mais coesos
    e bem separados)."""
    return max(resultados, key=lambda r: r["silhouette"])["k"]


def treinar_kmeans(vetores, k):
    modelo = KMeans(n_clusters=k, random_state=42, n_init=10)
    rotulos = modelo.fit_predict(vetores)
    return modelo, rotulos
