# Planning — Brazil Cost of Living: Análises de Dados Públicos Brasileiros

## Contexto

Este projeto nasce a partir do repositório [`flight-fares-analysis`](https://github.com/fredericohorst/flight-fares-analysis),
que analisa tarifas aéreas domésticas brasileiras (ANAC, 2002–presente) deflacionadas pelo IPCA,
com tratamento cuidadoso de quebra metodológica (Resolução ANAC 140/2010) e um pipeline de
limpeza/normalização de schemas variáveis (`FilesProcessor`).

A ideia é expandir essa linha de análise para outros bens/indicadores brasileiros, e no final
comparar a evolução de preços **em termos de salário mínimo** (não apenas inflação), trazendo
também o endividamento das famílias como camada de contexto explicativo.

**Decisão de arquitetura**: repositórios separados por domínio, com um pacote Python
compartilhado para lógica reutilizável (deflação, conversão para salário mínimo, helpers de
séries temporais), em vez de um monorepo único.

---

## Repositórios a criar

### 1. `flight-fares-analysis` *(já existe)*
Análise de tarifas aéreas domésticas brasileiras (ANAC), deflacionadas pelo IPCA, com
tratamento da quebra metodológica de 2010 (expansão de ~65 rotas tronco para 2000+ rotas).

- Fonte: [ANAC downloads](https://sistemas.anac.gov.br/sas/downloads/view/frmDownload.aspx)
- Fonte (inflação): [IBGE — IPCA histórico](https://www.ibge.gov.br/estatisticas/economicas/precos-e-custos/9256-indice-nacional-de-precos-ao-consumidor-amplo.html)

### 2. `real-estate-price-analysis`
Evolução de preços de imóveis no Brasil — venda e locação, por cidade, ao longo do tempo.

- Fonte principal: [Índice FipeZAP](https://www.fipe.org.br/pt-br/indices/fipezap/) — série mensal,
  R$/m², 56 cidades (22 capitais), download em Excel.
- Fonte complementar (opcional, dado de transação real em vez de anúncio): ITBI de São Paulo
  (Sistema de Transações Imobiliárias — SITI, Prefeitura de SP). Mais granular, porém mais
  trabalhoso (schema inconsistente entre anos, precisa de tratamento tipo `COLUMN_ALIASES`).
- Fonte complementar (crédito imobiliário): IVG-R — Índice de Valores de Garantia de Imóveis
  Residenciais Financiados (Banco Central), trimestral.

### 3. `new-car-price-analysis`
Evolução de preço de carro novo / tabela FIPE, com possibilidade de curva de depreciação por
modelo.

- Fonte 1 (preço de revenda/mercado, não é o preço de tabela da concessionária): Tabela FIPE via
  API gratuita [fipe.parallelum.com.br](https://fipe.parallelum.com.br/) (ex-deividfortuna),
  histórico mensal desde ~2001, endpoint de histórico por código FIPE.
- Fonte 2 (inflação específica de veículo novo, mais fiel ao conceito de "carro 0km"): subitem
  IPCA "veículo automotor novo" — [IBGE/SIDRA](https://sidra.ibge.gov.br/), mensal desde 1999.
- Fonte complementar (volume, não preço): ANFAVEA / FENABRAVE — vendas e produção mensal por
  categoria.

### 4. `br-economic-indicators` *(pacote compartilhado — não é um repo de "análise")*
Biblioteca Python reutilizável com:
- Funções de deflação (IPCA/INPC) reaproveitando a lógica já validada em `flight-fares-analysis`.
- Conversão de valores nominais para "quantidade de salários mínimos".
- Helpers de ingestão de séries temporais do BCB (API SGS), IBGE (SIDRA) e Ipeadata.

Consumido como dependência pelos demais repos.

**Fontes de dado — salário mínimo:**
- [Ipeadata](http://www.ipeadata.gov.br/) — série de salário mínimo **nominal** vigente, mensal,
  desde julho/1940. API OData disponível, ou download CSV direto.
- Ipeadata — série 37667, salário mínimo **real** (já deflacionado pelo INPC/IBGE), também desde
  1940, com metodologias de deflator diferentes por período histórico (documentar como quebra,
  no mesmo espírito da quebra ANAC 2010).
- Para a comparação com salário mínimo (foco deste projeto), usar a série **nominal**.

### 5. `household-debt-indicators` *(opcional — avaliar se vira repo próprio ou pasta dentro do consolidado)*
Ingestão das séries de endividamento e comprometimento de renda das famílias.

- Fonte: Banco Central do Brasil — Sistema Gerenciador de Séries Temporais (SGS), API pública
  sem necessidade de cadastro.
  - Padrão de URL: `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=csv&dataInicial={dd/mm/aaaa}&dataFinal={dd/mm/aaaa}`
  - Série 29037 — Endividamento das famílias com o SFN em relação à renda acumulada 12 meses
    (com habitação).
  - Série 29038 — idem, exceto crédito habitacional.
  - Série 29034 — Comprometimento de renda das famílias com serviço da dívida (com ajuste
    sazonal).
  - Séries 29265/29266 — Comprometimento de renda, variações (sem ajuste sazonal / exceto
    habitação).

**Atenção**: essas séries do BCB começam por volta de 2005 (dado de crédito estruturado é mais
recente). Isso limita o período "completo" da análise consolidada (aviação + imóvel + salário +
endividamento) a aproximadamente 2005–hoje, mesmo que ANAC e salário mínimo tenham histórico
mais longo.

### 6. `brazil-cost-of-living-analysis` *(repo-vitrine final)*
Consolida os datasets/outputs dos repos acima (via `br-economic-indicators`) e responde à
pergunta central: **quantos salários mínimos custava um imóvel / carro novo / passagem aérea ao
longo do tempo, e como o endividamento das famílias se relaciona com essa evolução.**

---

## Ordem sugerida de construção

1. `br-economic-indicators` (mesmo que mínimo, só com deflação + conversão pra salário mínimo)
2. `real-estate-price-analysis`
3. `new-car-price-analysis`
4. `brazil-cost-of-living-analysis` (por último, quando os outros já tiverem output pronto)

`household-debt-indicators` entra quando decidirmos se vira repo próprio ou pasta do consolidado.

---

## Notas de estilo (herdadas de `flight-fares-analysis`)

- Tratar toda quebra metodológica explicitamente (documentar no README, não esconder na análise).
- Pipeline de normalização de schema robusto a variações de formato/encoding entre arquivos de
  diferentes períodos (ver `FilesProcessor.COLUMN_ALIASES` do projeto original como referência).
- Preferir estatísticas ponderadas (ex: por volume/seats/amostra) a médias simples, quando a
  granularidade da fonte permitir.
- README com metodologia clara: fontes, pipeline, e limitações de comparabilidade entre períodos.
