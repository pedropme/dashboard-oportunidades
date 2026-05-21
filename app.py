import streamlit as st
import pandas as pd
import unicodedata
import altair as alt
import geopandas as gpd

# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="Matriz de Performance",
    layout="wide"
)

st.markdown("""
<style>
    .block-container {
        padding-top: 0.5rem;
        padding-bottom: 0rem;
    }
    [data-testid="stSidebarContent"] {
        padding-top: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# =========================
# HEADER
# =========================
col_logo_h, col_title_h = st.columns([1, 5])

with col_logo_h:
    st.image("dados/logo_pme.png", use_container_width=True)
    st.markdown(
        """<div style='
            text-align:center;
            font-size:14px;
            font-weight:300;
            color:#555;
            margin-top:2px;
        '>Projeto Horizonte</div>""",
        unsafe_allow_html=True
    )

with col_title_h:
    st.markdown(
        "<h1 style='text-align:center; margin-top:20px;'>Resumo de Oportunidades</h1>",
        unsafe_allow_html=True
    )

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Resumo por Vendedor",
    "🏙️ Resumo por Município",
    "📈 Matriz de Performance",
    "🧪 DEBUG MAPA"
])

# =========================
# MAPA (CACHE)
# =========================
@st.cache_data
def load_municipios():

    gdf = gpd.read_file("maps/municipios.geojson")

    gdf["CD_MUN"] = (
        gdf["CD_MUN"]
        .astype(str)
        .str.strip()
    )

    return gdf

gdf_mun = load_municipios()

# =========================
# BASES
# =========================
clientes = pd.read_excel("dados/clientes.xlsx")
opp = pd.read_excel("dados/oportunidades.xlsx")
territorio = pd.read_excel("dados/territorio.xlsx")

# =========================
# BASE VENDAS
# =========================
vendas = pd.read_excel(
    "dados/vendas.xlsx"
)


# =========================
# PADRÃO DE COLUNAS
# =========================
COL_DOC = "Documento"
COL_CONC = "Concessionaria"
COL_MUN = "CD_MUN"
COL_VEND = "Vendedor"

# =========================
# NORMALIZAÇÃO
# =========================
def normalizar(col):
    return (
        col.fillna("")
        .astype(str)
        .apply(lambda x: unicodedata.normalize("NFKD", x))
        .str.encode("ascii", errors="ignore")
        .str.decode("utf-8")
        .str.upper()
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )

# =========================
# NORMALIZAÇÃO VENDAS
# =========================
vendas["Segmento Maq"] = normalizar(
    vendas["Segmento Maq"].astype(str)
)

vendas["Familia"] = normalizar(
    vendas["Familia"].astype(str)
)

vendas["Tipo Produto"] = normalizar(
    vendas["Tipo Produto"].astype(str)
)

vendas["Grupo Modelo"] = normalizar(
    vendas["Grupo Modelo"].astype(str)
)

vendas["Vendedor"] = normalizar(
    vendas["Vendedor"]
)

vendas["Calc dim De Para Familia 2"] = normalizar(
    vendas["Calc dim De Para Familia 2"].astype(str)
)

# =========================
# CLASSIFICAÇÃO PRODUTOS
# =========================
def classificar_produto(row):

    de_para = row["Calc dim De Para Familia 2"]
    segmento = row["Segmento Maq"]
    familia = row["Familia"]
    tipo = row["Tipo Produto"]
    grupo = row["Grupo Modelo"]

    # =====================
    # TRATOR
    # =====================
    if "TRATOR" in de_para:
        return "TRATOR"

    # =====================
    # VEÍCULOS OFF ROAD
    # =====================
    if "VEICULOS OFF ROAD" in segmento:
        return "VEICULOS OFF ROAD"

    # =====================
    # IMPLEMENTOS
    # =====================
    if "IMPLEMENTO" in familia:
        return "IMPLEMENTO"

    # =====================
    # USADOS
    # =====================
    if "USADO" in familia:
        return "USADOS"

    # =====================
    # EMPILHADEIRA
    # =====================
    if "EMPILHADEIRA" in familia:
        return "EMPILHADEIRA"

    # =====================
    # PLATAFORMA
    # =====================
    if "PLATAFORMA" in familia:
        return "PLATAFORMA"

    # =====================
    # DRONE
    # =====================
    if "DRONE" in tipo:
        return "DRONE"

    # =====================
    # RECOLHEDORA AUTOMOTRIZ
    # =====================
    if "RECOLHEDORA AUTOMOTRIZ" in tipo:
        return "RECOLHEDORA AUTOMOTRIZ"

    # =====================
    # CR
    # =====================
    if "MASTER CAFE" in grupo:
        return "CR"

    # =====================
    # 2 CR
    # =====================
    if "2 CR" in grupo:
        return "2 CR"

    # =====================
    # MASTER GRAOS
    # =====================
    if "MASTER GRAOS" in grupo:
        return "MASTER GRAOS"

    # =====================
    # PULVERIZADOR
    # =====================
    if "PULVERIZADOR" in grupo:
        return "PULVERIZADOR"

    # =====================
    # PLANTADEIRA
    # =====================
    if "PLANTADEIRA" in grupo:
        return "PLANTADEIRA"

    return None

# =========================
# APLICAR CLASSIFICAÇÃO
# =========================
vendas["PRODUTO_MATRIZ"] = vendas.apply(
    classificar_produto,
    axis=1
)

# =========================
# DATA VENDAS
# =========================
vendas["Calc Mes"] = (
    vendas["Calc Mes"]
    .astype(str)
    .str.strip()
)

vendas["MES"] = pd.to_numeric(
    vendas["Calc Mes"],
    errors="coerce"
)

vendas["Ano"] = (
    vendas["Ano"]
    .astype(str)
    .str.strip()
)

vendas["ANO"] = pd.to_numeric(
    vendas["Ano"],
    errors="coerce"
)

# =========================
# VALOR REALIZADO
# =========================
vendas["VALOR_REALIZADO"] = (
    vendas["Quantidade"]
    .astype(float)
)

mask_valor = (
    vendas["PRODUTO_MATRIZ"]
    .isin(
        [
            "IMPLEMENTO",
            "USADOS"
        ]
    )
)

vendas.loc[
    mask_valor,
    "VALOR_REALIZADO"
] = vendas.loc[
    mask_valor,
    "Vl NFVenda"
]

