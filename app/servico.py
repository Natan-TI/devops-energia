"""Regras do painel: registrar, listar e resumir eventos e alertas."""
import json
import re
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import FUSO, Config
from .db import Alerta, Evento, em_utc
from .schemas import AlertaEntrada, EventoEntrada

LOJAS_PADRAO = ["padaria-01", "mercado-01"]


def agora() -> datetime:
    return datetime.now(timezone.utc)


def registrar_evento(sessao: Session, cfg: Config, dados: EventoEntrada) -> tuple[Evento, bool]:
    """Grava o evento. Reenviar o mesmo id não duplica: devolve o que já existe."""
    existente = sessao.get(Evento, str(dados.id))
    if existente:
        return existente, False
    evento = Evento(
        id=str(dados.id),
        loja_id=dados.loja_id,
        equipamento_id=dados.equipamento_id,
        tipo=dados.tipo,
        origem=dados.origem,
        inicio=dados.inicio.astimezone(timezone.utc),
        duracao_s=dados.duracao_s,
        custo_estimado_rs=dados.custo_estimado_rs,
        energia_kwh=round(dados.custo_estimado_rs / cfg.tarifa_rs_kwh, 6),  # energia = custo ÷ tarifa
        recebido_em=agora(),
    )
    sessao.add(evento)
    sessao.commit()
    return evento, True


def registrar_alerta(sessao: Session, dados: AlertaEntrada) -> Alerta:
    alerta = Alerta(
        id=str(dados.id or uuid.uuid4()),
        loja_id=dados.loja_id,
        equipamento_id=dados.equipamento_id,
        evento_id=str(dados.evento_id) if dados.evento_id else None,
        canal=dados.canal,
        mensagem=dados.mensagem,
        enviado_em=(dados.enviado_em or agora()).astimezone(timezone.utc),
    )
    alerta = sessao.merge(alerta)
    sessao.commit()
    return alerta


def listar_eventos(sessao: Session, loja_id=None, equipamento_id=None, desde=None, ate=None, limite=200):
    consulta = select(Evento).order_by(Evento.inicio.desc()).limit(limite)
    if loja_id:
        consulta = consulta.where(Evento.loja_id == loja_id)
    if equipamento_id:
        consulta = consulta.where(Evento.equipamento_id == equipamento_id)
    if desde:
        consulta = consulta.where(Evento.inicio >= desde.astimezone(timezone.utc))
    if ate:
        consulta = consulta.where(Evento.inicio < ate.astimezone(timezone.utc))
    return list(sessao.scalars(consulta))


def listar_alertas(sessao: Session, loja_id=None, limite=200):
    consulta = select(Alerta).order_by(Alerta.enviado_em.desc()).limit(limite)
    if loja_id:
        consulta = consulta.where(Alerta.loja_id == loja_id)
    return list(sessao.scalars(consulta))


def listar_lojas(sessao: Session) -> list[str]:
    encontradas = set(sessao.scalars(select(Evento.loja_id).distinct()))
    return sorted(encontradas | set(LOJAS_PADRAO))


def listar_equipamentos(sessao: Session, loja_id: str) -> list[str]:
    return sorted(sessao.scalars(select(Evento.equipamento_id).where(Evento.loja_id == loja_id).distinct()))


def periodo_atual() -> str:
    return datetime.now(FUSO).strftime("%Y-%m")


def limites_do_periodo(periodo: str) -> tuple[datetime, datetime]:
    """Recebe 'AAAA-MM' e devolve o primeiro instante do mês e o do mês seguinte."""
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", periodo):
        raise ValueError("Use o período no formato AAAA-MM.")
    ano, mes = int(periodo[:4]), int(periodo[5:])
    inicio = datetime(ano, mes, 1, tzinfo=FUSO)
    fim = datetime(ano + (mes == 12), mes % 12 + 1, 1, tzinfo=FUSO)
    return inicio, fim


