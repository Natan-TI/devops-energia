"""Rotas de dados (JSON e CSV), no contrato combinado pelo grupo."""
import csv
import hmac
import io
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from . import metricas, servico
from .schemas import AlertaEntrada, EventoEntrada, Identificador

rotas = APIRouter()


def sessao(request: Request):
    with request.app.state.Sessao() as s:
        yield s


def exigir_chave(request: Request, x_api_key: str | None = Header(default=None)):
    esperada = request.app.state.config.api_key
    if not x_api_key or not hmac.compare_digest(x_api_key.encode(), esperada.encode()):
        raise HTTPException(status_code=401, detail="Chave de API ausente ou inválida.")


def _dia(valor: str | None) -> datetime | None:
    try:
        return servico.dia_local(valor)
    except ValueError as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro


@rotas.get("/health", tags=["operação"])
def health(response: Response, s=Depends(sessao)):
    try:
        s.execute(text("SELECT 1"))
    except Exception:
        response.status_code = 503
        return {"status": "banco indisponível"}
    return {"status": "ok"}


@rotas.get("/metrics", tags=["operação"], include_in_schema=False)
def metrics(request: Request, authorization: str | None = Header(default=None)):
    token = request.app.state.config.metrics_token
    if token and not hmac.compare_digest((authorization or "").encode(), f"Bearer {token}".encode()):
        raise HTTPException(status_code=401, detail="Token de métricas ausente ou inválido.")
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@rotas.post("/events", status_code=201, tags=["eventos"], dependencies=[Depends(exigir_chave)])
def criar_evento(dados: EventoEntrada, request: Request, response: Response, s=Depends(sessao)):
    evento, criado = servico.registrar_evento(s, request.app.state.config, dados)
    if criado:
        metricas.EVENTOS_RECEBIDOS.labels(evento.origem, evento.tipo).inc()
    else:
        response.status_code = 200
    return servico.evento_para_dict(evento)


@rotas.get("/events", tags=["eventos"])
def listar_eventos(
    loja_id: Identificador | None = None,
    equipamento_id: Identificador | None = None,
    desde: str | None = Query(default=None, description="AAAA-MM-DD"),
    ate: str | None = Query(default=None, description="AAAA-MM-DD, não incluído"),
    limite: int = Query(default=200, ge=1, le=1000),
    s=Depends(sessao),
):
    eventos = servico.listar_eventos(s, loja_id, equipamento_id, _dia(desde), _dia(ate), limite)
    return [servico.evento_para_dict(e) for e in eventos]


def _celula(valor) -> str:
    """Evita que uma planilha interprete o texto como fórmula."""
    texto = str(valor)
    return "'" + texto if texto[:1] in ("=", "+", "-", "@") else texto


@rotas.get("/events.csv", tags=["eventos"])
def exportar_eventos(
    loja_id: Identificador | None = None,
    equipamento_id: Identificador | None = None,
    desde: str | None = None,
    ate: str | None = None,
    s=Depends(sessao),
):
    eventos = servico.listar_eventos(s, loja_id, equipamento_id, _dia(desde), _dia(ate), limite=10_000)
    colunas = ["inicio", "loja_id", "equipamento_id", "tipo", "origem", "duracao_s", "custo_estimado_rs",
               "energia_kwh", "id"]
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";", lineterminator="\n")
    escritor.writerow(colunas)
    for evento in eventos:
        linha = servico.evento_para_dict(evento)
        escritor.writerow([_celula(linha[c]) for c in colunas])
    return Response(
        "﻿" + saida.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="eventos.csv"'},
    )


@rotas.post("/alerts", status_code=201, tags=["alertas"], dependencies=[Depends(exigir_chave)])
def criar_alerta(dados: AlertaEntrada, s=Depends(sessao)):
    alerta = servico.registrar_alerta(s, dados)
    metricas.ALERTAS_RECEBIDOS.labels(alerta.canal).inc()
    return servico.alerta_para_dict(alerta)


@rotas.get("/alerts", tags=["alertas"])
def listar_alertas(
    loja_id: Identificador | None = None,
    limite: int = Query(default=200, ge=1, le=1000),
    s=Depends(sessao),
):
    return [servico.alerta_para_dict(a) for a in servico.listar_alertas(s, loja_id, limite)]


@rotas.get("/summary", tags=["resumo"])
def resumo(loja_id: Identificador, periodo: str | None = None, s=Depends(sessao)):
    try:
        return servico.resumo(s, loja_id, periodo or servico.periodo_atual())
    except ValueError as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro


@rotas.get("/recommendations", tags=["recomendações"])
def recomendacoes(request: Request, loja_id: Identificador | None = None):
    return servico.recomendacoes(request.app.state.config, loja_id)