# =========================
# BASE REALIZADO
# =========================
realizado = (
    vendas[
        vendas["PRODUTO_MATRIZ"]
        .notna()
    ]
    .groupby(
        [
            "Vendedor",
            "PRODUTO_MATRIZ",
            "MES"
        ]
    )["VALOR_REALIZADO"]
    .sum()
    .reset_index()
)

realizado.columns = [
    "CONSULTOR",
    "PRODUTO",
    "MES",
    "REALIZADO"
]

# =========================
# DEBUG COLUNAS
# =========================
with tab4:

    st.subheader("CLASSIFICAÇÃO PRODUTOS")

    st.dataframe(
    vendas[
        [
            "Calc dim De Para Familia 2",
            "Segmento Maq",
            "Familia",
            "Tipo Produto",
            "Grupo Modelo",
            "PRODUTO_MATRIZ"
        ]
    ]
    .drop_duplicates()
    .sort_values("PRODUTO_MATRIZ"),
    use_container_width=True
    )

    st.subheader("DEBUG BASE VENDAS")

    st.write("Colunas encontradas:")

    st.write(
        list(vendas.columns)
    )

    st.write("Prévia da base:")

    st.dataframe(
        vendas.head(20),
        use_container_width=True
    )

    st.subheader("BASE REALIZADO")

    st.dataframe(
        realizado.sort_values(
            ["CONSULTOR", "PRODUTO", "MES"]
        ),
        use_container_width=True
    )

# =========================
# RENOMEAR COLUNAS
# =========================
opp = opp.rename(columns={
    "Vendedor (Conta) (Conta)": COL_VEND,
    "Conta": "Cliente",
    "Documento (BR: CPF/CNPJ) (Conta) (Conta)": COL_DOC,
    "Concessionária (Conta) (Conta)": COL_CONC
})

clientes = clientes.rename(columns={
    "Documento (BR: CPF/CNPJ)": COL_DOC,
    "Concessionária": COL_CONC,
    "CÓD": COL_MUN
})

# =========================
# PADRONIZAÇÃO
# =========================
clientes[COL_VEND] = normalizar(clientes[COL_VEND])
opp[COL_VEND] = normalizar(opp[COL_VEND])

territorio["NOME CRM"] = normalizar(
    territorio["NOME CRM"]
)

territorio["NOME BI"] = normalizar(
    territorio["NOME BI"]
)

territorio["Filial"] = normalizar(
    territorio["Filial"]
)

territorio["Região"] = normalizar(
    territorio["Região"]
)

territorio["Marca"] = normalizar(
    territorio["Marca"]
)

clientes[COL_DOC] = (
    clientes[COL_DOC]
    .astype(str)
    .str.strip()
)

opp[COL_DOC] = (
    opp[COL_DOC]
    .astype(str)
    .str.strip()
)

clientes[COL_CONC] = normalizar(
    clientes[COL_CONC]
)

opp[COL_CONC] = normalizar(
    opp[COL_CONC]
)

clientes[COL_MUN] = (
    clientes[COL_MUN]
    .astype(str)
    .str.strip()
)

# =========================
# CRUZAMENTO MUNICÍPIO
# Chave inclui vendedor para garantir que, quando o mesmo
# cliente está cadastrado para mais de um vendedor (com
# municípios potencialmente diferentes), o município
# resolvido seja o do vendedor da oportunidade.
# =========================
base_municipio = (
    clientes[
        [
            COL_DOC,
            COL_CONC,
            COL_VEND,
            COL_MUN
        ]
    ]
    .drop_duplicates(
        subset=[COL_DOC, COL_CONC, COL_VEND]
    )
)

opp = opp.merge(
    base_municipio,
    on=[COL_DOC, COL_CONC, COL_VEND],
    how="left"
)

# =========================
# DASHBOARD BASE
# =========================
clientes_vendedor = (
    clientes
    .groupby(COL_VEND)[COL_DOC]
    .nunique()
    .reset_index()
    .rename(columns={COL_DOC: "Clientes Cadastrados"})
)

dados_vendedor = (
    territorio[
        [
            "NOME CRM",
            "NOME BI",
            "Filial",
            "Região"
        ]
    ]
    .drop_duplicates(subset=["NOME CRM"])
    .rename(columns={
        "NOME CRM": COL_VEND
    })
)

opp_total = (
    opp
    .groupby(COL_VEND)
    .size()
    .reset_index(name="Total Oportunidades")
)

opp_ganhas = (
    opp[
        opp["Status"]
        .str.upper()
        .str.contains("GANH", na=False)
    ]
    .groupby(COL_VEND)
    .size()
    .reset_index(name="Oportunidades Ganhas")
)

opp_perdidas = (
    opp[
        opp["Status"]
        .str.upper()
        .str.contains("PERD", na=False)
    ]
    .groupby(COL_VEND)
    .size()
    .reset_index(name="Oportunidades Perdidas")
)

opp_abertas = (
    opp[
        ~opp["Status"]
        .str.upper()
        .str.contains("GANH|PERD", na=False)
    ]
    .groupby(COL_VEND)
    .size()
    .reset_index(name="Oportunidades Em Aberto")
)

dashboard = (
    clientes_vendedor
    .merge(opp_total, on=COL_VEND, how="left")
    .merge(opp_ganhas, on=COL_VEND, how="left")
    .merge(opp_perdidas, on=COL_VEND, how="left")
    .merge(opp_abertas, on=COL_VEND, how="left")
    .merge(dados_vendedor, on=COL_VEND, how="left")
)

# =========================
# TMOEA
# =========================
opp["Data de Criação"] = pd.to_datetime(
    opp["Data de Criação"],
    errors="coerce"
)

opp_aberto_tmo = opp[
    ~opp["Status"]
    .str.upper()
    .str.contains("GANH|PERD", na=False)
].copy()

opp_aberto_tmo["Dias Em Aberto"] = (
    pd.Timestamp.today()
    - opp_aberto_tmo["Data de Criação"]
).dt.days

tmoea = (
    opp_aberto_tmo
    .groupby(COL_VEND)["Dias Em Aberto"]
    .mean()
    .reset_index()
)

dashboard = dashboard.merge(
    tmoea,
    on=COL_VEND,
    how="left"
)

dashboard["TMOEA"] = (
    dashboard["Dias Em Aberto"]
    .fillna(0)
    .round(0)
)

dashboard.drop(
    columns=["Dias Em Aberto"],
    inplace=True
)

