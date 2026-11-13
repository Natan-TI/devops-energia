# ⚡ Energia que dá Lucro · Painel do comerciante

API e painel web que mostram ao pequeno comerciante quanto ele perde com portas de geladeiras e freezers
abertas. **Os dados exibidos são simulados.**

Entrega da disciplina **Secure DevOps Tools & Cloud Computing** · FIAP · Global Solution 2026.2 · CitizenTech · 4ES

> Em construção: pipeline, Terraform, observabilidade e Ficha Técnica entram nas próximas etapas.

## ▶️ Como rodar

Requer Docker com o plugin Compose.

1. Copie `.env.example` para `.env` e preencha `POSTGRES_PASSWORD` e `API_KEY` com valores aleatórios:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. Suba tudo:

   ```bash
   docker compose up -d --build
   ```

3. Abra http://localhost:8000. O simulador preenche 30 dias de histórico na primeira vez e depois envia um
   evento a cada 5 segundos.

Para parar e apagar os dados:

```bash
docker compose down -v
```

## 🧩 O que sobe

| Serviço | O que faz |
|---|---|
| `db` | PostgreSQL 17. Não publica porta: só é acessível pela rede interna do compose. |
| `api` | FastAPI com a API e as telas. Roda como usuário sem privilégios, com sistema de arquivos somente leitura. |
| `simulador` | Envia eventos e alertas fictícios para a API: portas abertas (câmera) e luzes acesas em ambiente vazio (robô). |

## 🖥️ Telas

- **Visão geral** (`/`): desperdício estimado em reais e kWh no mês, projeção para 12 meses, divisão por causa
  (porta aberta ou luz acesa), por dia e por equipamento.
- **Eventos** (`/eventos`): lista com filtro por equipamento e período, e exportação em CSV.
- **Alertas** (`/alertas`): alertas enviados ao comerciante.
- **Sugestões** (`/sugestoes`): recomendações do consultor de eficiência (arquivo de exemplo).

## 🔌 API

A documentação interativa fica em `/docs`.

| Rota | Para quê |
|---|---|
| `POST /events` | Registrar um evento. Exige o cabeçalho `X-API-Key`. |
| `GET /events` · `GET /events.csv` | Listar ou exportar eventos (`loja_id`, `equipamento_id`, `desde`, `ate`). |
| `POST /alerts` · `GET /alerts` | Registrar (com `X-API-Key`) e listar alertas. |
| `GET /summary?loja_id=&periodo=AAAA-MM` | Resumo do mês: total em R$ e kWh, por equipamento e por dia. |
| `GET /recommendations?loja_id=` | Recomendações do consultor de eficiência. |
| `GET /health` · `GET /metrics` | Verificação de saúde e métricas para o Prometheus. |

Exemplo de evento:

```json
{"id": "3f2b6c1e-8a4d-4e0b-9d53-0c7a1e5b9f20", "loja_id": "padaria-01", "equipamento_id": "expositor-bebidas",
 "tipo": "porta_aberta", "origem": "acv", "inicio": "2026-11-12T14:03:10-03:00",
 "duracao_s": 95, "custo_estimado_rs": 0.0133}
```

## 🧮 De onde vêm os números

Os eventos são simulados, mas os parâmetros do custo têm origem declarada:

`custo = potência (kW) × fator de perda × horas × tarifa (R$/kWh)`

| Parâmetro | Valor | Origem |
|---|---|---|
| Tarifa | R$ 0,789/kWh | Enel SP, subgrupo B3 convencional, sem impostos: TUSD 472,42 + TE 316,96 R$/MWh (ANEEL, Resolução Homologatória 3.596/2026, em vigor desde 04/07/2026). Com impostos, a conta real é maior. |
| Expositor vertical grande | 0,91 kW | Potência de catálogo de um expositor de 569 L (Fricon VCFM569), em anúncio de loja. |
| Expositor vertical de 1 porta | 0,36 kW | Potência de catálogo de um expositor de 403 L (Metalfrio VB40), em anúncio de loja. |
| Freezer horizontal | 0,14 kW | Potência de um freezer de 417 L (Metalfrio DA420IF), em site de análise de produtos. |
| Fator de perda da porta aberta | 0,70 | **Premissa do grupo, sem medição.** Com a porta aberta, o compressor trabalha sem parar; fechado, ele fica ligado cerca de 30% do tempo. |
| Lâmpada | 0,018 kW | **Premissa do grupo:** lâmpada tubular LED de 18 W. O ambiente soma as lâmpadas (6 a 40). |
| Fator de perda da luz acesa | 1,00 | Luz acesa em ambiente vazio: toda a energia é desperdício. |

Limites dessa estimativa: ela não conta o tempo que o equipamento leva para recuperar a temperatura depois
que a porta fecha, nem a perda de produtos. As potências vêm de anúncios e não da etiqueta do Inmetro.
A quantidade de aberturas por dia e a frequência de luzes esquecidas são inventadas pelo simulador.

## 🧪 Testes

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

```bash
pip install -r requirements-dev.txt
```

```bash
python -m pytest
```

Os testes usam um banco SQLite temporário e não precisam do Docker.
