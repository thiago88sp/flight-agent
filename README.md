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

No formulário lateral escolha **Cidade** (nome ou código; várias separadas por vírgula) ou **Região**.
Veja o [glossário](#glossário-origens-e-destinos) do que pode ser digitado.

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

## Glossário: origens e destinos

Em **Origem** e **Destino** você pode digitar o **nome da cidade** (sem diferença entre maiúsculas,
minúsculas ou acentos: `São Paulo`, `sao paulo`, `SAO PAULO`) ou o **código IATA**.

- **Nome da cidade**: aceito no chat e no formulário para as cidades das tabelas abaixo. Cada nome
  vira o aeroporto principal indicado.
- **Código de aeroporto** (3 letras, ex.: `CGH`): aceito em qualquer lugar, para qualquer
  aeroporto do mundo, mesmo fora das tabelas.
- **Código de cidade** (ex.: `SAO`, `LON`): cobre todos os aeroportos da cidade de uma vez. Com
  preços reais (Travelpayouts) costuma trazer mais ofertas, porque inclui voos saindo ou chegando
  em qualquer um deles.
- No chat com Gemini ligado, cidades fora das tabelas também costumam ser entendidas. Com as regras
  locais, use o código.
- Para descobrir um código: busque "código IATA" + cidade, ou use a
  [busca da IATA](https://www.iata.org/en/publications/directories/code-search/).

### América do Sul — Brasil

| Nome aceito | Aeroporto usado | Código da cidade | Outros aeroportos da cidade |
|---|---|---|---|
| São Paulo, Guarulhos | `GRU` (Guarulhos) | `SAO` | `CGH` Congonhas, `VCP` Viracopos |
| Congonhas | `CGH` | `SAO` | |
| Campinas | `VCP` (Viracopos) | | |
| Rio de Janeiro, Rio | `GIG` (Galeão) | `RIO` | `SDU` Santos Dumont |
| Brasília | `BSB` | | |
| Belo Horizonte | `CNF` (Confins) | `BHZ` | `PLU` Pampulha |
| Salvador | `SSA` | | |
| Recife | `REC` | | |
| Fortaleza | `FOR` | | |
| Natal | `NAT` | | |
| Maceió | `MCZ` | | |
| João Pessoa | `JPA` | | |
| Porto Alegre | `POA` | | |
| Curitiba | `CWB` | | |
| Florianópolis | `FLN` | | |
| Manaus | `MAO` | | |

### América do Sul — outros países

| Nome aceito | Aeroporto usado | Código da cidade | Outros aeroportos da cidade |
|---|---|---|---|
| Buenos Aires (Argentina) | `EZE` (Ezeiza) | `BUE` | `AEP` Aeroparque |
| Santiago (Chile) | `SCL` | | |
| Lima (Peru) | `LIM` | | |
| Bogotá (Colômbia) | `BOG` | | |
| Montevidéu (Uruguai) | `MVD` | | |

### América do Norte

| Nome aceito | Aeroporto usado | Código da cidade | Outros aeroportos da cidade |
|---|---|---|---|
| Nova York, New York | `JFK` | `NYC` | `EWR` Newark, `LGA` LaGuardia |
| Miami | `MIA` | | `FLL` Fort Lauderdale (próximo) |
| Orlando | `MCO` | `ORL` | |
| Los Angeles | `LAX` | | |

### América Central e Caribe

| Nome aceito | Aeroporto usado | Código da cidade | Outros aeroportos da cidade |
|---|---|---|---|
| Cancún (México) | `CUN` | | |
| Punta Cana (Rep. Dominicana) | `PUJ` | | |
| Panamá (Cidade do Panamá) | `PTY` | | |

### Europa

| Nome aceito | Aeroporto usado | Código da cidade | Outros aeroportos da cidade |
|---|---|---|---|
| Lisboa | `LIS` | | |
| Porto | `OPO` | | |
| Madri, Madrid | `MAD` | | |
| Barcelona | `BCN` | | |
| Paris | `CDG` (Charles de Gaulle) | `PAR` | `ORY` Orly |
| Londres | `LHR` (Heathrow) | `LON` | `LGW` Gatwick, `STN` Stansted |
| Roma | `FCO` (Fiumicino) | `ROM` | `CIA` Ciampino |
| Milão | `MXP` (Malpensa) | `MIL` | `LIN` Linate, `BGY` Bergamo |
| Amsterdã | `AMS` | | |
| Frankfurt | `FRA` | | |
| Zurique | `ZRH` | | |

### Ásia e Oriente Médio

| Nome aceito | Aeroporto usado | Código da cidade | Outros aeroportos da cidade |
|---|---|---|---|
| Dubai (Emirados Árabes) | `DXB` | | |
| Tóquio, Tokyo (Japão) | `NRT` (Narita) | `TYO` | `HND` Haneda |

### África e Oceania

Nenhuma cidade com nome pré-cadastrado. Use o código, ex.: `JNB` (Joanesburgo), `CPT` (Cidade do
Cabo), `CMN` (Casablanca), `SYD` (Sydney), `AKL` (Auckland).

### Regiões (só como destino)

No chat ("qualquer cidade da Europa") ou no formulário, opção **Região**. A busca percorre todos
os destinos da lista:

| Região | Como escrever no chat | Destinos consultados |
|---|---|---|
| Europa | `Europa` | LIS, MAD, BCN, CDG, LHR, FCO, AMS, FRA, MXP, ZRH, OPO |
| América do Sul | `América do Sul`, `América Latina` | EZE, SCL, LIM, BOG, MVD |
| Estados Unidos | `Estados Unidos`, `EUA`, `USA` | MIA, MCO, JFK, LAX |
| Caribe / América Central | `Caribe`, `América Central` | CUN, PUJ, PTY |
| Nordeste do Brasil | `Nordeste` | REC, SSA, FOR, NAT, MCZ, JPA |

Para incluir cidades ou mudar uma região, edite `CITIES` e `REGIONS` em
[flight_agent/geo.py](flight_agent/geo.py) (e o nome de exibição em `CITY_NAMES`, em
[flight_agent/present.py](flight_agent/present.py)).

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