# =========================
# SIDEBAR
# =========================
st.sidebar.title("Filtros")

regiao = st.sidebar.selectbox(
    "Região",
    ["Todas"] + sorted(
        dashboard["Região"]
        .dropna()
        .unique()
    )
)

filial = st.sidebar.selectbox(
    "Filial",
    ["Todas"] + sorted(
        dashboard["Filial"]
        .dropna()
        .unique()
    )
)

# base filtrada até filial/região
base_filtro_vendedor = dashboard.copy()

if regiao != "Todas":
    base_filtro_vendedor = base_filtro_vendedor[
        base_filtro_vendedor["Região"] == regiao
    ]

if filial != "Todas":
    base_filtro_vendedor = base_filtro_vendedor[
        base_filtro_vendedor["Filial"] == filial
    ]

vendedor = st.sidebar.selectbox(
    "Vendedor",
    ["Todos"] + sorted(
        base_filtro_vendedor[COL_VEND]
        .dropna()
        .unique()
    )
)

df_base = dashboard.copy()

if regiao != "Todas":
    df_base = df_base[
        df_base["Região"] == regiao
    ]

if filial != "Todas":
    df_base = df_base[
        df_base["Filial"] == filial
    ]

if vendedor != "Todos":
    df_base = df_base[
        df_base[COL_VEND] == vendedor
    ]

# =========================
# FUNIL STATE
# =========================
if "filtro_funil" not in st.session_state:
    st.session_state["filtro_funil"] = "Em Aberto"

def set_filtro(v):
    st.session_state["filtro_funil"] = v
    st.rerun()

filtro_funil = st.session_state["filtro_funil"]

# =========================
# FUNIL DATA
# =========================
if filtro_funil == "Todas":

    df_funil = opp.copy()

elif filtro_funil == "Ganhas":

    df_funil = opp[
        opp["Status"]
        .str.upper()
        .str.contains("GANH", na=False)
    ]

elif filtro_funil == "Perdidas":

    df_funil = opp[
        opp["Status"]
        .str.upper()
        .str.contains("PERD", na=False)
    ]

else:

    df_funil = opp[
        ~opp["Status"]
        .str.upper()
        .str.contains("GANH|PERD", na=False)
    ]

df_funil = df_funil.merge(
    df_base[[COL_VEND]],
    on=COL_VEND,
    how="inner"
)

# =========================
# KPIs
# =========================
def format_br(v):
    return f"{v:,.0f}".replace(",", ".")

def card(t, v):

    st.markdown(f"""
    <div style="
        padding:16px;
        border-radius:10px;
        border:1px solid #eee;
        background:#fafafa;
        text-align:center">

    <div style="
        font-size:13px;
        color:#666">
        {t}
    </div>

    <div style="
        font-size:22px;
        font-weight:700">
        {v}
    </div>

    </div>
    """, unsafe_allow_html=True)

