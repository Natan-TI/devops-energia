# ⚡ Energia que dá Lucro · Painel do comerciante

API e painel web que mostram ao pequeno comerciante quanto ele perde com portas de geladeiras e freezers
abertas. **Os dados exibidos são simulados.**

Entrega da disciplina **Secure DevOps Tools & Cloud Computing** · FIAP · Global Solution 2026.2 · CitizenTech · 4ES

## 👥 Integrantes

| Nome | RM |
|---|---|
| Gustavo Henrique Santos Bonfim | RM98864 |
| João Pedro Marques | RM98307 |
| Kayky Paschoal Ribeiro | RM99929 |
| Lucas Yuji Farias Umada | RM99757 |
| Natan Eguchi dos Santos | RM98720 |

## 🔗 Links

- 📄 **Relatório com as evidências:** [docs/relatorio-devops.pdf](docs/relatorio-devops.pdf)
- 🌐 **URL pública do MVP:** http://100.60.176.115
- 🚀 **Pipeline:** https://github.com/Natan-TI/devops-energia/actions
- 🖼️ **Capturas originais:** [docs/evidencias](docs/evidencias)

A URL pública roda no AWS Academy Learner Lab, que desliga o ambiente depois de poucas horas. Fora das
sessões do laboratório, o endereço não responde; a publicação está comprovada no relatório.

## 📋 Ficha Técnica do MVP

| Campo | Conteúdo |
|---|---|
| Nome do produto | Energia que dá Lucro |
| Cidadão e território | Donos e funcionários de pequenos comércios de bairro (mercadinhos, padarias, açougues, lojas) em cidades brasileiras. |
| Problema, em uma frase | O pequeno comerciante paga caro de energia sem saber quais hábitos e equipamentos causam o desperdício. |
| Proposta de valor | Mostrar o desperdício em reais, avisar na hora em que ele acontece e sugerir ações simples, usando as câmeras que a loja já tem. |
| Arquitetura: componentes | API e painel do comerciante (Produção, este repositório) · detecção por câmera (Visão) · robô com sensores (Físico) · pipeline de dados (Dados) · consultor de eficiência com LLM local (Inteligência) · alertas e resumos automáticos (Automação) · modelo de negócio (Pitch). |
| Fontes de dados | Eventos simulados, no formato produzido pela detecção por câmera e pelo robô. Tarifa de energia da ANEEL. |
| Modelos de IA utilizados | Nenhum neste repositório. A detecção (YOLO11n) e o consultor (LLM local) rodam fora da nuvem e enviam só o resultado. |
| URL do MVP e repositório | http://100.60.176.115 · https://github.com/Natan-TI/devops-energia |
| Indicadores de impacto | R$ e kWh de desperdício evitados por loja ao mês · tempo médio de porta aberta · percentual de alertas resolvidos em poucos minutos. |
| ODS conectados | ODS 7 (energia acessível e limpa), ODS 12 (consumo responsável), ODS 9, ODS 11 e ODS 13. |

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

## 📈 Observabilidade

O Prometheus coleta as métricas da API a cada 5 segundos e avalia os alertas. O Grafana mostra as quatro
métricas de ouro. Preencha `GRAFANA_PASSWORD` no `.env` e suba junto com o painel:

```bash
docker compose -f docker-compose.yml -f docker-compose.observabilidade.yml up -d
```

- Grafana: http://localhost:3000 (abre direto no painel "4 métricas de ouro", em modo de leitura)
- Prometheus: http://localhost:9090/alerts

As duas portas só respondem no próprio computador (`127.0.0.1`).

| Métrica de ouro | O que o painel mostra | Alerta |
|---|---|---|
| Tráfego | Requisições por segundo, por rota, e eventos recebidos por minuto | `SemTrafego`: nenhuma requisição em 5 minutos |
| Erros | Taxa de respostas 5xx e respostas por código | `TaxaDeErrosAlta`: mais de 5% de erros por 30 segundos |
| Latência | Percentis p50, p95 e p99 e tempo médio por rota | `LatenciaAlta`: p95 acima de 0,5 s por 2 minutos |
| Saturação | CPU e memória da API, requisições em andamento | `MemoriaAlta`: mais de 400 MB por 5 minutos |

Há também o alerta `PainelForaDoAr`, para quando o Prometheus não consegue ler as métricas.

Para apontar o Prometheus para o painel publicado na nuvem, em vez do local:

```bash
ALVO=endereço:porta docker compose -f docker-compose.observabilidade.yml up -d
```

### Como disparar o alerta de erros

Pare o banco de dados. A API passa a responder com erro, e em cerca de um minuto o alerta
`TaxaDeErrosAlta` dispara:

```bash
docker compose stop db
```

Para voltar ao normal:

```bash
docker compose start db
```

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

## ☁️ Infraestrutura na AWS (Terraform)

A pasta `infra/` cria, na AWS, uma máquina EC2 com endereço fixo e um grupo de segurança.

- **Sem SSH:** a única porta de entrada é a 80. A administração e o deploy usam o AWS Systems Manager.
- **Segredos:** a senha do banco e a chave da API são geradas dentro da máquina e não saem dela.
  O estado do Terraform (`*.tfstate`) e os arquivos `*.tfvars` ficam fora do repositório.
- **Disco criptografado** e serviço de metadados só com token (IMDSv2).
- **Sem HTTPS:** o MVP não tem domínio próprio, então o painel responde em HTTP. Em produção, entraria um
  domínio com certificado.

O projeto foi feito para o AWS Academy Learner Lab, que não permite criar papéis de IAM: a máquina usa o
perfil `LabInstanceProfile`, que já existe no laboratório.

Com as credenciais da AWS no ambiente (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` e `AWS_SESSION_TOKEN`):

```bash
cd infra
```

```bash
terraform init
```

```bash
terraform apply
```

Ao final, o Terraform mostra a URL do painel. A primeira subida leva alguns minutos, porque a máquina
instala o Docker, constrói a imagem e gera o histórico de eventos.

Para apagar tudo:

```bash
terraform destroy
```

## 🚀 Pipeline

O arquivo `.github/workflows/pipeline.yml` roda a cada push:

| Job | O que faz |
|---|---|
| Testes | Roda os testes automáticos. |
| Gitleaks | Procura segredos em todo o histórico do repositório. |
| Semgrep | Analisa o código Python, o Dockerfile, o compose e o Terraform. |
| Build e Trivy | Constrói a imagem e barra vulnerabilidades altas ou críticas na imagem e na configuração. |
| Deploy na AWS | Só na branch principal e só se tudo passou: publica o commit na máquina pelo Systems Manager. |

O deploy usa três segredos do repositório (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` e
`AWS_SESSION_TOKEN`) e só roda quando a variável `DEPLOY_ATIVO` do repositório vale `true`. No Learner Lab,
as credenciais mudam a cada sessão, então os segredos precisam ser atualizados quando o laboratório é aberto.
