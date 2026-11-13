"""Telas do painel, montadas no servidor. Não usam JavaScript."""
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates

from . import servico
from .api import sessao
from .config import FUSO
from .db import em_utc

rotas = APIRouter(include_in_schema=False)
modelos = Jinja2Templates(directory=Path(__file__).parent / "templates")


def _numero(valor: float, casas: int) -> str:
    return f"{valor:,.{casas}f}".replace(",", "#").replace(".", ",").replace("#", ".")


def brl(valor: float, casas: int = 2) -> str:
    return "R$ " + _numero(valor, casas)


def duracao(segundos: int) -> str:
    horas, resto = divmod(int(segundos), 3600)
    minutos, seg = divmod(resto, 60)
    if horas:
        return f"{horas} h {minutos:02d} min"
    if minutos:
        return f"{minutos} min {seg:02d} s"
    return f"{seg} s"


def data_hora(momento: datetime) -> str:
    return em_utc(momento).astimezone(FUSO).strftime("%d/%m/%Y %H:%M:%S")


modelos.env.filters.update(brl=brl, numero=_numero, duracao=duracao, data_hora=data_hora)


# Nome exibido de cada tipo de evento e quem o detecta.
NOMES_TIPO = {
    "porta_aberta": ("Porta de refrigeração aberta", "Câmera (visão computacional)"),
    "luz_acesa": ("Luz acesa em ambiente vazio", "Robô com sensor de luminosidade"),
}


def _contexto(request: Request, s, loja_id: str | None, pagina: str) -> dict:
    lojas = servico.listar_lojas(s)
    loja = loja_id if loja_id in lojas else lojas[-1]
    return {"request": request, "lojas": lojas, "loja": loja, "pagina": pagina, "nomes_tipo": NOMES_TIPO}


@rotas.get("/")
def visao_geral(request: Request, loja_id: str | None = None, periodo: str | None = None, s=Depends(sessao)):
    ctx = _contexto(request, s, loja_id, "visao")
    periodo = periodo or servico.periodo_atual()
    try:
        resumo = servico.resumo(s, ctx["loja"], periodo)
    except ValueError:
        periodo = servico.periodo_atual()
        resumo = servico.resumo(s, ctx["loja"], periodo)
    por_dia = {d["dia"]: d for d in resumo["por_dia"]}
    dias = [
        {"rotulo": dia[8:], "titulo": f"{dia[8:]}/{dia[5:7]}", "valor": por_dia.get(dia, {}).get("total_rs", 0.0)}
        for dia in servico.dias_do_periodo(periodo)
    ]
    # Projeção: média diária do mês (até hoje, se for o mês atual) multiplicada por 365.
    hoje = datetime.now(FUSO).date().isoformat()
    dias_decorridos = sum(1 for dia in servico.dias_do_periodo(periodo) if dia <= hoje) or 1
    cfg = request.app.state.config
    ctx.update(
        dias_decorridos=dias_decorridos,
        projecao_anual=resumo["total_rs"] / dias_decorridos * 365,
        periodo=periodo,
        resumo=resumo,
        dias=dias,
        maximo_dia=max((d["valor"] for d in dias), default=0.0),
        maximo_equipamento=max((e["total_rs"] for e in resumo["por_equipamento"]), default=0.0),
        ultimos=servico.listar_eventos(s, loja_id=ctx["loja"], limite=6),
        sugestao=next(iter(servico.recomendacoes(cfg, ctx["loja"])), None),
        limite_alerta_s=cfg.limite_alerta_s,
    )
    return modelos.TemplateResponse(request, "visao_geral.html", ctx)


@rotas.get("/eventos")
def eventos(
    request: Request,
    loja_id: str | None = None,
    equipamento_id: str | None = None,
    desde: str | None = None,
    ate: str | None = None,
    s=Depends(sessao),
):
    ctx = _contexto(request, s, loja_id, "eventos")
    erro = None
    try:
        inicio = servico.dia_local(desde)
        fim = servico.dia_local(ate)
        fim = fim + timedelta(days=1) if fim else None  # o dia "até" entra na lista
    except ValueError as excecao:
        inicio = fim = None
        erro = str(excecao)
    lista = servico.listar_eventos(s, ctx["loja"], equipamento_id or None, inicio, fim, limite=200)
    filtros = {"loja_id": ctx["loja"]}
    if equipamento_id:
        filtros["equipamento_id"] = equipamento_id
    if inicio:
        filtros["desde"] = desde
    if fim:
        filtros["ate"] = fim.date().isoformat()
    ctx.update(
        eventos=lista,
        equipamentos=servico.listar_equipamentos(s, ctx["loja"]),
        equipamento=equipamento_id or "",
        desde=desde or "",
        ate=ate or "",
        erro=erro,
        link_csv="/events.csv?" + urlencode(filtros),
        limite_alerta_s=request.app.state.config.limite_alerta_s,
    )
    return modelos.TemplateResponse(request, "eventos.html", ctx)


@rotas.get("/alertas")
def alertas(request: Request, loja_id: str | None = None, s=Depends(sessao)):
    ctx = _contexto(request, s, loja_id, "alertas")
    ctx["alertas"] = servico.listar_alertas(s, ctx["loja"], limite=200)
    return modelos.TemplateResponse(request, "alertas.html", ctx)


@rotas.get("/sugestoes")
def sugestoes(request: Request, loja_id: str | None = None, s=Depends(sessao)):
    ctx = _contexto(request, s, loja_id, "sugestoes")
    ctx["sugestoes"] = servico.recomendacoes(request.app.state.config, ctx["loja"])
    return modelos.TemplateResponse(request, "sugestoes.html", ctx)
