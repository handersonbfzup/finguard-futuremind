"""FinGuard — Nível 2: Orquestrador de Análise (grafo LangGraph).

Uso:
    python3 main.py --csv "dataset_finguard_desafio_3 (5).csv" [--limit N] [--sem-llm]

Sem credenciais AWS configuradas, use --sem-llm para rodar o grafo inteiro (guardrail,
triagem heurística, risco heurístico, relatório) sem chamar o Bedrock — útil para validar
o fluxo, o roteamento condicional e o log de execuções antes de gastar chamadas de LLM.
"""

import argparse
import json
import os
import time
from collections import Counter
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader

from finguard.grafo import construir_grafo
from finguard.schemas import ResultadoReclamacao

RAIZ = Path(__file__).parent


def _obter_modelos_em_uso(usar_llm: bool) -> tuple[str, str] | None:
    if not usar_llm:
        return None

    from finguard.bedrock_client import MODELO_RISCO_PADRAO, MODELO_TRIAGEM_PADRAO

    return MODELO_TRIAGEM_PADRAO, MODELO_RISCO_PADRAO


def processar_csv(caminho_csv: str, limite: int | None, usar_llm: bool) -> list[ResultadoReclamacao]:
    df = pd.read_csv(caminho_csv)
    if limite:
        df = df.head(limite)
    total_registros = len(df)
    inicio_processamento = time.time()

    grafo = construir_grafo()
    resultados: list[ResultadoReclamacao] = []

    for indice, (_, linha) in enumerate(df.iterrows(), start=1):
        if total_registros:
            percentual = (indice / total_registros) * 100
            decorrido = time.time() - inicio_processamento
            media_por_item = decorrido / indice
            restante_segundos = int(media_por_item * (total_registros - indice))
            minutos = restante_segundos // 60
            segundos = restante_segundos % 60
            print(
                f"\rProgresso: {indice}/{total_registros} ({percentual:.1f}%) | ETA {minutos:02d}:{segundos:02d}",
                end="",
                flush=True,
            )

        produto_original = linha.get("produto")
        if pd.isna(produto_original):
            produto_original = None

        estado_inicial = {
            "id": linha["id"],
            "canal": linha["canal"],
            "produto_original": produto_original,
            "status": linha["status"],
            "texto_original": linha["texto_reclamacao"],
            "_usar_llm": usar_llm,
            "logs": [],
        }

        try:
            estado_final = grafo.invoke(estado_inicial)
        except Exception as erro:  # noqa: BLE001 - não deixar uma falha pontual derrubar o lote
            resultados.append(
                ResultadoReclamacao(
                    id=linha["id"],
                    canal=linha["canal"],
                    produto_original=produto_original,
                    status=linha["status"],
                    motivo_bloqueio=f"erro_pipeline:{erro}",
                )
            )
            continue

        resultados.append(
            ResultadoReclamacao(
                id=estado_final["id"],
                canal=estado_final["canal"],
                produto_original=estado_final.get("produto_original"),
                status=estado_final["status"],
                bloqueado=estado_final.get("bloqueado", False),
                motivo_bloqueio=estado_final.get("motivo_bloqueio"),
                classificacao=estado_final.get("classificacao"),
                risco_nivel=estado_final.get("risco_nivel"),
                risco_justificativa=estado_final.get("risco_justificativa"),
                acao_recomendada=estado_final.get("acao_recomendada"),
                logs=estado_final.get("logs", []),
            )
        )

    if total_registros:
        print()

    return resultados


