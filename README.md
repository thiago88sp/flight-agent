# Agente de Passagens ✈️

Agente que recebe um pedido (texto livre ou formulário), varre datas e destinos, ranqueia as ofertas,
compara com o histórico de preços e dispara alertas. **Projetado para gastar o mínimo de IA**:
a busca, o ranking e os alertas são Python puro; o chat só precisa de IA para interpretar a frase, e
mesmo isso é opcional (há um interpretador por regras, grátis e offline).

## O que ele faz

- **Chat e formulário** (Streamlit): `streamlit run app.py`
- **Linha de comando**, própria para agendar (cron): `python -m flight_agent ...`
- **Um destino, uma lista ou uma região inteira** ("qualquer cidade da Europa")
- **Datas flexíveis** (± dias) e estadia (ida e volta ou só ida), filtro de escalas e teto de preço
- **Botão de compra** em cada oferta: abre o itinerário no Aviasales (preços reais) ou a mesma busca no Google Flights (preços simulados)
- Aceita **nomes de cidades** no formulário ("São Paulo", "Lisboa") além de códigos IATA
- **Histórico** de menores preços por rota e alerta de queda ou de preço abaixo do teto
- Preços **simulados** por padrão; **reais** via Travelpayouts / Aviasales Data API (grátis)

## Instalação

```bash
git clone https://github.com/thiago88sp/flight-agent.git && cd flight-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # opcional: edite para ligar Travelpayouts / Gemini / etc.
```

> Em Debian/Ubuntu recentes o `pip` global é bloqueado (PEP 668); por isso o `venv`.
> No WSL, se o projeto estiver em `/mnt/c` (ex.: OneDrive), crie o venv no disco Linux, que é
> muito mais rápido: `python3 -m venv ~/.venvs/flight-agent && source ~/.venvs/flight-agent/bin/activate`.

## Uso

### Interface web

```bash
streamlit run app.py
```

No chat, escreva em português:

- `GRU para Lisboa por volta de 10/12, 10 dias, até R$ 4000`
- `GRU para qualquer cidade da Europa em março, 10 dias, direto`
- `para Paris, Londres ou Roma saindo de CNF em 05/01, uma semana`
- `Rio de Janeiro -> Miami 15 de janeiro, 12 dias, ±3 dias, máximo 5 mil`

No formulário lateral escolha **Cidade(s)** (IATA separados por vírgula) ou **Região**.

### Linha de comando

```bash
python -m flight_agent "GRU para qualquer cidade da Europa em 10/12, 10 dias, até R$ 3000"
python -m flight_agent --origin GRU --dest LIS,MAD --depart 2026-12-10 --stay 10 --flex 3
python -m flight_agent --origin GRU --region europa --depart 2026-12-10 --stay 10 --max-calls 120
```

Regiões disponíveis: `europa`, `america_do_sul`, `eua`, `caribe`, `nordeste`
(listas em `flight_agent/geo.py`; edite à vontade).

### Rodar sozinho todo dia (sem interação)

Use os parâmetros diretos (0 tokens). Chame o Python do venv, sem ativar nada:

```cron
0 7 * * * cd "/caminho/flight-agent" && .venv/bin/python -m flight_agent --origin GRU --region europa --depart 2026-12-10 --stay 10 --flex 1 --max-price 3500
```

## Custo de IA e consultas

| Interpretador (`LLM_PROVIDER`) | Custo | Como ativar |
|---|---|---|
| `rules` (padrão) | grátis, offline, sem conta | nada a fazer |
| `gemini` | grátis com limites | chave em aistudio.google.com → `GEMINI_API_KEY` |
| `ollama` | grátis, offline | `OLLAMA_MODEL=qwen2.5:3b` (com o Ollama instalado) |
| `anthropic` | pago por token | `ANTHROPIC_API_KEY` + `pip install anthropic` |

- Assinaturas de consumo (Gemini Plus, planos do Claude) **não** incluem chave de API; a chave
  gratuita do Gemini é criada à parte no Google AI Studio.
- No plano gratuito do Gemini o Google pode usar o conteúdo enviado para melhorar produtos
  (aqui só vai a frase da busca).
