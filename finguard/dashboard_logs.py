"""Agrega os logs estruturados (JSONL) de uma execução e renderiza o dashboard de rastreabilidade."""

import json
from collections import Counter, defaultdict
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

RAIZ = Path(__file__).parent.parent


def _ler_linhas(caminho_jsonl: Path) -> list[dict]:
    linhas = []
    with open(caminho_jsonl, encoding="utf-8") as arquivo:
        for linha in arquivo:
            linha = linha.strip()
            if linha:
                linhas.append(json.loads(linha))
    return linhas


_ACOES_BEDROCK = {
    "chamada_bedrock_triagem": "agente_triagem",
    "chamada_bedrock_risco": "agente_risco",
    "chamada_bedrock_rotulagem_cluster": "rotulagem_cluster",
}


def _agregar_tokens(linhas: list[dict]) -> dict:
    """Agrega consumo de tokens (usage do Converse) por agente e por mensagem a partir dos logs."""
    linhas_tokens = [
        linha
        for linha in linhas
        if linha["acao"] in _ACOES_BEDROCK and linha.get("detalhes", {}).get("tokens_total") is not None
    ]

    por_agente: dict[str, dict] = {}
    modelos_por_agente: dict[str, set] = defaultdict(set)
    por_mensagem: dict[str, dict] = defaultdict(lambda: {"reclamacao_id": None, "chamadas": 0, "tokens_entrada": 0, "tokens_saida": 0, "tokens_total": 0})

    for linha in linhas_tokens:
        agente = _ACOES_BEDROCK[linha["acao"]]
        detalhes = linha["detalhes"]
        entrada = detalhes.get("tokens_entrada") or 0
        saida = detalhes.get("tokens_saida") or 0
        total = detalhes.get("tokens_total") or 0

        agregado_agente = por_agente.setdefault(
            agente, {"agente": agente, "chamadas": 0, "tokens_entrada": 0, "tokens_saida": 0, "tokens_total": 0}
        )
        agregado_agente["chamadas"] += 1
        agregado_agente["tokens_entrada"] += entrada
        agregado_agente["tokens_saida"] += saida
        agregado_agente["tokens_total"] += total
        if detalhes.get("modelo"):
            modelos_por_agente[agente].add(detalhes["modelo"])

        reclamacao_id = linha.get("reclamacao_id")
        if reclamacao_id:
            agregado_mensagem = por_mensagem[reclamacao_id]
            agregado_mensagem["reclamacao_id"] = reclamacao_id
            agregado_mensagem["chamadas"] += 1
            agregado_mensagem["tokens_entrada"] += entrada
            agregado_mensagem["tokens_saida"] += saida
            agregado_mensagem["tokens_total"] += total

    tokens_por_agente = sorted(por_agente.values(), key=lambda item: item["tokens_total"], reverse=True)
    for item in tokens_por_agente:
        item["media_tokens_chamada"] = round(item["tokens_total"] / item["chamadas"], 1) if item["chamadas"] else 0.0
        item["modelos"] = ", ".join(sorted(modelos_por_agente.get(item["agente"], []))) or "—"

    top_mensagens = sorted(por_mensagem.values(), key=lambda item: item["tokens_total"], reverse=True)[:20]

    totais = {
        "tokens_entrada": sum(item["tokens_entrada"] for item in tokens_por_agente),
        "tokens_saida": sum(item["tokens_saida"] for item in tokens_por_agente),
        "tokens_total": sum(item["tokens_total"] for item in tokens_por_agente),
        "chamadas": sum(item["chamadas"] for item in tokens_por_agente),
    }

    return {"totais": totais, "por_agente": tokens_por_agente, "top_mensagens": top_mensagens}


def gerar_dashboard_logs(caminho_jsonl: Path, caminho_saida: str) -> None:
    """Lê um arquivo de log JSONL de uma execução e gera um dashboard HTML de rastreabilidade."""
    linhas = _ler_linhas(caminho_jsonl)

    total = len(linhas)
    por_status = Counter(linha["status"] for linha in linhas)
    total_erros = por_status.get("erro", 0)
    taxa_erro = (total_erros / total * 100) if total else 0.0

    por_acao = Counter(linha["acao"] for linha in linhas)

    # Eventos "resumo" (ex.: duração total da execução) não são ações individuais e não
    # devem entrar nas comparações de latência por ação/top mais lentas.
    linhas_acao = [linha for linha in linhas if linha.get("tipo", "acao") != "resumo"]

    duracoes_por_acao: dict[str, list[float]] = defaultdict(list)
    for linha in linhas_acao:
        if linha.get("duracao_ms") is not None:
            duracoes_por_acao[linha["acao"]].append(linha["duracao_ms"])

    latencia_por_acao = [
        {
            "acao": acao,
            "media_ms": round(sum(duracoes) / len(duracoes), 1),
            "max_ms": round(max(duracoes), 1),
            "qtd": len(duracoes),
        }
        for acao, duracoes in sorted(duracoes_por_acao.items())
    ]
    latencia_por_acao.sort(key=lambda item: item["media_ms"], reverse=True)

    erros = sorted((linha for linha in linhas if linha["status"] == "erro"), key=lambda linha: linha["timestamp"])

    mais_lentas = sorted(
        (linha for linha in linhas_acao if linha.get("duracao_ms") is not None),
        key=lambda linha: linha["duracao_ms"],
        reverse=True,
    )[:20]

    duracao_total_ms = next(
        (linha["duracao_ms"] for linha in linhas if linha["acao"] == "execucao_cli_fim" and linha.get("duracao_ms") is not None),
        None,
    )

    tokens = _agregar_tokens(linhas)

    execucao_id = linhas[0]["execucao_id"] if linhas else None

    ambiente = Environment(loader=FileSystemLoader(str(RAIZ / "templates")))
    template = ambiente.get_template("dashboard_logs.html.j2")
    html = template.render(
        execucao_id=execucao_id,
        arquivo_origem=str(caminho_jsonl),
        total=total,
        total_erros=total_erros,
        taxa_erro=round(taxa_erro, 1),
        duracao_total_ms=duracao_total_ms,
        contagem_acao=por_acao.most_common(),
        latencia_por_acao=latencia_por_acao,
        erros=erros,
        mais_lentas=mais_lentas,
        linhas=linhas,
        tokens_totais=tokens["totais"],
        tokens_por_agente=tokens["por_agente"],
        tokens_top_mensagens=tokens["top_mensagens"],
    )
    Path(caminho_saida).write_text(html, encoding="utf-8")