# =========================
# TAB 1 - VENDEDOR
# =========================
with tab1:

    col1, col2 = st.columns(2)

    with col1:
        card(
            "Clientes (Total)",
            format_br(
                df_base["Clientes Cadastrados"].sum()
            )
        )

    with col2:
        card(
            "Oportunidades (Total)",
            format_br(
                df_base["Total Oportunidades"].sum()
            )
        )

    col3, col4, col5 = st.columns(3)

    with col3:
        card(
            "Clientes (Funil)",
            format_br(
                df_funil["Cliente"].nunique()
            )
        )

    with col4:
        card(
            f"Oportunidades ({filtro_funil})",
            format_br(len(df_funil))
        )

    with col5:
        card(
            "TMOEA",
            f"{df_base['TMOEA'].mean():.0f} dias"
        )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.button(
            "📊 Todas",
            on_click=set_filtro,
            args=("Todas",),
            type="primary" if filtro_funil == "Todas" else "secondary",
            use_container_width=True
        )

    with c2:
        st.button(
            "✅ Ganhas",
            on_click=set_filtro,
            args=("Ganhas",),
            type="primary" if filtro_funil == "Ganhas" else "secondary",
            use_container_width=True
        )

    with c3:
        st.button(
            "❌ Perdidas",
            on_click=set_filtro,
            args=("Perdidas",),
            type="primary" if filtro_funil == "Perdidas" else "secondary",
            use_container_width=True
        )

    with c4:
        st.button(
            "🟡 Em Aberto",
            on_click=set_filtro,
            args=("Em Aberto",),
            type="primary" if filtro_funil == "Em Aberto" else "secondary",
            use_container_width=True
        )

    if filtro_funil == "Todas":
        col = "Total Oportunidades"

    elif filtro_funil == "Ganhas":
        col = "Oportunidades Ganhas"

    elif filtro_funil == "Perdidas":
        col = "Oportunidades Perdidas"

    else:
        col = "Oportunidades Em Aberto"

    grafico = df_base[
        [COL_VEND, col]
    ]

    chart = (
        alt.Chart(grafico)
        .mark_bar()
        .encode(
            x=alt.X(f"{COL_VEND}:N", sort="-y"),
            y=alt.Y(f"{col}:Q"),
            tooltip=[COL_VEND, col]
        )
    )

    text = (
        alt.Chart(grafico)
        .mark_text(
            dy=15,
            color="white"
        )
        .encode(
            x=f"{COL_VEND}:N",
            y=f"{col}:Q",
            text=f"{col}:Q"
        )
    )

    st.altair_chart(
        chart + text,
        use_container_width=True
    )

    # =========================
    # TABELA RESUMO VENDEDOR
    # =========================
    tabela_vendedor = df_base.drop(
        columns=["CÓD_ÁREA"],
        errors="ignore"
    ).copy()

    tabela_vendedor = tabela_vendedor.rename(columns={
        "Clientes Cadastrados": "Clientes",
        "Total Oportunidades": "Oportunidades",
        "Oportunidades Ganhas": "Ganhas",
        "Oportunidades Perdidas": "Perdidas",
        "Oportunidades Em Aberto": "Em Aberto"
    })

    st.dataframe(
        tabela_vendedor,
        use_container_width=True,
        hide_index=True,
        height=500
    )

    # =========================
    # TABELA DESCRITIVO OPORTUNIDADES
    # =========================
    st.markdown("### Descritivo das Oportunidades")

    df_detail = df_funil.copy()

    # Normaliza CD_MUN e marca linhas sem município
    df_detail["CD_MUN"] = (
        df_detail["CD_MUN"]
        .astype(str)
        .str.strip()
    )
    df_detail.loc[
        df_detail["CD_MUN"].isin(["nan", "None", ""]),
        "CD_MUN"
    ] = None

    # Flag que viaja com o DataFrame através dos merges
    df_detail["_usa_fallback"] = df_detail["CD_MUN"].isna()

    # Fallback: quando o vendedor da oportunidade não bate com nenhum
    # cadastro ativo do cliente, busca o município pelo documento apenas
    base_mun_doc = (
        clientes[[COL_DOC, COL_MUN]]
        .drop_duplicates(subset=[COL_DOC])
        .copy()
    )
    base_mun_doc[COL_MUN] = (
        base_mun_doc[COL_MUN]
        .astype(str)
        .str.strip()
    )

    df_detail = df_detail.merge(
        base_mun_doc.rename(columns={COL_MUN: "CD_MUN_fallback"}),
        on=COL_DOC,
        how="left"
    )

    df_detail.loc[
        df_detail["_usa_fallback"],
        "CD_MUN"
    ] = df_detail.loc[
        df_detail["_usa_fallback"],
        "CD_MUN_fallback"
    ]

    # Nomes de município
    mun_nome = (
        gdf_mun[["CD_MUN", "NM_MUN", "SIGLA_UF"]]
        .copy()
    )
    mun_nome["CD_MUN"] = (
        mun_nome["CD_MUN"]
        .astype(str)
        .str.strip()
    )

    df_detail = df_detail.merge(
        mun_nome,
        on="CD_MUN",
        how="left"
    )

    # Filial/Região pelo vendedor da oportunidade (caminho primário)
    df_detail = df_detail.merge(
        dados_vendedor[[COL_VEND, "Filial", "Região"]],
        on=COL_VEND,
        how="left"
    )

    # Lookup do vendedor ativo por município (usado no fallback)
    territorio_por_mun = (
        territorio[["Código IBGE", "NOME CRM", "Filial", "Região"]]
        .drop_duplicates(subset=["Código IBGE"])
        .copy()
    )
    territorio_por_mun["Código IBGE"] = (
        territorio_por_mun["Código IBGE"]
        .astype(str)
        .str.strip()
    )
    territorio_por_mun = territorio_por_mun.rename(columns={
        "Código IBGE": "CD_MUN",
        "NOME CRM": "Vendedor_Ativo",
        "Filial": "Filial_Ativo",
        "Região": "Região_Ativo"
    })

    df_detail = df_detail.merge(
        territorio_por_mun,
        on="CD_MUN",
        how="left"
    )

    # Para linhas de fallback: sobrescreve vendedor, filial e região
    # com os dados do vendedor ativo responsável pelo município
    fb = df_detail["_usa_fallback"]
    df_detail.loc[fb, COL_VEND] = df_detail.loc[fb, "Vendedor_Ativo"]
    df_detail.loc[fb, "Filial"] = df_detail.loc[fb, "Filial_Ativo"]
    df_detail.loc[fb, "Região"] = df_detail.loc[fb, "Região_Ativo"]

    # Dias desde a criação
    today = pd.Timestamp.today()
    df_detail["Dias desde Criação"] = (
        today - df_detail["Data de Criação"]
    ).dt.days

    # Valor Total formatado em R$ com separador de milhar
    df_detail["Valor Total"] = df_detail["Valor Total"].apply(
        lambda x: (
            "R$ " + f"{round(x):,}".replace(",", ".")
            if pd.notna(x) else ""
        )
    )

    tabela_opp = (
        df_detail[
            [
                "Cliente",
                COL_DOC,
                "NM_MUN",
                "SIGLA_UF",
                COL_VEND,
                "Filial",
                "Região",
                "Valor Total",
                "Dias desde Criação",
            ]
        ]
        .rename(columns={
            COL_DOC: "Documento",
            "NM_MUN": "Município",
            "SIGLA_UF": "UF",
            COL_VEND: "Vendedor"
        })
        .sort_values(
            "Dias desde Criação",
            ascending=True
        )
    )

    st.dataframe(
        tabela_opp,
        use_container_width=True,
        hide_index=True
    )

    # =========================
    # TAB 2 - MAPA MUNICÍPIO
    # =========================
    with tab2:

        st.subheader("Mapa de Oportunidades por Município")

        # =========================
        # MUNICÍPIOS / FILIAL / REGIÃO
        # =========================
        territorio["Código IBGE"] = (
            territorio["Código IBGE"]
            .astype(str)
            .str.strip()
        )

        base_municipios = (
            territorio[
                [
                    "Código IBGE",
                    "Filial",
                    "Região"
                ]
            ]
            .drop_duplicates(subset=["Código IBGE"])
            .rename(columns={
                "Código IBGE": "CD_MUN"
            })
        )

        base_municipios["Filial"] = normalizar(
            base_municipios["Filial"].astype(str)
        )

        base_municipios["Região"] = normalizar(
            base_municipios["Região"].astype(str)
        )

        # =========================
        # FILTRAR PELOS FILTROS LATERAIS
        # =========================
        vendedores_filtrados = (
            df_base[COL_VEND]
            .dropna()
            .unique()
        )

        opp_filtrada = opp[
            opp[COL_VEND].isin(vendedores_filtrados)
        ].copy()

        # =========================
        # OPORTUNIDADES TOTAL
        # =========================
        opp_total_mun = (
            opp_filtrada
            .groupby("CD_MUN")
            .size()
            .reset_index(name="Oportunidades Total")
        )

        # =========================
        # OPORTUNIDADES EM ABERTO
        # =========================
        opp_aberto = opp_filtrada[
            ~opp_filtrada["Status"]
            .str.upper()
            .str.contains("GANH|PERD", na=False)
        ]

        opp_aberto_mun = (
            opp_aberto
            .groupby("CD_MUN")
            .size()
            .reset_index(name="Oportunidades Em Aberto")
        )

        # =========================
        # MAPA BASE
        # =========================
        mapa = gdf_mun.merge(
            opp_total_mun,
            on="CD_MUN",
            how="left"
        )

        mapa = mapa.merge(
            opp_aberto_mun,
            on="CD_MUN",
            how="left"
        )

        mapa = mapa.merge(
            base_municipios,
            on="CD_MUN",
            how="left"
        )

        mapa["Oportunidades Total"] = (
            mapa["Oportunidades Total"]
            .fillna(0)
        )

        mapa["Oportunidades Em Aberto"] = (
            mapa["Oportunidades Em Aberto"]
            .fillna(0)
        )

        # =========================
        # TABELA
        # =========================
        mapa_tabela = mapa[
            mapa["Oportunidades Total"] > 0
        ].copy()

        mapa_tabela = mapa_tabela.drop_duplicates(
            subset=["CD_MUN"]
        )

        # =========================
        # CONTROLES DO MAPA
        # =========================
        col_toggle1, col_toggle2 = st.columns([1, 1])

        with col_toggle1:

            mostrar_dados = st.toggle(
                "Mostrar dados territoriais no mapa",
                value=False
            )

        with col_toggle2:

            somente_abertas = st.radio(
                "Municípios exibidos",
                options=[
                    "Todos com oportunidades",
                    "Somente em aberto"
                ],
                horizontal=True
            )

        # =========================
        # MAPA INTERATIVO
        # =========================
        import folium
        from streamlit_folium import st_folium

        mapa_geo = mapa.to_crs(epsg=4326)

        # =========================
        # FILTRO DE MUNICÍPIOS
        # =========================
        if somente_abertas == "Somente em aberto":

            mapa_geo = mapa_geo[
                mapa_geo["Oportunidades Em Aberto"] > 0
            ].copy()

        else:

            mapa_geo = mapa_geo[
                mapa_geo["Oportunidades Total"] > 0
            ].copy()

        # mapa leve
        m = folium.Map(
            location=[-15, -55],
            zoom_start=4,
            tiles="cartodbpositron"
        )
        # =========================
        # MOSTRAR MUNICÍPIOS
        # =========================
        if mostrar_dados:

            for _, row in mapa_geo.iterrows():

                tooltip = f"""
                <b>Município:</b> {row['NM_MUN']}<br>
                <b>UF:</b> {row['SIGLA_UF']}<br>
                <b>Filial:</b> {row['Filial']}<br>
                <b>Região:</b> {row['Região']}<br>
                <b>Oportunidades Total:</b> {int(row['Oportunidades Total'])}<br>
                <b>Oportunidades Em Aberto:</b> {int(row['Oportunidades Em Aberto'])}
                """

                folium.GeoJson(
                    row["geometry"],
                    style_function=lambda x: {
                        "fillColor": "#1565C0",
                        "color": "#0D47A1",
                        "weight": 2,
                        "fillOpacity": 0.35,
                    },
                    tooltip=tooltip
                ).add_to(m)

        # =========================
        # EXIBIR MAPA
        # =========================
        st_folium(
            m,
            width=None,
            height=650
        )

        # =========================
        # TABELA FINAL
        # =========================
        tabela_municipios = mapa_tabela[
            [
                "NM_MUN",
                "SIGLA_UF",
                "Filial",
                "Região",
                "Oportunidades Total",
                "Oportunidades Em Aberto"
            ]
        ].copy()

        tabela_municipios.columns = [
            "Município",
            "UF",
            "Filial",
            "Região",
            "Oportunidades Total",
            "Oportunidades Em Aberto"
        ]

        tabela_municipios = tabela_municipios.sort_values(
            "Oportunidades Total",
            ascending=False
        )

        st.dataframe(
            tabela_municipios,
            use_container_width=True,
            hide_index=True
        )

        # =========================
        # DESCRITIVO OPORTUNIDADES
        # =========================
        st.markdown("### Descritivo das Oportunidades")

        # Respeita o rádio "somente em aberto"
        if somente_abertas == "Somente em aberto":
            df_detail_mun = opp_filtrada[
                ~opp_filtrada["Status"]
                .str.upper()
                .str.contains("GANH|PERD", na=False)
            ].copy()
        else:
            df_detail_mun = opp_filtrada.copy()

        total_desc_mun = len(df_detail_mun)
        st.markdown(
            f"<span style='font-size:15px;'>Total de oportunidades: <b>{total_desc_mun:,}</b></span>".replace(",", "."),
            unsafe_allow_html=True
        )

        # Normaliza CD_MUN e marca linhas sem município
        df_detail_mun["CD_MUN"] = (
            df_detail_mun["CD_MUN"].astype(str).str.strip()
        )
        df_detail_mun.loc[
            df_detail_mun["CD_MUN"].isin(["nan", "None", ""]),
            "CD_MUN"
        ] = None
        df_detail_mun["_usa_fallback"] = df_detail_mun["CD_MUN"].isna()

        # Fallback: busca município pelo documento quando o vendedor não bate
        base_mun_doc2 = (
            clientes[[COL_DOC, COL_MUN]]
            .drop_duplicates(subset=[COL_DOC])
            .copy()
        )
        base_mun_doc2[COL_MUN] = (
            base_mun_doc2[COL_MUN].astype(str).str.strip()
        )
        df_detail_mun = df_detail_mun.merge(
            base_mun_doc2.rename(columns={COL_MUN: "CD_MUN_fallback"}),
            on=COL_DOC,
            how="left"
        )
        df_detail_mun.loc[
            df_detail_mun["_usa_fallback"],
            "CD_MUN"
        ] = df_detail_mun.loc[
            df_detail_mun["_usa_fallback"],
            "CD_MUN_fallback"
        ]

        # Nomes de município
        mun_nome2 = gdf_mun[["CD_MUN", "NM_MUN", "SIGLA_UF"]].copy()
        mun_nome2["CD_MUN"] = mun_nome2["CD_MUN"].astype(str).str.strip()
        df_detail_mun = df_detail_mun.merge(mun_nome2, on="CD_MUN", how="left")

        # Filial/Região pelo vendedor da oportunidade (caminho primário)
        df_detail_mun = df_detail_mun.merge(
            dados_vendedor[[COL_VEND, "Filial", "Região"]],
            on=COL_VEND,
            how="left"
        )

        # Lookup do vendedor ativo por município (fallback)
        territorio_por_mun2 = (
            territorio[["Código IBGE", "NOME CRM", "Filial", "Região"]]
            .drop_duplicates(subset=["Código IBGE"])
            .copy()
        )
        territorio_por_mun2["Código IBGE"] = (
            territorio_por_mun2["Código IBGE"].astype(str).str.strip()
        )
        territorio_por_mun2 = territorio_por_mun2.rename(columns={
            "Código IBGE": "CD_MUN",
            "NOME CRM": "Vendedor_Ativo",
            "Filial": "Filial_Ativo",
            "Região": "Região_Ativo"
        })
        df_detail_mun = df_detail_mun.merge(
            territorio_por_mun2, on="CD_MUN", how="left"
        )

        # Sobrescreve vendedor/filial/região para linhas de fallback
        fb2 = df_detail_mun["_usa_fallback"]
        df_detail_mun.loc[fb2, COL_VEND] = df_detail_mun.loc[fb2, "Vendedor_Ativo"]
        df_detail_mun.loc[fb2, "Filial"]  = df_detail_mun.loc[fb2, "Filial_Ativo"]
        df_detail_mun.loc[fb2, "Região"]  = df_detail_mun.loc[fb2, "Região_Ativo"]

        # Dias desde a criação
        df_detail_mun["Dias desde Criação"] = (
            pd.Timestamp.today() - df_detail_mun["Data de Criação"]
        ).dt.days

        # Valor Total em R$
        df_detail_mun["Valor Total"] = df_detail_mun["Valor Total"].apply(
            lambda x: (
                "R$ " + f"{round(x):,}".replace(",", ".")
                if pd.notna(x) else ""
            )
        )

        tabela_desc_mun = (
            df_detail_mun[
                [
                    "Data de Criação",
                    "Cliente",
                    COL_DOC,
                    "NM_MUN",
                    "SIGLA_UF",
                    COL_VEND,
                    "Filial",
                    "Região",
                    "Valor Total",
                    "Dias desde Criação",
                    "Criada Por"
                ]
            ]
            .rename(columns={
                COL_DOC: "Documento",
                "NM_MUN": "Município",
                "SIGLA_UF": "UF",
                COL_VEND: "Vendedor"
            })
            .sort_values("Data de Criação", ascending=False)
        )

        st.dataframe(
            tabela_desc_mun,
            use_container_width=True,
            hide_index=True
        )

