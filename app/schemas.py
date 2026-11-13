"""Formato dos dados que entram na API (contrato combinado pelo grupo)."""
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field, StringConstraints

Identificador = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")]


class EventoEntrada(BaseModel):
    id: UUID
    loja_id: Identificador
    equipamento_id: Identificador
    tipo: Literal["porta_aberta", "luz_acesa"]
    origem: Literal["acv", "robo", "simulador"]
    inicio: AwareDatetime
    duracao_s: int = Field(ge=0, le=86_400)
    custo_estimado_rs: float = Field(ge=0, le=10_000)


class AlertaEntrada(BaseModel):
    id: UUID | None = None
    loja_id: Identificador
    equipamento_id: Identificador
    evento_id: UUID | None = None
    canal: Literal["whatsapp", "telegram", "email", "painel"]
    mensagem: str = Field(min_length=1, max_length=500)
    enviado_em: AwareDatetime | None = None
