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
    "chamada_bedrock_triagem_lote": "agente_triagem",
    "chamada_bedrock_risco": "agente_risco",
    "chamada_bedrock_risco_lote": "agente_risco",
    "chamada_bedrock_rotulagem_cluster": "rotulagem_cluster",
}

# Preços por 1 milhão de tokens (BRL), Amazon Bedrock Standard us-east-1.
# Atualizar esta tabela quando os preços oficiais mudarem ou novos modelos entrarem em uso
# (fonte: https://aws.amazon.com/bedrock/pricing/). Chave = substring do modelId (case-insensitive).
_TABELA_PRECOS_BRL: list[tuple[str, str, float, float]] = [
    ("amazon.nova-lite-v1", "Amazon Nova Lite v1", 0.34, 1.37),
    ("claude-3-5-haiku", "Claude 3.5 Haiku", 4.56, 22.80),
    ("claude-haiku-4-5", "Claude Haiku 4.5", 4.56, 22.80),
    ("claude-sonnet-4-5", "Claude Sonnet 4.5", 17.10, 85.50),
]


def _buscar_preco(modelo_id: str | None) -> tuple[str, float, float] | None:
    """Retorna (nome_exibicao, preco_entrada_1m, preco_saida_1m) em BRL, ou None se o modelo não está cadastrado."""
    if not modelo_id:
        return None
    modelo_lower = modelo_id.lower()
    for chave, nome, preco_entrada, preco_saida in _TABELA_PRECOS_BRL:
        if chave in modelo_lower:
            return nome, preco_entrada, preco_saida
    return None


def _custo_brl(modelo_id: str | None, tokens_entrada: int, tokens_saida: int) -> float | None:
    """Calcula o custo estimado (BRL) de uma chamada, ou None se o modelo não tem preço cadastrado."""
    preco = _buscar_preco(modelo_id)
    if preco is None:
        return None
    _, preco_entrada, preco_saida = preco
    return (tokens_entrada / 1_000_000) * preco_entrada + (tokens_saida / 1_000_000) * preco_saida