def salvar_json(resultados: list[ResultadoReclamacao], caminho_saida: str) -> None:
    dados = [r.model_dump(mode="json") for r in resultados]
    Path(caminho_saida).write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def gerar_dashboard(resultados: list[ResultadoReclamacao], caminho_saida: str) -> None:
    classificados = [r.classificacao for r in resultados if r.classificacao is not None]
    bloqueados = [
        r for r in resultados
        if r.bloqueado and not (r.motivo_bloqueio or "").startswith("erro_pipeline:")
    ]
    falhas_pipeline = [
        r for r in resultados
        if (r.motivo_bloqueio or "").startswith("erro_pipeline:")
    ]
    criticos = [
        r for r in resultados
        if not r.bloqueado and r.risco_nivel in ("Alto", "Crítico")
    ]

    contagem_categoria = Counter(c.categoria.value for c in classificados)
    contagem_produto = Counter(c.produto.value for c in classificados)
    contagem_sentimento = Counter(c.sentimento.value for c in classificados)
    contagem_urgencia = Counter(c.urgencia.value for c in classificados)
    contagem_risco = Counter(r.risco_nivel for r in resultados if r.risco_nivel)

    ambiente = Environment(loader=FileSystemLoader(str(RAIZ / "templates")))
    template = ambiente.get_template("dashboard.html.j2")
    html = template.render(
        total=len(resultados),
        total_classificados=len(classificados),
        total_bloqueados=len(bloqueados),
        total_falhas_pipeline=len(falhas_pipeline),
        contagem_categoria=contagem_categoria.most_common(),
        contagem_produto=contagem_produto.most_common(),
        contagem_sentimento=contagem_sentimento.most_common(),
        contagem_urgencia=contagem_urgencia.most_common(),
        contagem_risco=contagem_risco.most_common(),
        bloqueados=bloqueados,
        falhas_pipeline=falhas_pipeline,
        criticos=criticos,
    )
    Path(caminho_saida).write_text(html, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="FinGuard — Nível 2: Orquestrador de Análise")
    parser.add_argument("--csv", default="dataset_finguard_desafio_3 (5).csv")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sem-llm", action="store_true", help="Roda o grafo com heurísticas, sem chamar o Bedrock")
    parser.add_argument("--aws-profile", default=None, help="Profile AWS a ser usado nas chamadas Bedrock (ex.: bedrock)")
    parser.add_argument("--aws-region", default=None, help="Região AWS para as chamadas Bedrock (ex.: us-east-1)")
    parser.add_argument("--out-json", default="resultado_analise.json")
    parser.add_argument("--out-html", default="dashboard.html")
    args = parser.parse_args()

    if args.aws_profile:
        os.environ["AWS_PROFILE"] = args.aws_profile
        os.environ["AWS_DEFAULT_PROFILE"] = args.aws_profile
    if args.aws_region:
        os.environ["AWS_REGION"] = args.aws_region
        os.environ["AWS_DEFAULT_REGION"] = args.aws_region

    if not args.sem_llm:
        profile_ativo = os.environ.get("AWS_PROFILE") or os.environ.get("AWS_DEFAULT_PROFILE") or "default"
        regiao_ativa = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
        print(f"Executando com AWS profile={profile_ativo} | region={regiao_ativa}")

    inicio = time.time()
    resultados = processar_csv(args.csv, args.limit, usar_llm=not args.sem_llm)
    salvar_json(resultados, args.out_json)
    gerar_dashboard(resultados, args.out_html)

    duracao = time.time() - inicio
    modelos = _obter_modelos_em_uso(usar_llm=not args.sem_llm)
    total_bloqueados = sum(
        1
        for r in resultados
        if r.bloqueado and not (r.motivo_bloqueio or "").startswith("erro_pipeline:")
    )
    total_falhas_pipeline = sum(
        1 for r in resultados if (r.motivo_bloqueio or "").startswith("erro_pipeline:")
    )
    total_criticos = sum(1 for r in resultados if r.risco_nivel in ("Alto", "Crítico"))
    print(f"Processadas {len(resultados)} reclamações em {duracao:.1f}s")
    if modelos is None:
        print("Modelos IA: nenhum (--sem-llm)")
    else:
        modelo_triagem, modelo_risco = modelos
        print(f"Modelos IA: triagem={modelo_triagem} | risco={modelo_risco}")
    print(f"Bloqueadas pelo guardrail de entrada: {total_bloqueados}")
    print(f"Falhas de pipeline: {total_falhas_pipeline}")
    print(f"Risco Alto/Crítico: {total_criticos}")
    print(f"JSON salvo em: {args.out_json}")
    print(f"Dashboard salvo em: {args.out_html}")


if __name__ == "__main__":
    main()
