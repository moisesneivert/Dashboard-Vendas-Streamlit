import io
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Dashboard de Vendas",
    page_icon="📊",
    layout="wide",
)

COLUNAS_OBRIGATORIAS = {
    "data", "pedido_id", "cliente", "cidade", "estado", "regiao",
    "produto", "categoria", "vendedor", "canal_venda", "quantidade",
    "preco_unitario", "custo_unitario", "status_pagamento",
}

@st.cache_data
def carregar_dados(arquivo):
    """Carrega dados de vendas a partir de CSV enviado pelo usuário ou base local."""
    if arquivo is not None:
        dados = pd.read_csv(arquivo)
    else:
        caminho_base = Path(__file__).parent / "vendas_exemplo.csv"
        dados = pd.read_csv(caminho_base)

    dados.columns = [col.strip().lower() for col in dados.columns]

    faltantes = COLUNAS_OBRIGATORIAS - set(dados.columns)
    if faltantes:
        raise ValueError(
            "A base não possui as seguintes colunas obrigatórias: "
            + ", ".join(sorted(faltantes))
        )

    dados["data"] = pd.to_datetime(dados["data"], errors="coerce")
    dados["quantidade"] = pd.to_numeric(dados["quantidade"], errors="coerce").fillna(0)
    dados["preco_unitario"] = pd.to_numeric(dados["preco_unitario"], errors="coerce").fillna(0)
    dados["custo_unitario"] = pd.to_numeric(dados["custo_unitario"], errors="coerce").fillna(0)
    dados = dados.dropna(subset=["data"])

    dados["faturamento"] = dados["quantidade"] * dados["preco_unitario"]
    dados["custo_total"] = dados["quantidade"] * dados["custo_unitario"]
    dados["lucro"] = dados["faturamento"] - dados["custo_total"]
    dados["margem_percentual"] = dados.apply(
        lambda linha: (linha["lucro"] / linha["faturamento"] * 100)
        if linha["faturamento"] > 0 else 0,
        axis=1,
    )
    dados["mes"] = dados["data"].dt.to_period("M").dt.to_timestamp()
    return dados


def formatar_moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_percentual(valor):
    return f"{valor:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")


def aplicar_filtros(dados):
    st.sidebar.header("Filtros")

    periodo_min = dados["data"].min().date()
    periodo_max = dados["data"].max().date()

    periodo = st.sidebar.date_input(
        "Período",
        value=(periodo_min, periodo_max),
        min_value=periodo_min,
        max_value=periodo_max,
    )

    if len(periodo) == 2:
        inicio, fim = periodo
        dados = dados[(dados["data"].dt.date >= inicio) & (dados["data"].dt.date <= fim)]

    filtros_multiselect = {
        "regiao": "Região",
        "estado": "Estado",
        "categoria": "Categoria",
        "produto": "Produto",
        "vendedor": "Vendedor",
        "canal_venda": "Canal de venda",
        "status_pagamento": "Status de pagamento",
    }

    for coluna, rotulo in filtros_multiselect.items():
        opcoes = sorted(dados[coluna].dropna().unique())
        selecionados = st.sidebar.multiselect(rotulo, opcoes)
        if selecionados:
            dados = dados[dados[coluna].isin(selecionados)]

    return dados


def exibir_kpis(dados):
    faturamento = dados["faturamento"].sum()
    lucro = dados["lucro"].sum()
    pedidos = dados["pedido_id"].nunique()
    quantidade = dados["quantidade"].sum()
    ticket_medio = faturamento / pedidos if pedidos else 0
    margem = (lucro / faturamento * 100) if faturamento else 0

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Faturamento", formatar_moeda(faturamento))
    col2.metric("Lucro", formatar_moeda(lucro))
    col3.metric("Pedidos", f"{pedidos:,}".replace(",", "."))
    col4.metric("Ticket médio", formatar_moeda(ticket_medio))
    col5.metric("Margem", formatar_percentual(margem))


