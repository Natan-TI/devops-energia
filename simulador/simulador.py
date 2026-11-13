"""Envia eventos fictícios para a API do painel, no formato combinado pelo grupo.

Simula as duas fontes de eventos do produto:
- a câmera (visão computacional), que detecta portas de geladeiras e freezers abertas;
- o robô com sensor de luminosidade, que detecta luz acesa em ambiente vazio.

Na primeira execução, preenche os últimos dias com histórico. Depois, envia eventos novos aos poucos
e consulta o resumo a cada intervalo, o que gera tráfego para as métricas.
Usa só a biblioteca padrão do Python.

Parâmetros do custo (veja a seção "De onde vêm os números" do README):
  custo = potência (kW) × fator de perda × horas × tarifa (R$/kWh)
"""
import http.client
import json
import logging
import os
import random
import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

FUSO = timezone(timedelta(hours=-3))
API_URL = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")
DESTINO = urlsplit(API_URL)
if DESTINO.scheme not in ("http", "https") or not DESTINO.netloc:
    raise SystemExit("API_URL precisa ser um endereço http:// ou https://")
CONEXAO = http.client.HTTPSConnection if DESTINO.scheme == "https" else http.client.HTTPConnection
API_KEY = os.environ.get("API_KEY", "")
INTERVALO_S = float(os.environ.get("INTERVALO_S", "5"))
EVENTOS_POR_MINUTO = float(os.environ.get("EVENTOS_POR_MINUTO", "0.5"))
DIAS_HISTORICO = int(os.environ.get("DIAS_HISTORICO", "30"))
LIMITE_ALERTA_S = int(os.environ.get("LIMITE_ALERTA_S", "60"))

# Tarifa B3 convencional da Enel SP, sem impostos: TUSD 472,42 + TE 316,96 R$/MWh (ANEEL, REH 3.596/2026).
TARIFA_RS_KWH = float(os.environ.get("TARIFA_RS_KWH", "0.789"))
# Premissa do grupo: com a porta aberta, o compressor trabalha sem parar. Fora disso ele fica ligado
# cerca de 30% do tempo, então a energia a mais é de cerca de 70% da potência nominal.
FATOR_PERDA_PORTA = float(os.environ.get("FATOR_PERDA_PORTA", "0.70"))

# Potência nominal de catálogo, em kW.
EXPOSITOR_1_PORTA = 0.36   # expositor vertical de 403 L
EXPOSITOR_GRANDE = 0.91    # expositor vertical de 569 L
FREEZER_HORIZONTAL = 0.14  # freezer horizontal de 417 L, 2 tampas
LAMPADA_LED = 0.018        # premissa: lâmpada tubular LED de 18 W

# Para cada loja: portas (potência em kW e peso; quanto maior o peso, mais aberturas),
# luzes (potência total das lâmpadas do ambiente, em kW) e aberturas de porta por dia.
LOJAS = {
    "padaria-01": {
        "aberturas_por_dia": 120,
        "portas": {
            "expositor-bebidas": (EXPOSITOR_GRANDE, 6),
            "expositor-frios": (EXPOSITOR_1_PORTA, 5),
            "expositor-laticinios": (EXPOSITOR_1_PORTA, 4),
            "expositor-sobremesas": (EXPOSITOR_1_PORTA, 2),
            "freezer-sorvetes": (FREEZER_HORIZONTAL, 2),
            "freezer-congelados": (FREEZER_HORIZONTAL, 1),
        },
        "luzes": {"luz-estoque": 6 * LAMPADA_LED, "luz-salao": 20 * LAMPADA_LED},
    },
    "mercado-01": {
        "aberturas_por_dia": 250,
        "portas": {
            "expositor-bebidas-1": (EXPOSITOR_GRANDE, 6),
            "expositor-bebidas-2": (EXPOSITOR_GRANDE, 5),
            "expositor-laticinios": (EXPOSITOR_GRANDE, 5),
            "expositor-frios": (EXPOSITOR_GRANDE, 4),
            "expositor-carnes": (EXPOSITOR_1_PORTA, 3),
            "expositor-hortifruti": (EXPOSITOR_1_PORTA, 2),
            "freezer-congelados-1": (FREEZER_HORIZONTAL, 3),
            "freezer-congelados-2": (FREEZER_HORIZONTAL, 2),
            "freezer-sorvetes": (FREEZER_HORIZONTAL, 2),
            "freezer-carnes": (FREEZER_HORIZONTAL, 1),
        },
        "luzes": {"luz-estoque": 10 * LAMPADA_LED, "luz-salao": 40 * LAMPADA_LED},
    },
}
CANAIS = ["whatsapp", "telegram", "painel"]

