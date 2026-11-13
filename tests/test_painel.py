"""Testa a API e as telas com um banco SQLite temporário. Não precisa de Docker."""
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import FUSO, Config
from app.main import criar_app
from app.servico import limites_do_periodo

CHAVE = "chave-de-teste-0123456789"
AUTENTICADO = {"X-API-Key": CHAVE}
AGORA = datetime.now(FUSO).replace(microsecond=0)
PERIODO = AGORA.strftime("%Y-%m")


@pytest.fixture
def cliente(tmp_path):
    cfg = Config(database_url=f"sqlite:///{tmp_path / 'teste.db'}", api_key=CHAVE)
    with TestClient(criar_app(cfg)) as c:
        yield c


def evento(**mudancas) -> dict:
    base = {
        "id": str(uuid.uuid4()),
        "loja_id": "padaria-01",
        "equipamento_id": "expositor-1",
        "tipo": "porta_aberta",
        "origem": "acv",
        "inicio": AGORA.isoformat(),
        "duracao_s": 95,
        "custo_estimado_rs": 0.0036,
    }
    return {**base, **mudancas}


def test_health_responde_ok(cliente):
    assert cliente.get("/health").json() == {"status": "ok"}


def test_gravar_evento_exige_a_chave(cliente):
    assert cliente.post("/events", json=evento()).status_code == 401
    assert cliente.post("/events", json=evento(), headers={"X-API-Key": "errada"}).status_code == 401
    assert cliente.get("/events").json() == []


def test_evento_e_gravado_e_reenvio_nao_duplica(cliente):
    dados = evento()
    primeira = cliente.post("/events", json=dados, headers=AUTENTICADO)
    assert primeira.status_code == 201
    assert primeira.json()["energia_kwh"] == pytest.approx(0.0036 / 0.789, abs=1e-4)
    assert cliente.post("/events", json=dados, headers=AUTENTICADO).status_code == 200
    lista = cliente.get("/events", params={"loja_id": "padaria-01"}).json()
    assert len(lista) == 1
    assert lista[0]["inicio"] == AGORA.isoformat()


@pytest.mark.parametrize("mudanca", [
    {"duracao_s": -1},
    {"custo_estimado_rs": -0.5},
    {"inicio": "2026-11-12T14:03:10"},  # sem fuso horário
    {"loja_id": "Padaria 01; DROP TABLE"},
    {"tipo": "outro"},
    {"id": "nao-e-uuid"},
])
def test_evento_fora_do_contrato_e_recusado(cliente, mudanca):
    assert cliente.post("/events", json=evento(**mudanca), headers=AUTENTICADO).status_code == 422


def test_resumo_soma_por_equipamento_e_por_dia(cliente):
    for dados in (
        evento(duracao_s=120, custo_estimado_rs=0.0045),
        evento(duracao_s=60, custo_estimado_rs=0.0023),
        evento(equipamento_id="freezer-1", duracao_s=30, custo_estimado_rs=0.0011),
        evento(loja_id="mercado-01", custo_estimado_rs=9.0),  # outra loja: não entra
    ):
        assert cliente.post("/events", json=dados, headers=AUTENTICADO).status_code == 201

    resumo = cliente.get("/summary", params={"loja_id": "padaria-01", "periodo": PERIODO}).json()
    assert resumo["eventos"] == 3
    assert resumo["total_rs"] == pytest.approx(0.0079)
    assert resumo["tempo_aberto_s"] == 210
    assert [e["equipamento_id"] for e in resumo["por_equipamento"]] == ["expositor-1", "freezer-1"]
    assert resumo["por_equipamento"][0]["eventos"] == 2
    assert [(t["tipo"], t["eventos"], t["tempo_s"]) for t in resumo["por_tipo"]] == [("porta_aberta", 3, 210)]
    assert resumo["por_dia"] == [{"dia": AGORA.date().isoformat(), "eventos": 3, "total_rs": 0.0079,
                                  "total_kwh": pytest.approx(0.0079 / 0.789, abs=1e-4)}]
    assert cliente.get("/summary", params={"loja_id": "padaria-01", "periodo": "2026-13"}).status_code == 422