def exibir_graficos(dados):
    st.subheader("Análise visual")
    col1, col2 = st.columns(2)

    vendas_mes = (
        dados.groupby("mes", as_index=False)["faturamento"]
        .sum().sort_values("mes").set_index("mes")
    )
    categoria = (
        dados.groupby("categoria", as_index=False)["faturamento"]
        .sum().sort_values("faturamento", ascending=False).set_index("categoria")
    )

    with col1:
        st.markdown("**Faturamento por mês**")
        st.line_chart(vendas_mes)
    with col2:
        st.markdown("**Faturamento por categoria**")
        st.bar_chart(categoria)

    col3, col4 = st.columns(2)
    top_produtos = (
        dados.groupby("produto", as_index=False)["faturamento"]
        .sum().sort_values("faturamento", ascending=False).head(10).set_index("produto")
    )
    vendedores = (
        dados.groupby("vendedor", as_index=False)["faturamento"]
        .sum().sort_values("faturamento", ascending=False).set_index("vendedor")
    )

    with col3:
        st.markdown("**Top 10 produtos por faturamento**")
        st.bar_chart(top_produtos)
    with col4:
        st.markdown("**Faturamento por vendedor**")
        st.bar_chart(vendedores)

    col5, col6 = st.columns(2)
    regioes = (
        dados.groupby("regiao", as_index=False)["faturamento"]
        .sum().sort_values("faturamento", ascending=False).set_index("regiao")
    )
    canais = (
        dados.groupby("canal_venda", as_index=False)["faturamento"]
        .sum().sort_values("faturamento", ascending=False).set_index("canal_venda")
    )

    with col5:
        st.markdown("**Faturamento por região**")
        st.bar_chart(regioes)
    with col6:
        st.markdown("**Faturamento por canal de venda**")
        st.bar_chart(canais)


def exibir_tabelas(dados):
    st.subheader("Tabelas analíticas")
    aba1, aba2, aba3 = st.tabs(["Resumo por produto", "Resumo por vendedor", "Base filtrada"])

    with aba1:
        resumo_produto = (
            dados.groupby(["categoria", "produto"], as_index=False)
            .agg(
                quantidade_vendida=("quantidade", "sum"),
                faturamento=("faturamento", "sum"),
                lucro=("lucro", "sum"),
                margem_media=("margem_percentual", "mean"),
            )
            .sort_values("faturamento", ascending=False)
        )
        st.dataframe(resumo_produto, use_container_width=True, hide_index=True)

    with aba2:
        resumo_vendedor = (
            dados.groupby("vendedor", as_index=False)
            .agg(
                pedidos=("pedido_id", "nunique"),
                quantidade_vendida=("quantidade", "sum"),
                faturamento=("faturamento", "sum"),
                lucro=("lucro", "sum"),
            )
            .sort_values("faturamento", ascending=False)
        )
        st.dataframe(resumo_vendedor, use_container_width=True, hide_index=True)

    with aba3:
        st.dataframe(dados.sort_values("data", ascending=False), use_container_width=True, hide_index=True)
        buffer = io.StringIO()
        dados.to_csv(buffer, index=False, encoding="utf-8-sig")
        st.download_button(
            label="Baixar base filtrada em CSV",
            data=buffer.getvalue(),
            file_name="base_filtrada_vendas.csv",
            mime="text/csv",
        )


def main():
    st.title("Dashboard de Vendas com Pandas + Streamlit")
    st.caption("Projeto de portfólio para análise comercial, filtros, KPIs e visualização de dados.")

    with st.sidebar:
        st.markdown("### Base de dados")
        arquivo = st.file_uploader("Envie um CSV de vendas ou use a base exemplo", type=["csv"])

    try:
        dados = carregar_dados(arquivo)
    except Exception as erro:
        st.error(f"Erro ao carregar os dados: {erro}")
        st.stop()

    dados_filtrados = aplicar_filtros(dados)
    if dados_filtrados.empty:
        st.warning("Nenhum dado encontrado para os filtros selecionados.")
        st.stop()

    exibir_kpis(dados_filtrados)
    st.divider()
    exibir_graficos(dados_filtrados)
    st.divider()
    exibir_tabelas(dados_filtrados)

    with st.expander("Formato esperado do CSV"):
        st.markdown(
            """
            A base enviada deve conter as colunas abaixo:

            `data`, `pedido_id`, `cliente`, `cidade`, `estado`, `regiao`,
            `produto`, `categoria`, `vendedor`, `canal_venda`, `quantidade`,
            `preco_unitario`, `custo_unitario`, `status_pagamento`.

            A coluna `data` deve estar preferencialmente no formato `AAAA-MM-DD`.
            """
        )


if __name__ == "__main__":
    main()
