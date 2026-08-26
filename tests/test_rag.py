from finguard.rag import PoliticaChunk, PoliticaRetriever, extrair_chunks_pdf, formatar_contexto_politica


def _retriever() -> PoliticaRetriever:
    return PoliticaRetriever(
        [
            PoliticaChunk("POL-SAC-001-p01-c00", "POL-SAC-001", 1, "2.1 Baixa", "Prazo de resposta baixa: cinco dias úteis."),
            PoliticaChunk("POL-SAC-001-p03-c00", "POL-SAC-001", 3, "4.3 Banco Central", "Banco Central ou Procon: urgência automaticamente crítica."),
        ]
    )


def test_recupera_regra_com_metadados():
    resultado = _retriever().recuperar("menção ao Banco Central e urgência", top_k=1)

    assert len(resultado) == 1
    assert resultado[0]["chunk_id"] == "POL-SAC-001-p03-c00"
    assert resultado[0]["page"] == 3
    assert resultado[0]["section"] == "4.3 Banco Central"
    assert resultado[0]["score"] > 0


def test_nao_retorna_contexto_sem_relevancia():
    assert _retriever().recuperar("senha do cliente e endereço", limiar=0.2) == []


def test_contexto_e_delimitado_como_dado_documental():
    contexto = formatar_contexto_politica(
        [{"chunk_id": "c1", "page": 2, "section": "4", "text": "texto da politica"}]
    )

    assert contexto.startswith('<fonte chunk_id="c1" pagina="2" secao="4">')
    assert "texto da politica" in contexto
    assert "instrução" not in contexto.lower()


def test_contexto_vazio_e_explicito():
    assert "NENHUM CONTEXTO" in formatar_contexto_politica([])


def test_pdf_real_preserva_paginas_e_secoes():
    chunks = extrair_chunks_pdf()

    assert chunks
    assert {chunk.page for chunk in chunks} == {1, 2, 3}
    assert any("4.3 Banco Central" in chunk.section for chunk in chunks)
