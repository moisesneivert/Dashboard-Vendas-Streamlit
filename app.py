import io
import re
import unicodedata
from pathlib import Path

import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="Dashboard de Vendas Lite",
    page_icon="📊",
    layout="wide",
)


COLUNAS_OBRIGATORIAS = {
    "data",
    "pedido_id",
    "cliente",
    "cidade",
    "estado",
    "regiao",
    "produto",
    "categoria",
    "vendedor",
    "canal_venda",
    "quantidade",
    "preco_unitario",
    "custo_unitario",
    "status_pagamento",
}

COLUNAS_CATEGORICAS = [
    "pedido_id",
    "cliente",
    "cidade",
    "estado",
    "regiao",
    "produto",
    "categoria",
    "vendedor",
    "canal_venda",
    "status_pagamento",
]


def normalizar_nome_coluna(nome_coluna):
    """
    Padroniza nomes de colunas para facilitar a leitura do CSV.

    Exemplos:
    - "Preço Unitário" vira "preco_unitario"
    - "Canal de Venda" vira "canal_de_venda"
    - "Data " vira "data"
    """
    nome = str(nome_coluna).strip().lower()
    nome = unicodedata.normalize("NFKD", nome)
    nome = "".join(caractere for caractere in nome if not unicodedata.combining(caractere))
    nome = re.sub(r"[^a-z0-9]+", "_", nome)
    nome = nome.strip("_")
    return nome


def converter_numero(serie):
    """
    Converte colunas numéricas aceitando formatos comuns no Brasil.

    Exemplos aceitos:
    - 1200.50
    - 1200,50
    - 1.200,50
    """
    if pd.api.types.is_numeric_dtype(serie):
        return pd.to_numeric(serie, errors="coerce").fillna(0)

    texto = serie.astype(str).str.strip()

    # Se houver vírgula, assume padrão brasileiro: 1.234,56
    if texto.str.contains(",", regex=False).any():
        texto = texto.str.replace(".", "", regex=False)
        texto = texto.str.replace(",", ".", regex=False)

    return pd.to_numeric(texto, errors="coerce").fillna(0)


def localizar_base_exemplo():
    """
    Localiza a base fictícia de exemplo.

    Recomenda-se usar:
    data/exemplo_vendas.csv

    A segunda opção, vendas_exemplo.csv na raiz, foi mantida
    apenas para compatibilidade com versões anteriores.
    """
    pasta_projeto = Path(__file__).parent

    caminhos_possiveis = [
        pasta_projeto / "data" / "exemplo_vendas.csv",
        pasta_projeto / "vendas_exemplo.csv",
    ]

    for caminho in caminhos_possiveis:
        if caminho.exists():
            return caminho

    raise FileNotFoundError(
        "Nenhum CSV foi enviado e a base de exemplo não foi encontrada. "
        "Envie um arquivo CSV pelo upload ou crie o arquivo "
        "'data/exemplo_vendas.csv'."
    )


def ler_csv_flexivel(origem):
    """
    Lê arquivos CSV com diferentes separadores e codificações.
    Isso ajuda quando o CSV vem separado por vírgula ou ponto e vírgula.
    """
    tentativas = [
        {"sep": None, "engine": "python", "encoding": "utf-8-sig"},
        {"sep": None, "engine": "python", "encoding": "utf-8"},
        {"sep": ";", "encoding": "latin1"},
        {"sep": ",", "encoding": "latin1"},
    ]

    ultimo_erro = None

    for configuracao in tentativas:
        try:
            if hasattr(origem, "seek"):
                origem.seek(0)

            dados = pd.read_csv(origem, **configuracao)

            if dados.empty:
                raise ValueError("O arquivo CSV está vazio.")

            return dados

        except Exception as erro:
            ultimo_erro = erro

    raise ValueError(f"Não foi possível ler o arquivo CSV. Último erro: {ultimo_erro}")