- Se o LLM falhar (rede, cota, resposta ruim), o app cai sozinho nas regras locais.
- **Consultas** = destinos × (2×flex+1) datas. O limite padrão é `MAX_CALLS=80`; acima disso a busca
  é recusada com uma mensagem. Em pedidos só com o mês ("Europa em março") a flexibilidade é
  ajustada automaticamente para caber no limite.

## Preços reais (Travelpayouts)

> O plano gratuito do Amadeus (Self-Service) foi desativado em 17/07; hoje ele só atende empresas
> via contrato. Por isso o projeto usa a Aviasales Data API, gratuita.

1. Crie conta grátis em <https://www.travelpayouts.com>. O cadastro pede o link de um "canal"
   (site, rede social etc.); para lab, o link do seu GitHub ou LinkedIn serve.
2. Copie o token em <https://app.travelpayouts.com/profile/api-token> e preencha
   `TRAVELPAYOUTS_TOKEN` no `.env`.
3. A barra lateral passa a mostrar "✅ Travelpayouts".

Os preços vêm do **cache** de buscas recentes feitas no Aviasales, não de consulta em tempo real.
Rotas e datas pouco procuradas podem voltar sem resultado, e o valor pode estar defasado em alguns
dias. Para acompanhar tendência e quedas de preço isso basta; confirme o preço antes de comprar.

Como o cache raramente tem o par exato de datas pedido, o app faz **uma consulta por destino e mês**
e filtra localmente: ida dentro da janela (± flexibilidade) e estadia de `dias ± STAY_TOLERANCE`
(padrão 3). Por isso a volta mostrada pode diferir alguns dias do pedido. Com preços simulados a
busca continua sendo em grade (uma consulta por data).

Pedidos só com o mês ("Europa em março") consideram qualquer dia do mês. Quando nada se encaixa,
o app mostra as **datas mais próximas que têm preço** (para até 3 destinos, busca qualquer data da
rota) e um botão para ver as datas exatas no Google Flights. Na prática o cache gratuito tem pouca
coisa a mais de 2–3 meses de antecedência.

## Estrutura

```
app.py                  interface Streamlit (chat + formulário)
flight_agent/
  parsing.py            texto livre -> parâmetros (regras, Gemini, Ollama, Anthropic) e validação
  search.py             grade datas × destinos, ranking, análise e alertas
  providers.py          MockProvider (simulado) e TravelpayoutsProvider (real)
  present.py            textos amigáveis: cidades, companhias, datas, preços e link de compra
  geo.py                cidades conhecidas e regiões
  history.py            histórico de preços (JSON Lines)
  notify.py             ponto de extensão para alertas (hoje imprime)
  config.py             variáveis de ambiente / .env
  cli.py, __main__.py   linha de comando
tests/                  pytest (parser, busca, histórico, interface)
.github/workflows/      CI: roda pytest a cada push
```

## Testes

```bash
pip install -r requirements-dev.txt
pytest -q
```

Cobrem o interpretador por regras (incluindo regiões e listas), busca em grade, limite de consultas,
alertas, fallback de LLM e a interface (com `streamlit.testing`). **Não há testes automáticos** para as
chamadas reais ao Travelpayouts, Gemini e Ollama (dependem de rede e credenciais).

## Limitações conhecidas

- Preços simulados são fictícios; servem para validar o fluxo, não para decidir compras.
- O interpretador por regras entende o formato "origem para destino, data, dias, teto"; frases muito
  livres funcionam melhor com Gemini/Ollama. Cidades não listadas em `geo.py` precisam do código IATA.
- Sem busca "para qualquer lugar do mundo": o conjunto de destinos vem das regiões definidas em `geo.py`.
- O alerta hoje só imprime; troque `notify()` por Telegram, e-mail ou WhatsApp.

## Próximos passos sugeridos

- Notificação por Telegram/e-mail em `notify.py`.
- Histórico em SQLite e gráfico de evolução de preço por rota.
- Provedores adicionais (mesma interface `search(origin, dest, depart, ret)`).