def test_filtro_por_data_e_exportacao_csv(cliente):
    antigo = evento(inicio=(AGORA - timedelta(days=10)).isoformat(), equipamento_id="freezer-1")
    for dados in (evento(), antigo):
        cliente.post("/events", json=dados, headers=AUTENTICADO)
    ontem = (AGORA - timedelta(days=1)).date().isoformat()
    assert len(cliente.get("/events", params={"desde": ontem}).json()) == 1
    assert cliente.get("/events", params={"ate": ontem}).json()[0]["id"] == antigo["id"]
    assert cliente.get("/events", params={"desde": "ontem"}).status_code == 422

    csv = cliente.get("/events.csv", params={"loja_id": "padaria-01"})
    assert csv.headers["content-type"].startswith("text/csv")
    linhas = csv.text.lstrip("﻿").strip().split("\n")
    assert linhas[0].startswith("inicio;loja_id;equipamento_id")
    assert len(linhas) == 3


def test_alertas_sao_gravados_e_listados(cliente):
    alerta = {"loja_id": "padaria-01", "equipamento_id": "expositor-1", "canal": "whatsapp",
              "mensagem": "expositor-1 aberto há mais de 60 segundos."}
    assert cliente.post("/alerts", json=alerta).status_code == 401
    assert cliente.post("/alerts", json=alerta, headers=AUTENTICADO).status_code == 201
    assert cliente.get("/alerts", params={"loja_id": "padaria-01"}).json()[0]["canal"] == "whatsapp"
    assert cliente.get("/alerts", params={"loja_id": "mercado-01"}).json() == []


def test_recomendacoes_sao_filtradas_por_loja(cliente):
    itens = cliente.get("/recommendations", params={"loja_id": "padaria-01"}).json()
    assert itens and all(item["loja_id"] == "padaria-01" for item in itens)


def test_telas_abrem_e_escapam_o_conteudo(cliente):
    cliente.post("/events", json=evento(duracao_s=200), headers=AUTENTICADO)
    cliente.post("/alerts", headers=AUTENTICADO, json={
        "loja_id": "padaria-01", "equipamento_id": "expositor-1", "canal": "painel",
        "mensagem": "<script>alert(1)</script>"})
    for caminho in ("/", "/eventos", "/alertas", "/sugestoes", "/eventos?desde=errado", "/?periodo=errado"):
        resposta = cliente.get(caminho, params={"loja_id": "padaria-01"})
        assert resposta.status_code == 200, caminho
        assert "script-src 'none'" in resposta.headers["content-security-policy"]
        assert "<script>" not in resposta.text
    assert "&lt;script&gt;" in cliente.get("/alertas", params={"loja_id": "padaria-01"}).text
    assert "expositor-1" in cliente.get("/", params={"loja_id": "padaria-01"}).text


def test_metricas_contam_as_requisicoes_pela_rota(cliente):
    cliente.post("/events", json=evento(), headers=AUTENTICADO)
    cliente.get("/nao-existe")
    texto = cliente.get("/metrics").text
    assert 'http_requisicoes_total{metodo="POST",rota="/events",status="201"}' in texto
    assert 'rota="nao_encontrada",status="404"' in texto
    assert "http_duracao_segundos_bucket" in texto
    assert 'eventos_recebidos_total{origem="acv",tipo="porta_aberta"}' in texto


def test_metricas_podem_exigir_token(tmp_path):
    cfg = Config(database_url=f"sqlite:///{tmp_path / 't.db'}", api_key=CHAVE, metrics_token="segredo-das-metricas")
    with TestClient(criar_app(cfg)) as c:
        assert c.get("/metrics").status_code == 401
        assert c.get("/metrics", headers={"Authorization": "Bearer segredo-das-metricas"}).status_code == 200


def test_limites_do_periodo_viram_o_ano():
    inicio, fim = limites_do_periodo("2026-12")
    assert (inicio.isoformat(), fim.isoformat()) == ("2026-12-01T00:00:00-03:00", "2027-01-01T00:00:00-03:00")
