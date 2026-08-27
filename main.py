"""FinGuard — Nível 2: Orquestrador de Análise (grafo LangGraph).

Uso:
    python3 main.py --csv "dataset_finguard_desafio_3 (5).csv" [--limit N] [--sem-llm]
    python3 main.py --csv "dataset_finguard_desafio_3 (5).csv" --batch-size 15

Sem credenciais AWS configuradas, use --sem-llm para rodar o grafo inteiro (guardrail,
triagem heurística, risco heurístico, relatório) sem chamar o Bedrock — útil para validar
o fluxo, o roteamento condicional e o log de execuções antes de gastar chamadas de LLM.

--batch-size agrupa N reclamações por chamada ao Bedrock (triagem e risco) em vez de 1 por
chamada, reduzindo custo/latência (ver docs/tasks/09-processamento-em-lote-llm.md).
"""

import argparse
import json
import math
import os
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pandas as pd
from jinja2 import Environment, FileSystemLoader

from finguard.agentes import calcular_risco_heuristico
from finguard.bedrock_client import analisar_riscos_lote, classificar_reclamacoes_lote
from finguard.dashboard_logs import gerar_dashboard_logs
from finguard.grafo import construir_grafo
from finguard.guardrails import verificar_guardrail_entrada
from finguard.logging_config import caminho_arquivo_atual, iniciar_execucao, registrar
from finguard.rag import recuperar_contexto_politica
from finguard.schemas import ResultadoReclamacao

RAIZ = Path(__file__).parent


def _obter_modelos_em_uso(usar_llm: bool) -> tuple[str, str] | None:
    if not usar_llm:
        return None

    from finguard.bedrock_client import MODELO_RISCO_PADRAO, MODELO_TRIAGEM_PADRAO

    return MODELO_TRIAGEM_PADRAO, MODELO_RISCO_PADRAO


def _processar_linha(
    grafo, linha, usar_llm: bool, precomputado: dict[str, Any] | None = None
) -> ResultadoReclamacao:
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
    if precomputado:
        # Modo lote (processar_csv_em_lote): classificação/risco já obtidos em chamadas em
        # lote ao Bedrock; os nós do grafo leem esses valores em vez de chamar o Bedrock de novo.
        estado_inicial.update(precomputado)

    try:
        estado_final = grafo.invoke(estado_inicial)
    except Exception as erro:  # noqa: BLE001 - não deixar uma falha pontual derrubar o lote
        registrar(
            acao="erro_pipeline",
            status="erro",
            reclamacao_id=linha["id"],
            detalhes={"erro": str(erro)},
            nivel="ERROR",
        )
        return ResultadoReclamacao(
            id=linha["id"],
            canal=linha["canal"],
            produto_original=produto_original,
            status=linha["status"],
            motivo_bloqueio=f"erro_pipeline:{erro}",
        )

    return ResultadoReclamacao(
        id=estado_final["id"],
        canal=estado_final["canal"],
        produto_original=estado_final.get("produto_original"),
        status=estado_final["status"],
        bloqueado=estado_final.get("bloqueado", False),
        motivo_bloqueio=estado_final.get("motivo_bloqueio"),
        classificacao=estado_final.get("classificacao"),
        risco_nivel=estado_final.get("risco_nivel"),
        risco_justificativa=estado_final.get("risco_justificativa"),
        fontes_politica=estado_final.get("fontes_politica", []),
        politica_contexto_disponivel=estado_final.get("politica_contexto_disponivel", False),
        acao_recomendada=estado_final.get("acao_recomendada"),
        logs=estado_final.get("logs", []),
    )


def processar_csv(
    caminho_csv: str, limite: int | None, usar_llm: bool, workers: int = 8
) -> list[ResultadoReclamacao]:
    df = pd.read_csv(caminho_csv)
    if limite:
        df = df.head(limite)
    total_registros = len(df)
    inicio_processamento = time.time()

    grafo = construir_grafo()
    # Cada registro é independente (I/O de rede ao Bedrock); processar em paralelo evita
    # serializar centenas de round-trips de rede em um único thread.
    max_workers = workers if usar_llm else 1
    resultados: list[ResultadoReclamacao | None] = [None] * total_registros
    concluidos = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futuros = {
            executor.submit(_processar_linha, grafo, linha, usar_llm): indice
            for indice, (_, linha) in enumerate(df.iterrows())
        }
        for futuro in as_completed(futuros):
            indice = futuros[futuro]
            resultados[indice] = futuro.result()
            concluidos += 1

            if total_registros:
                percentual = (concluidos / total_registros) * 100
                decorrido = time.time() - inicio_processamento
                media_por_item = decorrido / concluidos
                restante_segundos = int(media_por_item * (total_registros - concluidos))
                minutos = restante_segundos // 60
                segundos = restante_segundos % 60
                print(
                    f"\rProgresso: {concluidos}/{total_registros} ({percentual:.1f}%) | ETA {minutos:02d}:{segundos:02d}",
                    end="",
                    flush=True,
                )

    if total_registros:
        print()

    return resultados


