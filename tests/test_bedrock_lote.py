"""Testes do processamento em lote (batch) do cliente Bedrock (docs/tasks/09-processamento-em-lote-llm.md)."""

import json

import pytest

from finguard import bedrock_client as bc


def _resposta_converse(texto: str, stop_reason: str = "end_turn") -> dict:
    return {
        "output": {"message": {"content": [{"text": texto}]}},
        "stopReason": stop_reason,
        "usage": {"inputTokens": 10, "outputTokens": 20, "totalTokens": 30},
    }


@pytest.fixture(autouse=True)
def _sem_log_real(monkeypatch):
    """Evita que os testes gravem arquivos reais em logs/ (registrar() cria um por padrão)."""
    monkeypatch.setattr(bc, "registrar", lambda **kwargs: None)


def test_extrair_json_lista_ok():
    texto = 'Aqui está: [{"id": "1", "nivel": "Alto"}] fim.'
    assert bc._extrair_json_lista(texto) == [{"id": "1", "nivel": "Alto"}]


def test_extrair_json_lista_sem_array_levanta_erro():
    with pytest.raises(ValueError):
        bc._extrair_json_lista("não tem array nenhum aqui")


def test_processar_em_lotes_com_fallback_happy_path():
    itens = [{"id": str(i), "texto": f"texto {i}"} for i in range(5)]
    tamanhos_chamados = []

    def chamar_lote(lote):
        tamanhos_chamados.append(len(lote))
        return {item["id"]: item["texto"] for item in lote}

    resultados, erros = bc._processar_em_lotes_com_fallback(itens, tamanho_lote=2, chamar_lote=chamar_lote)

    assert erros == {}
    assert resultados == {item["id"]: item["texto"] for item in itens}
    assert tamanhos_chamados == [2, 2, 1]


def test_processar_em_lotes_com_fallback_bisecta_ate_isolar_item_com_falha():
    itens = [{"id": str(i), "texto": f"texto {i}"} for i in range(4)]

    def chamar_lote(lote):
        if any(item["id"] == "2" for item in lote):
            raise ValueError("item 2 quebra o lote")
        return {item["id"]: item["texto"] for item in lote}

    resultados, erros = bc._processar_em_lotes_com_fallback(itens, tamanho_lote=4, chamar_lote=chamar_lote)

    assert set(erros.keys()) == {"2"}
    assert set(resultados.keys()) == {"0", "1", "3"}


def test_processar_em_lotes_com_fallback_lote_vazio():
    assert bc._processar_em_lotes_com_fallback([], tamanho_lote=10, chamar_lote=lambda lote: {}) == ({}, {})


def test_processar_em_lotes_com_fallback_paralelo_entre_lotes():
    itens = [{"id": str(i), "texto": f"texto {i}"} for i in range(6)]

    resultados, erros = bc._processar_em_lotes_com_fallback(
        itens, tamanho_lote=2, chamar_lote=lambda lote: {item["id"]: item["texto"] for item in lote}, max_workers=4
    )

    assert erros == {}
    assert set(resultados.keys()) == {item["id"] for item in itens}


def test_chamar_lote_triagem_ok(monkeypatch):
    lote = [
        {"id": "REC-1", "texto": "reclamação 1"},
        {"id": "REC-2", "texto": "reclamação 2"},
    ]
    resposta_json = json.dumps(
        [
            {
                "id": "REC-1",
                "categoria": "Atendimento",
                "produto": "Conta Corrente",
                "sentimento": "Negativo",
                "urgencia": "Baixa",
                "resumo": "Cliente reclama de atendimento.",
            },
            {
                "id": "REC-2",
                "categoria": "Cobrança Indevida",
                "produto": "Cartão de Crédito",
                "sentimento": "Crítico",
                "urgencia": "Alta",
                "resumo": "Cliente reclama de cobrança indevida.",
            },
        ]
    )
    monkeypatch.setattr(bc, "_obter_cliente", lambda regiao: object())
    monkeypatch.setattr(bc, "_converse_com_retry", lambda cliente, **kwargs: _resposta_converse(resposta_json))

    resultado = bc._chamar_lote_triagem(lote, bc.MODELO_TRIAGEM_PADRAO, bc.REGIAO_PADRAO)

    assert set(resultado.keys()) == {"REC-1", "REC-2"}
    assert resultado["REC-1"].categoria.value == "Atendimento"
    assert resultado["REC-2"].urgencia.value == "Alta"