@st.cache_data(show_spinner=False)
def carregar_dados(nome_arquivo=None, conteudo_arquivo=None):
    """
    Carrega, valida e prepara os dados de vendas.
    """
    if conteudo_arquivo is not None:
        origem = io.BytesIO(conteudo_arquivo)
    else:
        origem = localizar_base_exemplo()

    dados = ler_csv_flexivel(origem)

    dados.columns = [normalizar_nome_coluna(coluna) for coluna in dados.columns]

    faltantes = COLUNAS_OBRIGATORIAS - set(dados.columns)

    if faltantes:
        raise ValueError(
            "A base não possui as seguintes colunas obrigatórias: "
            + ", ".join(sorted(faltantes))
        )

    dados = dados.copy()

    for coluna in COLUNAS_CATEGORICAS:
        dados[coluna] = dados[coluna].fillna("Não informado").astype(str).str.strip()

    dados["data"] = pd.to_datetime(dados["data"], errors="coerce", dayfirst=True)

    dados["quantidade"] = converter_numero(dados["quantidade"])
    dados["preco_unitario"] = converter_numero(dados["preco_unitario"])
    dados["custo_unitario"] = converter_numero(dados["custo_unitario"])

    dados = dados.dropna(subset=["data"])

    if dados.empty:
        raise ValueError(
            "Após o tratamento da coluna 'data', nenhum registro válido foi encontrado."
        )

    dados["faturamento"] = dados["quantidade"] * dados["preco_unitario"]
    dados["custo_total"] = dados["quantidade"] * dados["custo_unitario"]
    dados["lucro"] = dados["faturamento"] - dados["custo_total"]

    dados["margem_percentual"] = 0.0
    registros_com_faturamento = dados["faturamento"] > 0

    dados.loc[registros_com_faturamento, "margem_percentual"] = (
        dados.loc[registros_com_faturamento, "lucro"]
        / dados.loc[registros_com_faturamento, "faturamento"]
        * 100
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

    if isinstance(periodo, (tuple, list)) and len(periodo) == 2:
        inicio, fim = periodo
        dados = dados[
            (dados["data"].dt.date >= inicio)
            & (dados["data"].dt.date <= fim)
        ]

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
    margem = lucro / faturamento * 100 if faturamento else 0

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("Faturamento", formatar_moeda(faturamento))
    col2.metric("Lucro", formatar_moeda(lucro))
    col3.metric("Pedidos", f"{pedidos:,}".replace(",", "."))
    col4.metric("Ticket médio", formatar_moeda(ticket_medio))
    col5.metric("Margem", formatar_percentual(margem))

    st.caption(
        f"Quantidade total vendida: {quantidade:,.0f}".replace(",", ".")
    )


def exibir_graficos(dados):
    st.subheader("Análise visual")

    col1, col2 = st.columns(2)

    vendas_mes = (
        dados.groupby("mes", as_index=False)["faturamento"]
        .sum()
        .sort_values("mes")
        .set_index("mes")
    )

    categoria = (
        dados.groupby("categoria", as_index=False)["faturamento"]
        .sum()
        .sort_values("faturamento", ascending=False)
        .set_index("categoria")
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
        .sum()
        .sort_values("faturamento", ascending=False)
        .head(10)
        .set_index("produto")
    )

    vendedores = (
        dados.groupby("vendedor", as_index=False)["faturamento"]
        .sum()
        .sort_values("faturamento", ascending=False)
        .set_index("vendedor")
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
        .sum()
        .sort_values("faturamento", ascending=False)
        .set_index("regiao")
    )

    canais = (
        dados.groupby("canal_venda", as_index=False)["faturamento"]
        .sum()
        .sort_values("faturamento", ascending=False)
        .set_index("canal_venda")
    )

    with col5:
        st.markdown("**Faturamento por região**")
        st.bar_chart(regioes)

    with col6:
        st.markdown("**Faturamento por canal de venda**")
        st.bar_chart(canais)


def exibir_tabelas(dados):
    st.subheader("Tabelas analíticas")

    aba1, aba2, aba3 = st.tabs(
        [
            "Resumo por produto",
            "Resumo por vendedor",
            "Base filtrada",
        ]
    )

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

        st.dataframe(
            resumo_produto,
            use_container_width=True,
            hide_index=True,
            column_config={
                "quantidade_vendida": st.column_config.NumberColumn(
                    "Quantidade vendida",
                    format="%.0f",
                ),
                "faturamento": st.column_config.NumberColumn(
                    "Faturamento",
                    format="R$ %.2f",
                ),
                "lucro": st.column_config.NumberColumn(
                    "Lucro",
                    format="R$ %.2f",
                ),
                "margem_media": st.column_config.NumberColumn(
                    "Margem média (%)",
                    format="%.2f%%",
                ),
            },
        )

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

        st.dataframe(
            resumo_vendedor,
            use_container_width=True,
            hide_index=True,
            column_config={
                "pedidos": st.column_config.NumberColumn(
                    "Pedidos",
                    format="%d",
                ),
                "quantidade_vendida": st.column_config.NumberColumn(
                    "Quantidade vendida",
                    format="%.0f",
                ),
                "faturamento": st.column_config.NumberColumn(
                    "Faturamento",
                    format="R$ %.2f",
                ),
                "lucro": st.column_config.NumberColumn(
                    "Lucro",
                    format="R$ %.2f",
                ),
            },
        )

    with aba3:
        base_filtrada = dados.sort_values("data", ascending=False)

        st.dataframe(
            base_filtrada,
            use_container_width=True,
            hide_index=True,
        )

        buffer = io.StringIO()
        base_filtrada.to_csv(buffer, index=False, encoding="utf-8-sig")

        st.download_button(
            label="Baixar base filtrada em CSV",
            data=buffer.getvalue(),
            file_name="base_filtrada_vendas.csv",
            mime="text/csv",
        )


def exibir_formato_csv():
    with st.expander("Formato esperado do CSV"):
        st.markdown(
            """
            A base enviada deve conter as seguintes colunas:

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

            A coluna `data` pode estar em formatos como `AAAA-MM-DD` ou `DD/MM/AAAA`.

            O sistema também aceita nomes com espaços e acentos, por exemplo:

            - `Preço Unitário`
            - `Custo Unitário`
            - `Canal Venda`
            - `Canal de Venda`

            Esses nomes são normalizados automaticamente durante o carregamento.
            """
        )


def main():
    st.title("Dashboard de Vendas Lite")
    st.caption(
        "Análise comercial com Python, Pandas e Streamlit: filtros, KPIs, gráficos e exportação."
    )

    with st.sidebar:
        st.markdown("### Base de dados")

        arquivo = st.file_uploader(
            "Envie um CSV de vendas ou use a base exemplo",
            type=["csv"],
        )

        st.markdown("---")
        st.caption(
            "Este projeto é a versão inicial/lite. "
            "A versão Pro contém autenticação, banco de dados, metas e previsão."
        )

    try:
        if arquivo is not None:
            dados = carregar_dados(
                nome_arquivo=arquivo.name,
                conteudo_arquivo=arquivo.getvalue(),
            )
        else:
            dados = carregar_dados()

    except Exception as erro:
        st.error(f"Erro ao carregar os dados: {erro}")
        exibir_formato_csv()
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

    exibir_formato_csv()


if __name__ == "__main__":
    main()