def _criar_callback_progresso_lote(rotulo: str, total_itens: int, tamanho_lote: int):
    """Imprime progresso a cada lote concluído (fases sem feedback ficariam mudas até o
    fim, dando a impressão de travamento em datasets grandes)."""
    total_lotes = math.ceil(total_itens / tamanho_lote) if tamanho_lote > 0 else (1 if total_itens else 0)
    if total_lotes == 0:
        return None

    concluidos = 0
    lock = threading.Lock()

    def callback() -> None:
        nonlocal concluidos
        with lock:
            concluidos += 1
            print(f"\r{rotulo}: lote {concluidos}/{total_lotes} concluído", end="", flush=True)
            if concluidos == total_lotes:
                print()

    return callback


def processar_csv_em_lote(
    caminho_csv: str, limite: int | None, tamanho_lote: int, workers: int = 8
) -> list[ResultadoReclamacao]:
    """Como `processar_csv`, mas agrupa reclamações em lotes de `tamanho_lote` por chamada
    ao Bedrock (triagem e risco) em vez de 1 chamada por reclamação — ver
    docs/tasks/09-processamento-em-lote-llm.md. Reclamações cuja classificação/risco não
    forem obtidos em lote (falha após bissecção) caem automaticamente no fallback
    individual (mesmo caminho de `processar_csv`), sem perder o restante do dataset.
    """
    df = pd.read_csv(caminho_csv)
    if limite:
        df = df.head(limite)
    total_registros = len(df)
    inicio_processamento = time.time()

    grafo = construir_grafo()
    linhas = [linha for _, linha in df.iterrows()]

    # Fase 1: guardrail de entrada é local/heurístico (sem LLM) — decide, antes de montar
    # os lotes, quem nem deveria entrar no lote de triagem.
    indices_bloqueados: list[int] = []
    indices_pendentes: list[int] = []
    for indice, linha in enumerate(linhas):
        if verificar_guardrail_entrada(str(linha["texto_reclamacao"])).bloqueado:
            indices_bloqueados.append(indice)
        else:
            indices_pendentes.append(indice)

    # Fase 2: triagem em lote.
    itens_triagem = [
        {"id": str(linhas[indice]["id"]), "texto": str(linhas[indice]["texto_reclamacao"])}
        for indice in indices_pendentes
    ]
    print(f"Fase 1/4: {len(indices_bloqueados)} reclamação(ões) bloqueada(s) pelo guardrail de entrada.")
    classificacoes_por_id, erros_triagem_por_id = classificar_reclamacoes_lote(
        itens_triagem,
        tamanho_lote=tamanho_lote,
        max_workers=workers,
        ao_concluir_lote=_criar_callback_progresso_lote("Fase 2/4 (triagem em lote)", len(itens_triagem), tamanho_lote),
    )

    # Fase 3: contexto de política (local, TF-IDF) + risco em lote, só para quem já tem classificação.
    classificacoes_por_indice: dict[int, dict] = {}
    fontes_por_indice: dict[int, list[dict]] = {}
    itens_risco = []
    for indice in indices_pendentes:
        linha = linhas[indice]
        id_reclamacao = str(linha["id"])
        classificacao = classificacoes_por_id.get(id_reclamacao)
        if classificacao is None:
            continue
        classificacao_dict = classificacao.model_dump(mode="json")
        classificacoes_por_indice[indice] = classificacao_dict
        texto = str(linha["texto_reclamacao"])
        nivel_heuristico, _ = calcular_risco_heuristico(texto, linha["canal"])
        fontes = recuperar_contexto_politica(texto, classificacao_dict, linha["canal"])
        fontes_por_indice[indice] = fontes
        itens_risco.append(
            {
                "id": id_reclamacao,
                "texto": texto,
                "classificacao": classificacao_dict,
                "nivel_heuristico": nivel_heuristico,
                "fontes_politica": fontes,
            }
        )

    riscos_por_id, erros_risco_por_id = analisar_riscos_lote(
        itens_risco,
        tamanho_lote=tamanho_lote,
        max_workers=workers,
        ao_concluir_lote=_criar_callback_progresso_lote("Fase 3/4 (risco em lote)", len(itens_risco), tamanho_lote),
    )

    total_fallback = len(erros_triagem_por_id) + len(erros_risco_por_id)
    if total_fallback:
        print(
            f"Aviso: {len(erros_triagem_por_id)} reclamação(ões) com fallback individual na "
            f"triagem e {len(erros_risco_por_id)} no risco (lote falhou mesmo após bissecção)."
        )

    # Fase 4: monta a tarefa de cada linha — o que já foi pré-computado em lote é anexado ao
    # estado inicial; o que faltar é resolvido normalmente pelo grafo (individual, com LLM).
    tarefas: list[tuple[int, Any, dict[str, Any]]] = [
        (indice, linhas[indice], {}) for indice in indices_bloqueados
    ]
    for indice in indices_pendentes:
        linha = linhas[indice]
        precomputado: dict[str, Any] = {}
        classificacao_dict = classificacoes_por_indice.get(indice)
        if classificacao_dict is not None:
            precomputado["_classificacao_precomputada"] = classificacao_dict
            precomputado["_fontes_politica_precomputadas"] = fontes_por_indice.get(indice)
            risco = riscos_por_id.get(str(linha["id"]))
            if risco is not None:
                precomputado["_risco_nivel_precomputado"] = risco[0]
                precomputado["_risco_justificativa_precomputada"] = risco[1]
        tarefas.append((indice, linha, precomputado))

    # Fase 5: executa o grafo por linha. Quem teve tudo pré-computado não chama o Bedrock
    # aqui; só o fallback (triagem e/ou risco ausentes) gera chamadas individuais reais.
    print(f"Fase 4/4: executando o grafo para {total_registros} reclamação(ões)...")
    resultados: list[ResultadoReclamacao | None] = [None] * total_registros
    concluidos = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futuros = {
            executor.submit(_processar_linha, grafo, linha, True, precomputado): indice
            for indice, linha, precomputado in tarefas
        }
        for futuro in as_completed(futuros):
            indice = futuros[futuro]
            resultados[indice] = futuro.result()
            concluidos += 1

            if total_registros:
                percentual = (concluidos / total_registros) * 100
                decorrido = time.time() - inicio_processamento
                media_por_item = decorrido / concluidos
                restante_segundos = int(media_por_item * (total_registros - concluidos))
                minutos = restante_segundos // 60
                segundos = restante_segundos % 60
                print(
                    f"\rProgresso: {concluidos}/{total_registros} ({percentual:.1f}%) | ETA {minutos:02d}:{segundos:02d}",
                    end="",
                    flush=True,
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
    parser.add_argument(
        "--workers",
        type=int,
        default=16,
        help="Nº de reclamações processadas em paralelo quando usando LLM (chamadas Bedrock são I/O-bound)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help=(
            "Agrupa N reclamações por chamada ao Bedrock (triagem e risco) em vez de 1 por "
            "chamada; reduz custo/latência diluindo o prompt de sistema fixo. Sem esse "
            "parâmetro, mantém o modo atual (1 chamada por reclamação). Ignorado com "
            "--sem-llm. Ver docs/tasks/09-processamento-em-lote-llm.md para o tamanho recomendado."
        ),
    )
    parser.add_argument("--aws-profile", default=None, help="Profile AWS a ser usado nas chamadas Bedrock (ex.: bedrock)")
    parser.add_argument("--aws-region", default=None, help="Região AWS para as chamadas Bedrock (ex.: us-east-1)")
    parser.add_argument("--out-json", default="resultado_analise.json")
    parser.add_argument("--out-html", default="dashboard.html")
    parser.add_argument("--out-html-logs", default="dashboard_logs.html", help="Dashboard de rastreabilidade das ações/logs desta execução")
    args = parser.parse_args()

    iniciar_execucao(prefixo="execucao")

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
    registrar(
        acao="execucao_cli_inicio",
        tipo="resumo",
        detalhes={
            "csv": args.csv,
            "limite": args.limit,
            "usar_llm": not args.sem_llm,
            "workers": args.workers,
            "batch_size": args.batch_size,
        },
    )
    if args.batch_size and args.sem_llm:
        print("Aviso: --batch-size ignorado em modo --sem-llm (não há chamadas ao Bedrock para agrupar).")
    if args.batch_size and not args.sem_llm:
        resultados = processar_csv_em_lote(
            args.csv, args.limit, tamanho_lote=args.batch_size, workers=args.workers
        )
    else:
        resultados = processar_csv(args.csv, args.limit, usar_llm=not args.sem_llm, workers=args.workers)
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
    registrar(
        acao="execucao_cli_fim",
        tipo="resumo",
        duracao_ms=round(duracao * 1000, 1),
        detalhes={
            "total": len(resultados),
            "bloqueados": total_bloqueados,
            "falhas_pipeline": total_falhas_pipeline,
            "criticos": total_criticos,
        },
    )
    arquivo_logs = caminho_arquivo_atual()
    if arquivo_logs is not None:
        gerar_dashboard_logs(arquivo_logs, args.out_html_logs)

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
    if arquivo_logs is not None:
        print(f"Dashboard de logs salvo em: {args.out_html_logs} (fonte: {arquivo_logs})")


if __name__ == "__main__":
    main()