# =========================
# TAB 3 - MATRIZ
# =========================
with tab3:

    st.subheader("Matriz de Performance")

    # =====================================================
    # BASE METAS
    # =====================================================
    metas = pd.read_excel(
        "dados/metas.xlsx"
    )

    # =====================================================
    # NORMALIZAÇÃO
    # =====================================================
    metas["CONSULTOR"] = normalizar(
        metas["CONSULTOR"]
    )

    metas["PRODUTO"] = normalizar(
        metas["PRODUTO"]
    )

    metas["STATUS"] = normalizar(
        metas["STATUS"]
    )

    # =====================================================
    # SOMENTE ATIVOS
    # =====================================================
    metas = metas[
        metas["STATUS"]
        .str.contains("ATIVO", na=False)
    ].copy()

    # =====================================================
    # BASE TERRITÓRIO
    # =====================================================
    base_territorio_matriz = (
        territorio[
            [
                "NOME BI",
                "Filial",
                "Região"
            ]
        ]
        .drop_duplicates(subset=["NOME BI"])
    )

    # =====================================================
    # CRUZAMENTO
    # =====================================================
    matriz = metas.merge(
        base_territorio_matriz,
        left_on="CONSULTOR",
        right_on="NOME BI",
        how="left"
    )

    # =====================================================
    # FILTROS GERAIS
    # =====================================================
    if regiao != "Todas":

        matriz = matriz[
            matriz["Região"] == regiao
        ]

    if filial != "Todas":

        matriz = matriz[
            matriz["Filial"] == filial
        ]

    # O sidebar usa NOME CRM; a base de metas usa NOME BI.
    # A base território relaciona os dois — fazemos o mapeamento aqui.
    if vendedor != "Todos":

        mapa_crm_bi = (
            territorio[["NOME CRM", "NOME BI"]]
            .drop_duplicates(subset=["NOME CRM"])
        )

        match_bi = mapa_crm_bi[
            mapa_crm_bi["NOME CRM"] == vendedor
        ]

        vendedor_bi = (
            match_bi["NOME BI"].iloc[0]
            if not match_bi.empty
            else vendedor
        )

        matriz = matriz[
            matriz["CONSULTOR"] == vendedor_bi
        ]

    else:
        vendedor_bi = "Todos"

    # =====================================================
    # SELECT CONSULTOR
    # =====================================================
    lista_consultores = sorted(
        matriz["CONSULTOR"]
        .dropna()
        .unique()
        .tolist()
    )

    if not lista_consultores:
        st.warning(
            "Nenhum consultor ativo encontrado para os filtros selecionados."
        )
        st.stop()

    # Pré-seleciona usando o nome BI (que é como aparece na lista)
    default_idx = 0
    if vendedor_bi != "Todos" and vendedor_bi in lista_consultores:
        default_idx = lista_consultores.index(vendedor_bi)

    consultor_matriz = st.selectbox(
        "Consultor",
        lista_consultores,
        index=default_idx
    )

    matriz_consultor = matriz[
        matriz["CONSULTOR"] == consultor_matriz
    ].copy()

    # =========================
    # ACUMULADORES DE PONTUAÇÃO
    # =========================

    total_p_q1 = 0
    total_p_q2 = 0
    total_p_q3 = 0
    total_p_q4 = 0

    real_q1_total = 0
    real_q2_total = 0
    real_q3_total = 0
    real_q4_total = 0

    meta_q1_total = 0
    meta_q2_total = 0
    meta_q3_total = 0
    meta_q4_total = 0

    n_produtos = len(matriz_consultor)

    # Inicializado aqui para evitar NameError no bloco else
    # (o valor correto é recalculado após o loop de produtos)
    media_pontuacao = 0

    # =========================
    # STATUS CONSULTOR
    # =========================
    if len(matriz_consultor) > 0:

        status_consultor = "ATIVO"

        filial_consultor = (
            matriz_consultor["Filial"]
            .dropna()
            .iloc[0]
            if matriz_consultor["Filial"].dropna().shape[0] > 0
            else "-"
        )

        regiao_consultor = (
            matriz_consultor["Região"]
            .dropna()
            .iloc[0]
            if matriz_consultor["Região"].dropna().shape[0] > 0
            else "-"
        )

    else:

        status_consultor = "INATIVO"

        filial_consultor = "-"
        regiao_consultor = "-"

        # =====================================================
        # HEADER EXECUTIVO
        # =====================================================
        st.markdown("---")

        c1, c2, c3, c4 = st.columns(4)

        # =====================================================
        # CARD CONSULTOR
        # =====================================================
        with c1:

            st.markdown(f"""
            <div style='
                background:#fafafa;
                border:1px solid #e5e7eb;
                border-radius:12px;
                padding:18px;
                height:120px;
            '>

                <div style='
                    font-size:22px;
                    font-weight:700;
                    margin-bottom:12px;
                '>
                    {consultor_matriz}
                </div>

                <div style='font-size:14px;'>
                    <b>Filial:</b> {filial_consultor}
                </div>

                <div style='font-size:14px; margin-top:4px;'>
                    <b>Região:</b> {regiao_consultor}
                </div>

            </div>
            """, unsafe_allow_html=True)

        # =====================================================
        # CARD PONTUAÇÃO
        # =====================================================
        with c2:

            st.markdown(f"""
            <div style='
                background:#fafafa;
                border:1px solid #e5e7eb;
                border-radius:12px;
                padding:18px;
                height:120px;
                text-align:center;
            '>

                <div style='
                    font-size:14px;
                    color:#666;
                '>
                    Pontuação Final
                </div>

                <div style='font-size:34px;font-weight:700;margin-top:12px;'>
                    {media_pontuacao:.1f}
                </div>

            </div>
            """, unsafe_allow_html=True)

        # =====================================================
        # CARD ELEGIBILIDADE
        # =====================================================
        with c3:

            st.markdown("""
            <div style='
                background:#E3F2FD;
                border:1px solid #BBDEFB;
                border-radius:12px;
                padding:18px;
                height:120px;
                text-align:center;
            '>

                <div style='
                    font-size:14px;
                    color:#666;
                '>
                    Elegibilidade
                </div>

                <div style='
                    font-size:30px;
                    font-weight:700;
                    margin-top:12px;
                '>
                    SIM
                </div>

            </div>
            """, unsafe_allow_html=True)

        # =====================================================
        # CARD STATUS
        # =====================================================
        with c4:

            cor_status = (
                "#2E7D32"
                if status_consultor == "ATIVO"
                else "#C62828"
            )

            st.markdown(f"""
            <div style='
                background:#fafafa;
                border:1px solid #e5e7eb;
                border-radius:12px;
                padding:18px;
                height:120px;
                text-align:center;
            '>

                <div style='
                    font-size:14px;
                    color:#666;
                '>
                    Status Consultor
                </div>

                <div style='
                    font-size:28px;
                    font-weight:700;
                    color:{cor_status};
                    margin-top:12px;
                '>
                    {status_consultor}
                </div>

            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

    # =====================================================
    # RESUMO TRIMESTRAL — posição fixada aqui na UI,
    # métricas preenchidas após o loop de produtos
    # =====================================================
    col_q1, col_q2, col_q3, col_q4, col_qf = st.columns(5)

    # =========================
    # FUNÇÃO REALIZADO
    # =========================
    def buscar_realizado(
        consultor,
        produto,
        mes
    ):

        filtro = realizado[
            (realizado["CONSULTOR"] == consultor)
            &
            (realizado["PRODUTO"] == produto)
            &
            (realizado["MES"] == mes)
        ]

        if len(filtro) == 0:
            return 0

        return filtro["REALIZADO"].sum()



    # =====================================================
    # LOOP PRODUTOS
    # =====================================================
    pontuacao_produtos = []
    for _, row in matriz_consultor.iterrows():

        # =========================
        # PERCENTUAL POR TRIMESTRE
        # =========================

        produto = row["PRODUTO"]

        # =================================================
        # VALORES
        # =================================================
        jan = row["JAN"]
        fev = row["FEV"]
        mar = row["MAR"]
        abr = row["ABR"]
        mai = row["MAI"]
        jun = row["JUN"]
        jul = row["JUL"]
        ago = row["AGO"]
        setm = row["SET"]
        out = row["OUT"]
        nov = row["NOV"]
        dez = row["DEZ"]

        total_meta = row["TOTAL"]

        # =================================================
        # REALIZADO
        # =================================================
        consultor = row["CONSULTOR"]

        r_jan = buscar_realizado(
            consultor,
            produto,
            1
        )

        r_fev = buscar_realizado(
            consultor,
            produto,
            2
        )

        r_mar = buscar_realizado(
            consultor,
            produto,
            3
        )

        r_abr = buscar_realizado(
            consultor,
            produto,
            4
        )

        r_mai = buscar_realizado(
            consultor,
            produto,
            5
        )

        r_jun = buscar_realizado(
            consultor,
            produto,
            6
        )

        r_jul = buscar_realizado(
            consultor,
            produto,
            7
        )

        r_ago = buscar_realizado(
            consultor,
            produto,
            8
        )

        r_set = buscar_realizado(
            consultor,
            produto,
            9
        )

        r_out = buscar_realizado(
            consultor,
            produto,
            10
        )

        r_nov = buscar_realizado(
            consultor,
            produto,
            11
        )

        r_dez = buscar_realizado(
            consultor,
            produto,
            12
        )

        # =================================================
        # TRIMESTRES
        # =================================================
        meta_q1 = jan + fev + mar
        meta_q2 = abr + mai + jun
        meta_q3 = jul + ago + setm
        meta_q4 = out + nov + dez

        real_q1 = r_jan + r_fev + r_mar
        real_q2 = r_abr + r_mai + r_jun
        real_q3 = r_jul + r_ago + r_set
        real_q4 = r_out + r_nov + r_dez

        real_q1_total += real_q1
        real_q2_total += real_q2
        real_q3_total += real_q3
        real_q4_total += real_q4

        meta_q1_total += meta_q1
        meta_q2_total += meta_q2
        meta_q3_total += meta_q3
        meta_q4_total += meta_q4

        # =================================================
        # DIFERENÇAS
        # =================================================
        dif_total = (
            real_q1
            + real_q2
            + real_q3
            + real_q4
        ) - total_meta

        # =================================================
        # EXPANDER
        # =================================================
        with st.expander(f"{produto}"):

            st.markdown(f"""
            ### {produto}
            """)

            # Formatting helpers para este produto
            is_monetary = produto in ["IMPLEMENTO", "USADOS"]

            if is_monetary:
                fmt_fn = lambda x: (
                    "R$ " + f"{round(x):,}".replace(",", ".")
                    if pd.notna(x) else ""
                )
            else:
                fmt_fn = lambda x: f"{x:.0f}" if pd.notna(x) else ""

            def highlight_tri(col):
                if col.name in ["1 TRI", "2 TRI", "3 TRI", "4 TRI"]:
                    return [
                        "background-color: #d6d6d6; color: black; font-weight: bold"
                    ] * len(col)
                return [""] * len(col)

            _cols17 = [
                "Jan", "Fev", "Mar", "1 TRI",
                "Abr", "Mai", "Jun", "2 TRI",
                "Jul", "Ago", "Set", "3 TRI",
                "Out", "Nov", "Dez", "4 TRI", "TOTAL"
            ]
            col_cfg_17 = {
                c: st.column_config.TextColumn(c, width="small")
                for c in _cols17
            }

            # =============================================
            # META
            # =============================================
            st.markdown("#### Meta")

            meta_df = pd.DataFrame({
                "Jan": [jan],
                "Fev": [fev],
                "Mar": [mar],
                "1 TRI": [meta_q1],
                "Abr": [abr],
                "Mai": [mai],
                "Jun": [jun],
                "2 TRI": [meta_q2],
                "Jul": [jul],
                "Ago": [ago],
                "Set": [setm],
                "3 TRI": [meta_q3],
                "Out": [out],
                "Nov": [nov],
                "Dez": [dez],
                "4 TRI": [meta_q4],
                "TOTAL": [total_meta]
            })

            st.dataframe(
                meta_df.style
                .format(fmt_fn)
                .apply(highlight_tri, axis=0),
                use_container_width=True,
                hide_index=True,
                column_config=col_cfg_17
            )

            # =============================================
            # REALIZADO
            # =============================================
            st.markdown("#### Realizado")

            realizado_df = pd.DataFrame({
                "Jan": [r_jan],
                "Fev": [r_fev],
                "Mar": [r_mar],
                "1 TRI": [real_q1],
                "Abr": [r_abr],
                "Mai": [r_mai],
                "Jun": [r_jun],
                "2 TRI": [real_q2],
                "Jul": [r_jul],
                "Ago": [r_ago],
                "Set": [r_set],
                "3 TRI": [real_q3],
                "Out": [r_out],
                "Nov": [r_nov],
                "Dez": [r_dez],
                "4 TRI": [real_q4],
                "TOTAL": [
                    real_q1
                    + real_q2
                    + real_q3
                    + real_q4
                ]
            })

            st.dataframe(
                realizado_df.style
                .format(fmt_fn)
                .apply(highlight_tri, axis=0),
                use_container_width=True,
                hide_index=True,
                column_config=col_cfg_17
            )

            # =============================================
            # DIFERENÇA
            # =============================================
            st.markdown("#### Diferença")

            # DIFERENÇA (corrigido)
            diferenca = realizado_df.iloc[0].subtract(meta_df.iloc[0], fill_value=0)

            diferenca_df = diferenca.to_frame().T.reset_index(drop=True)

            st.dataframe(
                diferenca_df.style
                .format(fmt_fn)
                .apply(highlight_tri, axis=0),
                use_container_width=True,
                hide_index=True,
                column_config=col_cfg_17
            )

            # =========================
            # FUNÇÃO DE PONTUAÇÃO
            # =========================
            def calc_ponto(real, meta):
                real = 0 if pd.isna(real) else real
                meta = 0 if pd.isna(meta) else meta
                return 10 if meta > 0 and real >= meta else 0

            # =========================
            # PONTUAÇÃO POR TRIMESTRE
            # =========================
            p_q1 = calc_ponto(real_q1, meta_q1)
            p_q2 = calc_ponto(real_q2, meta_q2)
            p_q3 = calc_ponto(real_q3, meta_q3)
            p_q4 = calc_ponto(real_q4, meta_q4)

            total_p_q1 += p_q1
            total_p_q2 += p_q2
            total_p_q3 += p_q3
            total_p_q4 += p_q4

            pontuacao_total_produto = p_q1 + p_q2 + p_q3 + p_q4

            pontuacao_produtos.append({
                "produto": produto,
                "pontuacao": pontuacao_total_produto
            })

            pontos = {
                "Q1": p_q1,
                "Q2": p_q2,
                "Q3": p_q3,
                "Q4": p_q4
            }

            pontos_total = next((pontos[q] for q in ["Q4","Q3","Q2","Q1"] if pontos[q] is not None), 0)

            score_df = pd.DataFrame({
                "Q1": [p_q1],
                "Q2": [p_q2],
                "Q3": [p_q3],
                "Q4": [p_q4],
                "TOTAL": [pontos_total]
            })

            st.markdown("### Pontuação por Trimestre")

            # Proporção 4:4:4:4:1 = 17 partes, igual às 17 colunas
            # das tabelas acima — Q1 alinha com Jan+Fev+Mar+1TRI
            _sc = st.columns([4, 4, 4, 4, 1])
            for _col, _lbl, _val in zip(
                _sc,
                ["Q1", "Q2", "Q3", "Q4", "TOTAL"],
                [p_q1, p_q2, p_q3, p_q4, pontos_total]
            ):
                with _col:
                    st.metric(_lbl, _val)
          
    # =====================================================
    # PONTUAÇÃO PONDERADA POR TRIMESTRE (calculada pós-loop)
    # =====================================================
    # Máximo por trimestre = n_produtos × 10 pts
    # q_final = (pontos_obtidos / máximo) × 100
    q1_final = (total_p_q1 / (n_produtos * 10)) * 100 if n_produtos > 0 else 0
    q2_final = (total_p_q2 / (n_produtos * 10)) * 100 if n_produtos > 0 else 0
    q3_final = (total_p_q3 / (n_produtos * 10)) * 100 if n_produtos > 0 else 0
    q4_final = (total_p_q4 / (n_produtos * 10)) * 100 if n_produtos > 0 else 0

    with col_q1:
        st.metric("Q1", f"{q1_final:.0f}")

    with col_q2:
        st.metric("Q2", f"{q2_final:.0f}")

    with col_q3:
        st.metric("Q3", f"{q3_final:.0f}")

    with col_q4:
        st.metric("Q4", f"{q4_final:.0f}")

    with col_qf:
        st.metric("FINAL", "0")

# =====================================================
# MÉDIA FINAL DO CONSULTOR
# =====================================================

df_score = pd.DataFrame(pontuacao_produtos)
media_pontuacao = df_score["pontuacao"].mean() if not df_score.empty else 0