log = logging.getLogger("simulador")
sorteio = random.Random()  # dados fictícios: não precisa de gerador criptográfico


def chamar(metodo: str, caminho: str, corpo: dict | None = None):
    """Chama a API. Só aceita endereços http e https (http.client não abre arquivos locais)."""
    cabecalhos = {"Content-Type": "application/json"}
    if metodo != "GET":
        cabecalhos["X-API-Key"] = API_KEY
    conexao = CONEXAO(DESTINO.netloc, timeout=10)
    try:
        conexao.request(metodo, DESTINO.path.rstrip("/") + caminho,
                        body=json.dumps(corpo) if corpo is not None else None, headers=cabecalhos)
        resposta = conexao.getresponse()
        texto = resposta.read()
        if resposta.status >= 400:
            raise OSError(f"{metodo} {caminho} respondeu {resposta.status}")
        return json.loads(texto or b"null")
    finally:
        conexao.close()


def custo(potencia_kw: float, fator: float, duracao_s: int) -> float:
    return round(potencia_kw * fator * (duracao_s / 3600) * TARIFA_RS_KWH, 4)


def montar(loja: str, equipamento: str, tipo: str, origem: str, inicio: datetime, duracao_s: int, valor: float) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "loja_id": loja,
        "equipamento_id": equipamento,
        "tipo": tipo,
        "origem": origem,
        "inicio": inicio.astimezone(FUSO).isoformat(timespec="seconds"),
        "duracao_s": duracao_s,
        "custo_estimado_rs": valor,
    }


def duracao_de_porta() -> int:
    """A maioria das aberturas é rápida; algumas passam do limite; poucas são portas esquecidas."""
    tipo = sorteio.random()
    if tipo < 0.90:
        return sorteio.randint(5, 40)
    if tipo < 0.99:
        return sorteio.randint(61, 240)
    return sorteio.randint(600, 1800)


def porta_aberta(loja: str, inicio: datetime, duracao_s: int | None = None) -> dict:
    """Evento da câmera: porta de geladeira ou freezer aberta."""
    portas = LOJAS[loja]["portas"]
    equipamento = sorteio.choices(list(portas), weights=[peso for _, peso in portas.values()])[0]
    duracao_s = duracao_s if duracao_s is not None else duracao_de_porta()
    valor = custo(portas[equipamento][0], FATOR_PERDA_PORTA, duracao_s)
    return montar(loja, equipamento, "porta_aberta", "simulador", inicio, duracao_s, valor)


def luz_acesa(loja: str, ambiente: str, inicio: datetime, duracao_s: int) -> dict:
    """Evento do robô: luz acesa em ambiente vazio. Toda a energia é desperdício (fator 1)."""
    valor = custo(LOJAS[loja]["luzes"][ambiente], 1.0, duracao_s)
    return montar(loja, ambiente, "luz_acesa", "robo", inicio, duracao_s, valor)


def enviar(evento: dict) -> None:
    chamar("POST", "/events", evento)
    if evento["duracao_s"] <= LIMITE_ALERTA_S:
        return
    minutos, segundos = divmod(evento["duracao_s"], 60)
    valor = f"{evento['custo_estimado_rs']:.2f}".replace(".", ",")
    if evento["tipo"] == "luz_acesa":
        mensagem = f"{evento['equipamento_id']} ficou acesa por {minutos} min sem ninguém no local."
    else:
        mensagem = f"{evento['equipamento_id']} ficou aberto por {minutos} min {segundos:02d} s."
    chamar("POST", "/alerts", {
        "loja_id": evento["loja_id"],
        "equipamento_id": evento["equipamento_id"],
        "evento_id": evento["id"],
        "canal": sorteio.choice(CANAIS),
        "mensagem": f"{mensagem} Desperdício estimado: R$ {valor}.",
        "enviado_em": (datetime.fromisoformat(evento["inicio"]) + timedelta(seconds=LIMITE_ALERTA_S)).isoformat(),
    })


