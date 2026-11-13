"""Tabelas do banco de dados."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class Evento(Base):
    __tablename__ = "eventos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    loja_id: Mapped[str] = mapped_column(String(64), index=True)
    equipamento_id: Mapped[str] = mapped_column(String(64))
    tipo: Mapped[str] = mapped_column(String(32))
    origem: Mapped[str] = mapped_column(String(32))
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duracao_s: Mapped[int] = mapped_column(Integer)
    custo_estimado_rs: Mapped[float] = mapped_column(Float)
    energia_kwh: Mapped[float] = mapped_column(Float)
    recebido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Alerta(Base):
    __tablename__ = "alertas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    loja_id: Mapped[str] = mapped_column(String(64), index=True)
    equipamento_id: Mapped[str] = mapped_column(String(64))
    evento_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    canal: Mapped[str] = mapped_column(String(16))
    mensagem: Mapped[str] = mapped_column(String(500))
    enviado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


def criar_engine(url: str):
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)


def criar_sessao(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


def em_utc(momento: datetime) -> datetime:
    """O SQLite devolve datas sem fuso; todas são gravadas em UTC."""
    return momento.replace(tzinfo=timezone.utc) if momento.tzinfo is None else momento.astimezone(timezone.utc)
