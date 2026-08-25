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


def gerar_dashboard_logs(caminho_jsonl: Path, caminho_saida: str) -> None:
    """Lê um arquivo de log JSONL de uma execução e gera um dashboard HTML de rastreabilidade."""
    linhas = _ler_linhas(caminho_jsonl)

    total = len(linhas)
    por_status = Counter(linha["status"] for linha in linhas)
    total_erros = por_status.get("erro", 0)
    taxa_erro = (total_erros / total * 100) if total else 0.0

    por_acao = Counter(linha["acao"] for linha in linhas)

    duracoes_por_acao: dict[str, list[float]] = defaultdict(list)
    for linha in linhas:
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
        (linha for linha in linhas if linha.get("duracao_ms") is not None),
        key=lambda linha: linha["duracao_ms"],
        reverse=True,
    )[:20]

    execucao_id = linhas[0]["execucao_id"] if linhas else None

    ambiente = Environment(loader=FileSystemLoader(str(RAIZ / "templates")))
    template = ambiente.get_template("dashboard_logs.html.j2")
    html = template.render(
        execucao_id=execucao_id,
        arquivo_origem=str(caminho_jsonl),
        total=total,
        total_erros=total_erros,
        taxa_erro=round(taxa_erro, 1),
        contagem_acao=por_acao.most_common(),
        latencia_por_acao=latencia_por_acao,
        erros=erros,
        mais_lentas=mais_lentas,
        linhas=linhas,
    )
    Path(caminho_saida).write_text(html, encoding="utf-8")