def eventos_do_dia(loja: str, dia: datetime) -> list[dict]:
    """Um dia de funcionamento da loja, das 7h às 21h."""
    eventos = []
    quantidade = round(LOJAS[loja]["aberturas_por_dia"] * sorteio.uniform(0.85, 1.15))
    for _ in range(quantidade):
        eventos.append(porta_aberta(loja, dia + timedelta(seconds=sorteio.randint(7 * 3600, 21 * 3600))))
    # Luz do estoque esquecida acesa algumas vezes por dia, de 15 a 90 minutos.
    for _ in range(sorteio.randint(2, 4)):
        inicio = dia + timedelta(seconds=sorteio.randint(7 * 3600, 20 * 3600))
        eventos.append(luz_acesa(loja, "luz-estoque", inicio, sorteio.randint(15 * 60, 90 * 60)))
    # Em cerca de um dia a cada dez, a luz do salão fica acesa a noite toda depois de fechar.
    if sorteio.random() < 0.10:
        inicio = dia + timedelta(hours=21, minutes=sorteio.randint(10, 50))
        eventos.append(luz_acesa(loja, "luz-salao", inicio, sorteio.randint(8 * 3600, 10 * 3600)))
    return eventos


def esperar_api() -> None:
    while True:
        try:
            chamar("GET", "/health")
            return
        except (http.client.HTTPException, OSError):
            log.info("Aguardando a API em %s", API_URL)
            time.sleep(2)


def preencher_historico() -> None:
    if chamar("GET", "/events?limite=1"):
        log.info("O painel já tem eventos: histórico não será gerado de novo.")
        return
    agora = datetime.now(FUSO)
    total = 0
    for dias_atras in range(DIAS_HISTORICO, -1, -1):
        dia = (agora - timedelta(days=dias_atras)).replace(hour=0, minute=0, second=0, microsecond=0)
        for loja in LOJAS:
            for evento in eventos_do_dia(loja, dia):
                fim = datetime.fromisoformat(evento["inicio"]) + timedelta(seconds=evento["duracao_s"])
                if fim < agora:  # só eventos que já terminaram
                    enviar(evento)
                    total += 1
        log.info("Histórico: faltam %d dias (%d eventos enviados).", dias_atras, total)
    log.info("Histórico gerado: %d eventos em %d dias.", total, DIAS_HISTORICO)


def evento_ao_vivo() -> dict:
    loja = sorteio.choice(list(LOJAS))
    agora = datetime.now(FUSO)
    if sorteio.random() < 0.03:
        duracao_s = sorteio.randint(15 * 60, 90 * 60)
        return luz_acesa(loja, "luz-estoque", agora - timedelta(seconds=duracao_s), duracao_s)
    duracao_s = duracao_de_porta()
    return porta_aberta(loja, agora - timedelta(seconds=duracao_s), duracao_s)


def principal() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if len(API_KEY) < 16:
        raise SystemExit("Defina a variável API_KEY (a mesma da API).")
    esperar_api()
    preencher_historico()
    chance = min(1.0, EVENTOS_POR_MINUTO * INTERVALO_S / 60)
    log.info("Consultando a API a cada %.0f s e enviando cerca de %.1f evento(s) por minuto.",
             INTERVALO_S, EVENTOS_POR_MINUTO)
    while True:
        try:
            chamar("GET", f"/summary?loja_id={sorteio.choice(list(LOJAS))}")
            if sorteio.random() < chance:
                evento = evento_ao_vivo()
                enviar(evento)
                log.info("Evento: %s / %s (%s) por %d s", evento["loja_id"], evento["equipamento_id"],
                         evento["tipo"], evento["duracao_s"])
        except (http.client.HTTPException, OSError) as erro:
            log.warning("Falha ao falar com a API: %s", erro)
        time.sleep(INTERVALO_S)


if __name__ == "__main__":
    principal()