def dia_local(valor: str | None) -> datetime | None:
    """Converte 'AAAA-MM-DD' para a meia-noite desse dia no horário de Brasília."""
    if not valor:
        return None
    try:
        dia = date.fromisoformat(valor)
    except ValueError as erro:
        raise ValueError("Use a data no formato AAAA-MM-DD.") from erro
    return datetime(dia.year, dia.month, dia.day, tzinfo=FUSO)


def resumo(sessao: Session, loja_id: str, periodo: str) -> dict:
    inicio, fim = limites_do_periodo(periodo)
    eventos = listar_eventos(sessao, loja_id=loja_id, desde=inicio, ate=fim, limite=100_000)
    por_equipamento = defaultdict(lambda: {"eventos": 0, "total_rs": 0.0, "total_kwh": 0.0, "tempo_aberto_s": 0})
    por_tipo = defaultdict(lambda: {"eventos": 0, "total_rs": 0.0, "total_kwh": 0.0, "tempo_s": 0})
    por_dia = defaultdict(lambda: {"eventos": 0, "total_rs": 0.0, "total_kwh": 0.0})
    for evento in eventos:
        dia = em_utc(evento.inicio).astimezone(FUSO).date().isoformat()
        for grupo in (por_equipamento[evento.equipamento_id], por_tipo[evento.tipo], por_dia[dia]):
            grupo["eventos"] += 1
            grupo["total_rs"] += evento.custo_estimado_rs
            grupo["total_kwh"] += evento.energia_kwh
        por_equipamento[evento.equipamento_id]["tempo_aberto_s"] += evento.duracao_s
        por_tipo[evento.tipo]["tempo_s"] += evento.duracao_s

    def arredondar(grupo: dict) -> dict:
        return {**grupo, "total_rs": round(grupo["total_rs"], 4), "total_kwh": round(grupo["total_kwh"], 4)}

    return {
        "loja_id": loja_id,
        "periodo": periodo,
        "eventos": len(eventos),
        "total_rs": round(sum(e.custo_estimado_rs for e in eventos), 4),
        "total_kwh": round(sum(e.energia_kwh for e in eventos), 4),
        "tempo_aberto_s": sum(e.duracao_s for e in eventos),
        "por_equipamento": sorted(
            ({"equipamento_id": nome, **arredondar(g)} for nome, g in por_equipamento.items()),
            key=lambda g: g["total_rs"],
            reverse=True,
        ),
        "por_tipo": sorted(
            ({"tipo": nome, **arredondar(g)} for nome, g in por_tipo.items()),
            key=lambda g: g["total_rs"],
            reverse=True,
        ),
        "por_dia": [{"dia": dia, **arredondar(g)} for dia, g in sorted(por_dia.items())],
    }


def dias_do_periodo(periodo: str) -> list[str]:
    """Todos os dias do mês, para o gráfico não pular dias sem evento."""
    inicio, fim = limites_do_periodo(periodo)
    dias, dia = [], inicio
    while dia < fim:
        dias.append(dia.date().isoformat())
        dia += timedelta(days=1)
    return dias


def recomendacoes(cfg: Config, loja_id: str | None = None) -> list[dict]:
    try:
        itens = json.loads(cfg.arquivo_recomendacoes.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [item for item in itens if not loja_id or item.get("loja_id") == loja_id]


def evento_para_dict(evento: Evento) -> dict:
    return {
        "id": evento.id,
        "loja_id": evento.loja_id,
        "equipamento_id": evento.equipamento_id,
        "tipo": evento.tipo,
        "origem": evento.origem,
        "inicio": em_utc(evento.inicio).astimezone(FUSO).isoformat(timespec="seconds"),
        "duracao_s": evento.duracao_s,
        "custo_estimado_rs": round(evento.custo_estimado_rs, 4),
        "energia_kwh": round(evento.energia_kwh, 4),
    }


def alerta_para_dict(alerta: Alerta) -> dict:
    return {
        "id": alerta.id,
        "loja_id": alerta.loja_id,
        "equipamento_id": alerta.equipamento_id,
        "evento_id": alerta.evento_id,
        "canal": alerta.canal,
        "mensagem": alerta.mensagem,
        "enviado_em": em_utc(alerta.enviado_em).astimezone(FUSO).isoformat(timespec="seconds"),
    }
