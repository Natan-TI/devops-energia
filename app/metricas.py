"""Métricas para o Prometheus: tráfego, latência, erros e saturação."""
import time

from prometheus_client import Counter, Gauge, Histogram

REQUISICOES = Counter(
    "http_requisicoes_total", "Requisições recebidas.", ["metodo", "rota", "status"]
)
DURACAO = Histogram(
    "http_duracao_segundos",
    "Tempo de resposta das requisições.",
    ["metodo", "rota"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
EM_ANDAMENTO = Gauge("http_requisicoes_em_andamento", "Requisições sendo atendidas agora.")
EVENTOS_RECEBIDOS = Counter("eventos_recebidos_total", "Eventos gravados.", ["origem", "tipo"])
ALERTAS_RECEBIDOS = Counter("alertas_recebidos_total", "Alertas gravados.", ["canal"])


async def medir(request, call_next):
    """Mede cada requisição. A rota usada é o modelo ('/events'), nunca o endereço bruto."""
    if request.url.path == "/metrics":
        return await call_next(request)
    inicio = time.perf_counter()
    status = 500
    EM_ANDAMENTO.inc()
    try:
        resposta = await call_next(request)
        status = resposta.status_code
        return resposta
    finally:
        EM_ANDAMENTO.dec()
        rota = getattr(request.scope.get("route"), "path", "nao_encontrada")
        REQUISICOES.labels(request.method, rota, str(status)).inc()
        DURACAO.labels(request.method, rota).observe(time.perf_counter() - inicio)
