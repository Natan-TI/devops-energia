"""Configuração lida de variáveis de ambiente. Nenhum segredo fica no código."""
import os
from dataclasses import dataclass
from datetime import timedelta, timezone
from pathlib import Path

# Horário de Brasília, usado para agrupar eventos por dia e por mês.
FUSO = timezone(timedelta(hours=-3))
RAIZ = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    database_url: str
    api_key: str
    metrics_token: str = ""
    # Tarifa B3 convencional da Enel SP, sem impostos (ANEEL, REH 3.596/2026): TUSD + TE.
    tarifa_rs_kwh: float = 0.789
    limite_alerta_s: int = 60
    arquivo_recomendacoes: Path = RAIZ / "dados" / "recomendacoes.json"


def carregar() -> Config:
    api_key = os.environ.get("API_KEY", "")
    if len(api_key) < 16:
        raise RuntimeError("Defina a variável API_KEY com pelo menos 16 caracteres.")
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("Defina a variável DATABASE_URL.")
    return Config(
        database_url=database_url,
        api_key=api_key,
        metrics_token=os.environ.get("METRICS_TOKEN", ""),
        tarifa_rs_kwh=float(os.environ.get("TARIFA_RS_KWH", "0.789")),
        limite_alerta_s=int(os.environ.get("LIMITE_ALERTA_S", "60")),
    )
