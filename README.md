# Dashboard de Vendas com Pandas + Streamlit

Projeto de análise de dados e criação de dashboards.

## Objetivo

Criar um dashboard comercial com:

- upload de CSV;
- filtros por período, região, estado, categoria, produto, vendedor, canal e status;
- KPIs principais;
- gráficos de faturamento;
- tabelas analíticas;
- exportação da base filtrada.

## Tecnologias

- Python
- Pandas
- Streamlit

## Estrutura do projeto

```text
dashboard_vendas_streamlit/
├── app.py
├── vendas_exemplo.csv
├── requirements.txt
└── README.md
```

## Como rodar

1. Crie um ambiente virtual:

```bash
python -m venv .venv
```

2. Ative o ambiente virtual:

No Windows:

```bash
.venv\Scripts\activate
```

No macOS/Linux:

```bash
source .venv/bin/activate
```

3. Instale as dependências:

```bash
pip install -r requirements.txt
```

4. Execute o dashboard:

```bash
streamlit run app.py
```

## Colunas esperadas no CSV

A base enviada deve conter:

```text
data
pedido_id
cliente
cidade
estado
regiao
produto
categoria
vendedor
canal_venda
quantidade
preco_unitario
custo_unitario
status_pagamento
```