def _formatar_custo_brl(valor: float) -> str:
    """Formata custo em BRL; usa mais casas decimais para valores pequenos (execuções de teste com poucas chamadas geram frações de centavo que sumiriam com 2 casas fixas)."""
    if valor != 0 and abs(valor) < 0.01:
        return f"R$ {valor:.4f}"
    return f"R$ {valor:.2f}"


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
        modelo = detalhes.get("modelo")

        agregado_agente = por_agente.setdefault(
            agente,
            {
                "agente": agente,
                "chamadas": 0,
                "tokens_entrada": 0,
                "tokens_saida": 0,
                "tokens_total": 0,
                "custo_brl": 0.0,
                "preco_indisponivel": False,
            },
        )
        agregado_agente["chamadas"] += 1
        agregado_agente["tokens_entrada"] += entrada
        agregado_agente["tokens_saida"] += saida
        agregado_agente["tokens_total"] += total
        if modelo:
            modelos_por_agente[agente].add(modelo)

        custo_linha = _custo_brl(modelo, entrada, saida)
        if custo_linha is None:
            agregado_agente["preco_indisponivel"] = True
        else:
            agregado_agente["custo_brl"] += custo_linha

        reclamacao_id = linha.get("reclamacao_id")
        # Em chamadas de lote não há um `reclamacao_id` único; os tokens/custo da chamada
        # são rateados igualmente entre os ids do lote (`detalhes.reclamacoes_ids`) para
        # preservar a rastreabilidade por reclamação mesmo no modo lote.
        ids_para_ratear = detalhes.get("reclamacoes_ids") or ([reclamacao_id] if reclamacao_id else [])
        n_ids = len(ids_para_ratear)
        if n_ids:
            for id_rateado in ids_para_ratear:
                agregado_mensagem = por_mensagem[id_rateado]
                agregado_mensagem["reclamacao_id"] = id_rateado
                agregado_mensagem["chamadas"] += 1
                agregado_mensagem["tokens_entrada"] += entrada / n_ids
                agregado_mensagem["tokens_saida"] += saida / n_ids
                agregado_mensagem["tokens_total"] += total / n_ids

    tokens_por_agente = sorted(por_agente.values(), key=lambda item: item["tokens_total"], reverse=True)
    for item in tokens_por_agente:
        item["media_tokens_chamada"] = round(item["tokens_total"] / item["chamadas"], 1) if item["chamadas"] else 0.0
        item["modelos"] = ", ".join(sorted(modelos_por_agente.get(item["agente"], []))) or "—"
        # Se algum modelo usado pelo agente não tem preço cadastrado, o custo do agente fica
        # indisponível (evita exibir um total parcial que pareça completo). Mantém o valor bruto
        # (sem arredondar ainda) para a soma do total não acumular erro de arredondamento.
        item["custo_brl"] = None if item["preco_indisponivel"] else item["custo_brl"]
        item["custo_brl_fmt"] = _formatar_custo_brl(item["custo_brl"]) if item["custo_brl"] is not None else None

    top_mensagens = sorted(por_mensagem.values(), key=lambda item: item["tokens_total"], reverse=True)[:20]
    for item in top_mensagens:
        # Tokens rateados de chamadas em lote ficam fracionados; arredondar só para exibição.
        item["tokens_entrada"] = round(item["tokens_entrada"], 1)
        item["tokens_saida"] = round(item["tokens_saida"], 1)
        item["tokens_total"] = round(item["tokens_total"], 1)

    custo_total_brl = sum(item["custo_brl"] for item in tokens_por_agente if item["custo_brl"] is not None)
    custo_disponivel = any(item["custo_brl"] is not None for item in tokens_por_agente)

    totais = {
        "tokens_entrada": sum(item["tokens_entrada"] for item in tokens_por_agente),
        "tokens_saida": sum(item["tokens_saida"] for item in tokens_por_agente),
        "tokens_total": sum(item["tokens_total"] for item in tokens_por_agente),
        "chamadas": sum(item["chamadas"] for item in tokens_por_agente),
        "custo_brl_fmt": _formatar_custo_brl(custo_total_brl) if custo_disponivel else None,
        "custo_disponivel": custo_disponivel,
        "custo_parcial": any(item["custo_brl"] is None for item in tokens_por_agente),
    }

    return {"totais": totais, "por_agente": tokens_por_agente, "top_mensagens": top_mensagens}


def _diagnosticar_tokens_indisponiveis(linhas: list[dict], total_chamadas_tokens: int) -> str | None:
    """Explica por que o dashboard pode não exibir métricas de tokens."""
    if total_chamadas_tokens > 0:
        return None

    inicio_execucao = next((linha for linha in linhas if linha.get("acao") == "execucao_cli_inicio"), None)
    usar_llm = bool(inicio_execucao and inicio_execucao.get("detalhes", {}).get("usar_llm"))
    if not usar_llm:
        return "Execução sem LLM (--sem-llm): não há chamadas Bedrock para contabilizar tokens."

    erros_pipeline = [
        linha
        for linha in linhas
        if linha.get("acao") == "erro_pipeline" and linha.get("status") == "erro"
    ]

    erro_sso = next(
        (
            linha.get("detalhes", {}).get("erro", "")
            for linha in erros_pipeline
            if "token from sso" in str(linha.get("detalhes", {}).get("erro", "")).lower()
        ),
        None,
    )
    if erro_sso:
        return "Nenhuma chamada Bedrock registrada: credencial AWS SSO expirada ou inválida (faça aws sso login e execute novamente)."

    if erros_pipeline:
        return "Nenhuma chamada Bedrock registrada: houve falhas de pipeline antes das etapas de triagem/risco."

    return "Nenhuma chamada Bedrock registrada nesta execução; sem dados de tokens para exibir."


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
    diagnostico_tokens = _diagnosticar_tokens_indisponiveis(linhas, tokens["totais"]["chamadas"])

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
        diagnostico_tokens=diagnostico_tokens,
    )
    Path(caminho_saida).write_text(html, encoding="utf-8")
