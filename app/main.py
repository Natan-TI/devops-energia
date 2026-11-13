"""Monta a aplicação: banco, rotas, métricas e cabeçalhos de segurança."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import api, config, db, metricas, paginas

# As telas não usam JavaScript nem recursos de outros sites.
CSP = (
    "default-src 'self'; script-src 'none'; style-src 'self'; img-src 'self' data:; "
    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


def criar_app(cfg: config.Config | None = None) -> FastAPI:
    cfg = cfg or config.carregar()
    engine = db.criar_engine(cfg.database_url)

    @asynccontextmanager
    async def ciclo(_app: FastAPI):
        db.Base.metadata.create_all(engine)
        yield
        engine.dispose()

    app = FastAPI(
        title="Energia que dá Lucro · Painel",
        description="API e painel do comerciante. Os dados exibidos são simulados.",
        version="1.0.0",
        lifespan=ciclo,
    )
    app.state.config = cfg
    app.state.Sessao = db.criar_sessao(engine)

    @app.middleware("http")
    async def cabecalhos_de_seguranca(request, call_next):
        resposta = await call_next(request)
        resposta.headers["X-Content-Type-Options"] = "nosniff"
        resposta.headers["Referrer-Policy"] = "no-referrer"
        resposta.headers["X-Frame-Options"] = "DENY"
        if not request.url.path.startswith(("/docs", "/redoc")):
            resposta.headers["Content-Security-Policy"] = CSP
        return resposta

    app.middleware("http")(metricas.medir)
    app.include_router(api.rotas)
    app.include_router(paginas.rotas)
    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
    return app