def test_chamar_lote_triagem_ids_faltantes_levanta_erro(monkeypatch):
    lote = [{"id": "REC-1", "texto": "x"}, {"id": "REC-2", "texto": "y"}]
    resposta_json = json.dumps(
        [
            {
                "id": "REC-1",
                "categoria": "Atendimento",
                "produto": "Conta Corrente",
                "sentimento": "Negativo",
                "urgencia": "Baixa",
                "resumo": "resumo curto",
            }
        ]
    )
    monkeypatch.setattr(bc, "_obter_cliente", lambda regiao: object())
    monkeypatch.setattr(bc, "_converse_com_retry", lambda cliente, **kwargs: _resposta_converse(resposta_json))

    with pytest.raises(ValueError, match="ausentes"):
        bc._chamar_lote_triagem(lote, bc.MODELO_TRIAGEM_PADRAO, bc.REGIAO_PADRAO)


def test_chamar_lote_triagem_truncado_levanta_erro(monkeypatch):
    lote = [{"id": "REC-1", "texto": "x"}]
    monkeypatch.setattr(bc, "_obter_cliente", lambda regiao: object())
    monkeypatch.setattr(
        bc, "_converse_com_retry", lambda cliente, **kwargs: _resposta_converse("[trunc", stop_reason="max_tokens")
    )

    with pytest.raises(ValueError, match="truncada"):
        bc._chamar_lote_triagem(lote, bc.MODELO_TRIAGEM_PADRAO, bc.REGIAO_PADRAO)


def test_chamar_lote_risco_ok(monkeypatch):
    lote = [
        {
            "id": "REC-1",
            "texto": "reclamação 1",
            "classificacao": {"categoria": "Atendimento"},
            "nivel_heuristico": "Baixo",
            "fontes_politica": [],
        }
    ]
    resposta_json = json.dumps([{"id": "REC-1", "nivel": "Médio", "justificativa": "justificativa curta"}])
    monkeypatch.setattr(bc, "_obter_cliente", lambda regiao: object())
    monkeypatch.setattr(bc, "_converse_com_retry", lambda cliente, **kwargs: _resposta_converse(resposta_json))

    resultado = bc._chamar_lote_risco(lote, bc.MODELO_RISCO_PADRAO, bc.REGIAO_PADRAO)

    assert resultado == {"REC-1": ("Médio", "justificativa curta")}


def test_classificar_reclamacoes_lote_fallback_isola_item_invalido(monkeypatch):
    """Um item com categoria inválida não pode derrubar as demais reclamações do lote."""
    itens = [
        {"id": "REC-1", "texto": "ok"},
        {"id": "REC-2", "texto": "ruim"},
    ]

    def falso_converse(cliente, **kwargs):
        mensagem = kwargs["messages"][0]["content"][0]["text"]
        if "REC-2" in mensagem and "REC-1" not in mensagem:
            # Lote isolado do item problemático: categoria inválida.
            return _resposta_converse(
                json.dumps(
                    [
                        {
                            "id": "REC-2",
                            "categoria": "Categoria Inexistente",
                            "produto": "Conta Corrente",
                            "sentimento": "Negativo",
                            "urgencia": "Baixa",
                            "resumo": "x",
                        }
                    ]
                )
            )
        if "REC-1" in mensagem and "REC-2" not in mensagem:
            return _resposta_converse(
                json.dumps(
                    [
                        {
                            "id": "REC-1",
                            "categoria": "Atendimento",
                            "produto": "Conta Corrente",
                            "sentimento": "Negativo",
                            "urgencia": "Baixa",
                            "resumo": "x",
                        }
                    ]
                )
            )
        # Lote com os dois juntos: simula o modelo devolvendo só 1 dos 2 itens.
        return _resposta_converse(
            json.dumps(
                [
                    {
                        "id": "REC-1",
                        "categoria": "Atendimento",
                        "produto": "Conta Corrente",
                        "sentimento": "Negativo",
                        "urgencia": "Baixa",
                        "resumo": "x",
                    }
                ]
            )
        )

    monkeypatch.setattr(bc, "_obter_cliente", lambda regiao: object())
    monkeypatch.setattr(bc, "_converse_com_retry", falso_converse)

    resultados, erros = bc.classificar_reclamacoes_lote(itens, tamanho_lote=2)

    assert set(resultados.keys()) == {"REC-1"}
    assert set(erros.keys()) == {"REC-2"}
