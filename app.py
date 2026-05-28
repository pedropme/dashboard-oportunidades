import streamlit as st
import pandas as pd
import unicodedata
import altair as alt
import geopandas as gpd
import os
import datetime
import subprocess
import json

# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="Resumo Geral de Oportunidades e Performance",
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
# AUTENTICAÇÃO
# =========================
USUARIOS_FILE = "dados/usuarios.json"

def _load_usuarios():
    # 1. Streamlit Secrets (Streamlit Cloud — não entra no git)
    try:
        if "usuarios" in st.secrets:
            result = {}
            for email, dados in st.secrets["usuarios"].items():
                result[email] = {
                    "senha":           dados.get("senha", ""),
                    "perfil":          dados.get("perfil", "geral"),
                    "nome":            dados.get("nome", ""),
                    "filial_restrita": dados.get("filial_restrita") or None,
                    "regiao_restrita": dados.get("regiao_restrita") or None,
                    "ultimo_acesso":   None,
                }
            return result
    except Exception:
        pass
    # 2. Arquivo local (desenvolvimento / execução local)
    try:
        with open(USUARIOS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_usuarios(data):
    try:
        with open(USUARIOS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass  # No Streamlit Cloud, alterações não persistem entre reinicializações

if "usuario" not in st.session_state:
    st.markdown("""
    <style>
        section[data-testid="stMain"] .block-container {
            padding-top: 5vh !important;
        }
    </style>
    """, unsafe_allow_html=True)
    _, _col_login, _ = st.columns([1, 1.4, 1])
    with _col_login:
        try:
            _li, _lc, _lr = st.columns([1, 2, 1])
            with _lc:
                st.image("dados/logo_pme.png", use_container_width=True)
        except Exception:
            pass
        st.markdown(
            "<h3 style='text-align:center; margin-bottom:16px; margin-top:6px; "
            "font-size:19px; font-weight:600;'>"
            "Resumo Geral de Oportunidades e Performance</h3>",
            unsafe_allow_html=True
        )
        with st.form("login_form"):
            _email_input = st.text_input(
                "E-mail", placeholder="usuario@pmemaquinas.com.br"
            )
            _senha_input = st.text_input("Senha", type="password")
            _login_btn = st.form_submit_button(
                "Entrar", use_container_width=True, type="primary"
            )
        st.markdown(
            "<div style='text-align:center; margin-top:10px;'>"
            "<a href='https://wa.me/+5527999981134' target='_blank' "
            "style='font-size:13px; color:#25D366; text-decoration:none;'>"
            "💬 Esqueceu sua senha? Fale conosco</a></div>",
            unsafe_allow_html=True
        )
        if _login_btn:
            _usuarios_db = _load_usuarios()
            _u = _usuarios_db.get(_email_input)
            if _u and _u.get("senha") == _senha_input:
                st.session_state.usuario         = _email_input
                st.session_state.perfil          = _u.get("perfil", "geral")
                st.session_state.nome            = _u.get(
                    "nome",
                    _email_input.split("@")[0].split(".")[0].capitalize()
                )
                st.session_state.filial_restrita = _u.get("filial_restrita")
                st.session_state.regiao_restrita = _u.get("regiao_restrita")
                _u["ultimo_acesso"] = datetime.datetime.now().strftime(
                    "%d/%m/%Y %H:%M"
                )
                _save_usuarios(_usuarios_db)
                st.rerun()
            else:
                st.error("E-mail ou senha incorretos.")
    st.stop()

# --- Variáveis de sessão ---
_perfil          = st.session_state.get("perfil", "geral")
_nome            = st.session_state.get("nome", "")
_filial_restrita   = st.session_state.get("filial_restrita")   # None | "LINHARES" | "BOM JESUS,URUCUI"
_filiais_restritas = (
    [f.strip() for f in _filial_restrita.split(",") if f.strip()]
    if _filial_restrita else None
)
_regiao_restrita   = st.session_state.get("regiao_restrita")   # None | "CERRADO" | "SUDESTE"

# =========================
# HEADER
# =========================
st.markdown(
    "<h1 style='text-align:center; margin-top:8px;'>Resumo de Oportunidades</h1>",
    unsafe_allow_html=True
)

_tabs_labels = [
    "📊 Resumo por Vendedor",
    "🏙️ Resumo por Município",
    "📈 Matriz de Performance",
    "🔽 Funil de Vendas",
]
if _perfil == "admin":
    _tabs_labels.append("⚙️ Administração")
_all_tabs = st.tabs(_tabs_labels)
tab1, tab2, tab3, tab4 = _all_tabs[:4]
tab_admin = _all_tabs[4] if _perfil == "admin" else None

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
# PADRÃO DE COLUNAS
# =========================
COL_DOC  = "Documento"
COL_CONC = "Concessionaria"
COL_MUN  = "CD_MUN"
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
# CLASSIFICAÇÃO PRODUTOS
# =========================
def classificar_produto(row):
    de_para  = row["Calc dim De Para Familia 2"]
    segmento = row["Segmento Maq"]
    familia  = row["Familia"]
    tipo     = row["Tipo Produto"]
    grupo    = row["Grupo Modelo"]
    if "TRATOR"               in de_para:  return "TRATOR"
    if "VEICULOS OFF ROAD"    in segmento: return "VEICULOS OFF ROAD"
    if "IMPLEMENTO"           in familia:  return "IMPLEMENTO"
    if "USADO"                in familia:  return "USADOS"
    if "EMPILHADEIRA"         in familia:  return "EMPILHADEIRA"
    if "PLATAFORMA"           in familia:  return "PLATAFORMA"
    if "DRONE"                in tipo:     return "DRONE"
    if "RECOLHEDORA AUTOMOTRIZ" in tipo:   return "RECOLHEDORA AUTOMOTRIZ"
    if "MASTER CAFE"          in grupo:    return "CR"
    if "2 CR"                 in grupo:    return "2 CR"
    if "MASTER GRAOS"         in grupo:    return "MASTER GRAOS"
    if "PULVERIZADOR"         in grupo:    return "PULVERIZADOR"
    if "PLANTADEIRA"          in grupo:    return "PLANTADEIRA"
    return None

# =========================
# BASES (cacheadas)
# =========================
@st.cache_data
def load_clientes():
    df = pd.read_excel("dados/clientes.xlsx")
    df = df.rename(columns={
        "Documento (BR: CPF/CNPJ)": COL_DOC,
        "Concessionária":           COL_CONC,
        "CÓD":                      COL_MUN,
    })
    df[COL_VEND] = normalizar(df[COL_VEND])
    df[COL_DOC]  = df[COL_DOC].astype(str).str.strip()
    df[COL_CONC] = normalizar(df[COL_CONC])
    df[COL_MUN]  = df[COL_MUN].astype(str).str.strip()
    return df

@st.cache_data
def load_opp():
    df = pd.read_excel("dados/oportunidades.xlsx")
    df = df.rename(columns={
        "Vendedor (Conta) (Conta)":                   COL_VEND,
        "Conta":                                      "Cliente",
        "Documento (BR: CPF/CNPJ) (Conta) (Conta)":  COL_DOC,
        "Concessionária (Conta) (Conta)":             COL_CONC,
    })
    df[COL_VEND] = normalizar(df[COL_VEND])
    df[COL_DOC]  = df[COL_DOC].astype(str).str.strip()
    df[COL_CONC] = normalizar(df[COL_CONC])
    df["Data de Criação"] = pd.to_datetime(df["Data de Criação"], errors="coerce")
    return df

@st.cache_data
def load_territorio():
    df = pd.read_excel("dados/territorio.xlsx")
    for col in ["NOME CRM", "NOME BI", "Filial", "Região", "Marca"]:
        df[col] = normalizar(df[col])
    return df

@st.cache_data
def load_vendas_e_realizado():
    df = pd.read_excel("dados/vendas.xlsx")
    for col in ["Segmento Maq", "Familia", "Tipo Produto",
                "Grupo Modelo", "Vendedor", "Calc dim De Para Familia 2"]:
        df[col] = normalizar(df[col].astype(str))
    df["PRODUTO_MATRIZ"]   = df.apply(classificar_produto, axis=1)
    df["Calc Mes"]         = df["Calc Mes"].astype(str).str.strip()
    df["MES"]              = pd.to_numeric(df["Calc Mes"], errors="coerce")
    df["Ano"]              = df["Ano"].astype(str).str.strip()
    df["ANO"]              = pd.to_numeric(df["Ano"], errors="coerce")
    df["VALOR_REALIZADO"]  = df["Quantidade"].astype(float)
    mask_v = df["PRODUTO_MATRIZ"].isin(["IMPLEMENTO", "USADOS"])
    df.loc[mask_v, "VALOR_REALIZADO"] = df.loc[mask_v, "Vl NFVenda"]
    realizado = (
        df[df["PRODUTO_MATRIZ"].notna()]
        .groupby(["Vendedor", "PRODUTO_MATRIZ", "MES"])["VALOR_REALIZADO"]
        .sum().reset_index()
    )
    realizado.columns = ["CONSULTOR", "PRODUTO", "MES", "REALIZADO"]
    return df, realizado

@st.cache_data
def load_rel_prod():
    df = pd.read_excel(
        "dados/Relatorio de Oportunidades e Produtos.xlsx",
        usecols=[2, 3, 4, 5, 13, 20, 33, 35, 47]
    )
    df.columns = [
        "Cliente", COL_DOC, COL_CONC, COL_VEND,
        "Data de Criação", "Razão do Status",
        "Tipo de Produto", "Família", "Tipo de Adicional",
    ]
    df[COL_VEND]          = normalizar(df[COL_VEND])
    df["Data de Criação"] = pd.to_datetime(df["Data de Criação"], dayfirst=True, errors="coerce")
    return df

clientes            = load_clientes()
opp                 = load_opp()
territorio          = load_territorio()
vendas, realizado   = load_vendas_e_realizado()
rel_prod            = load_rel_prod()

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

# ── Restrição de acesso por filial(is) ou região ─────────────────────────────
if _filiais_restritas:
    dashboard = dashboard[dashboard["Filial"].isin(_filiais_restritas)]
elif _regiao_restrita:
    dashboard = dashboard[dashboard["Região"] == _regiao_restrita]

# =========================
# SIDEBAR
# =========================

# ── Logo + Projeto Horizonte ──────────────────────────────
st.sidebar.image("dados/logo_pme.png", use_container_width=True)
st.sidebar.markdown(
    """<div style='text-align:center; font-size:14px; font-weight:300;
        color:#555; margin-top:2px; margin-bottom:12px;'
    >Projeto Horizonte</div>""",
    unsafe_allow_html=True
)

# ── Usuário logado + Logout ───────────────────────────────
st.sidebar.markdown(
    f"""<div style='font-size:13px; color:#444; margin-bottom:6px;'>
        👤 <b>{_nome}</b>
    </div>""",
    unsafe_allow_html=True
)
if st.sidebar.button("🚪 Sair", use_container_width=True):
    st.session_state.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.title("Filtros")

if _filiais_restritas:
    # dashboard já foi pré-filtrado para as filiais deste usuário
    filial = _filiais_restritas[0] if len(_filiais_restritas) == 1 else "Todas"
    _label_filiais = " + ".join(_filiais_restritas)
    st.sidebar.markdown(
        f"""<div style='font-size:13px; color:#888; margin-bottom:10px;
            border:1px solid #ddd; border-radius:6px; padding:6px 10px;
            background:#f9f9f9;'>
            🔒 <b>{'Filial' if len(_filiais_restritas)==1 else 'Filiais'}:</b>
            {_label_filiais}
        </div>""",
        unsafe_allow_html=True
    )
    regiao = st.sidebar.selectbox(
        "Região",
        ["Todas"] + sorted(dashboard["Região"].dropna().unique())
    )
elif _regiao_restrita:
    # dashboard já pré-filtrado para esta região
    regiao = _regiao_restrita
    st.sidebar.markdown(
        f"""<div style='font-size:13px; color:#888; margin-bottom:10px;
            border:1px solid #ddd; border-radius:6px; padding:6px 10px;
            background:#f9f9f9;'>
            🔒 <b>Região:</b> {_regiao_restrita}
        </div>""",
        unsafe_allow_html=True
    )
    filial = st.sidebar.selectbox(
        "Filial",
        ["Todas"] + sorted(dashboard["Filial"].dropna().unique())
    )
else:
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

# ── Datas de atualização ──────────────────────────────────
def _data_mod(path):
    # Usa git log para pegar a data do último commit que alterou o arquivo.
    # Funciona tanto localmente quanto no Streamlit Cloud.
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", path],
            capture_output=True, text=True
        )
        date_str = result.stdout.strip()
        if date_str:
            return datetime.datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        pass
    # fallback: data de modificação do sistema de arquivos
    try:
        ts = os.path.getmtime(path)
        return datetime.datetime.fromtimestamp(ts).strftime("%d/%m/%Y")
    except Exception:
        return "—"

_bases = [
    ("Clientes",        "dados/clientes.xlsx"),
    ("Oportunidades",   "dados/oportunidades.xlsx"),
    ("Território",      "dados/territorio.xlsx"),
    ("Vendas",          "dados/vendas.xlsx"),
    ("Rel. Produtos",   "dados/Relatorio de Oportunidades e Produtos.xlsx"),
]

_linhas = "<br>".join(
    f"<b>{nome}</b>: {_data_mod(path)}"
    for nome, path in _bases
)

st.sidebar.markdown(
    f"""<hr style='margin:12px 0 8px 0'>
    <div style='font-size:14px; font-weight:300; color:#555; line-height:1.8;'>
        <b style='color:#333;'>Última atualização</b><br>{_linhas}
    </div>""",
    unsafe_allow_html=True
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

    # Criador: "Criado pelo celular" se preenchido, senão "Criada Por"
    _cel = df_detail["Criado pelo celular"].astype(str).str.strip()
    df_detail["Criador"] = _cel.where(
        ~_cel.isin(["", "nan", "None"]),
        df_detail["Criada Por"].fillna("")
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
                "Criador",
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

        # Criador: "Criado pelo celular" se preenchido, senão "Criada Por"
        _cel2 = df_detail_mun["Criado pelo celular"].astype(str).str.strip()
        df_detail_mun["Criador"] = _cel2.where(
            ~_cel2.isin(["", "nan", "None"]),
            df_detail_mun["Criada Por"].fillna("")
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
                    "Criador"
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

    if _filiais_restritas:
        matriz = matriz[matriz["Filial"].isin(_filiais_restritas)]
    elif filial != "Todas":
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

# =========================
# FUNIL DE VENDAS
# =========================
with tab4:

    COL_RAZAO = "Razão do Status"
    NOMES_MES  = {1:"Jan",2:"Fev",3:"Mar",4:"Abr",5:"Mai",6:"Jun",
                  7:"Jul",8:"Ago",9:"Set",10:"Out",11:"Nov",12:"Dez"}

    # ── Filtro de data (canto direito) ────────────────────────
    anos_opp = sorted(opp["Data de Criação"].dt.year.dropna().unique().astype(int).tolist(), reverse=True)

    col_tit, col_ano, col_mes = st.columns([4, 1, 1])
    with col_tit:
        st.markdown("### Funil de Vendas — Oportunidades em Aberto")

    with col_ano:
        ano_sel = st.selectbox("Ano", ["Todos"] + [str(a) for a in anos_opp], key="funil_ano")

    with col_mes:
        if ano_sel != "Todos":
            meses_disp = sorted(
                opp[opp["Data de Criação"].dt.year == int(ano_sel)]["Data de Criação"]
                .dt.month.dropna().unique().astype(int).tolist()
            )
            opcoes_mes = ["Todos"] + [f"{m:02d} — {NOMES_MES[m]}" for m in meses_disp]
        else:
            opcoes_mes = ["Todos"]
        mes_sel = st.selectbox("Mês", opcoes_mes, key="funil_mes",
                               disabled=(ano_sel == "Todos"))

    # ── Filtra opp em aberto + sidebar + data ─────────────────
    vendedores_funil = df_base[COL_VEND].dropna().unique()
    opp_funil = opp[
        opp[COL_VEND].isin(vendedores_funil)
        & ~opp["Status"].str.upper().str.contains("GANH|PERD", na=False)
    ].copy()

    if ano_sel != "Todos":
        opp_funil = opp_funil[opp_funil["Data de Criação"].dt.year == int(ano_sel)]
        if mes_sel != "Todos":
            mes_num = int(mes_sel.split(" — ")[0])
            opp_funil = opp_funil[opp_funil["Data de Criação"].dt.month == mes_num]

    if opp_funil.empty:
        st.info("Nenhuma oportunidade em aberto para os filtros selecionados.")
    else:
        # Agrupa por Razão do Status
        funil_df = (
            opp_funil.groupby(COL_RAZAO)
            .size()
            .reset_index(name="Quantidade")
            .sort_values(COL_RAZAO, ascending=True)
        )
        total_funil = funil_df["Quantidade"].sum()
        funil_df["%"] = (funil_df["Quantidade"] / total_funil * 100).round(1)

        # ── Gráfico horizontal (funil) ──────────────────────────────
        chart = (
            alt.Chart(funil_df)
            .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
            .encode(
                y=alt.Y(
                    f"{COL_RAZAO}:N",
                    sort=alt.EncodingSortField(field=COL_RAZAO, order="descending"),
                    axis=alt.Axis(labelLimit=300, title=None)
                ),
                x=alt.X("Quantidade:Q", axis=alt.Axis(title="Quantidade de Oportunidades")),
                color=alt.Color("Quantidade:Q", scale=alt.Scale(scheme="blues"), legend=None),
                tooltip=[
                    alt.Tooltip(f"{COL_RAZAO}:N", title="Razão do Status"),
                    alt.Tooltip("Quantidade:Q", title="Quantidade"),
                    alt.Tooltip("%:Q", title="%", format=".1f")
                ]
            )
            .properties(height=max(200, len(funil_df) * 45))
        )
        text = chart.mark_text(align="left", dx=5, color="#333").encode(
            text=alt.Text("Quantidade:Q")
        )
        st.altair_chart(chart + text, use_container_width=True)

        st.markdown("---")

        # ── Tabela resumo ────────────────────────────────────────────
        st.markdown(
            f"<span style='font-size:15px;'>Total de oportunidades em aberto: "
            f"<b>{total_funil:,}</b></span>".replace(",", "."),
            unsafe_allow_html=True
        )
        tabela_funil = funil_df.copy()
        tabela_funil["%"] = tabela_funil["%"].apply(lambda x: f"{x:.1f}%".replace(".", ","))
        st.dataframe(
            tabela_funil.rename(columns={COL_RAZAO: "Razão do Status", "Quantidade": "Qtd"}),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Razão do Status": st.column_config.TextColumn("Razão do Status", width="large"),
                "Qtd":             st.column_config.NumberColumn("Qtd", width="small"),
                "%":               st.column_config.TextColumn("%", width="small"),
            }
        )

    st.markdown("---")

    # ── Gráfico por Produto ───────────────────────────────────
    mostrar_prod = st.checkbox("📦 Mostrar gráfico de produtos por razão de status", value=False)

    if mostrar_prod:

        st.markdown("### Funil por Produto — Oportunidades em Aberto")
        por_familia = st.toggle("Mostrar por família", value=False)

        # Filtra rel_prod: em aberto + vendedores + data
        mask_aberto = ~rel_prod["Razão do Status"].str.upper().str.contains("GANH|PERD", na=False)
        rel_funil = rel_prod[
            rel_prod[COL_VEND].isin(vendedores_funil) & mask_aberto
        ].copy()

        if ano_sel != "Todos":
            rel_funil = rel_funil[rel_funil["Data de Criação"].dt.year == int(ano_sel)]
            if mes_sel != "Todos":
                mes_num = int(mes_sel.split(" — ")[0])
                rel_funil = rel_funil[rel_funil["Data de Criação"].dt.month == mes_num]

        # Determina categoria e família
        rel_funil["Categoria"] = rel_funil["Tipo de Produto"].apply(
            lambda x: "Implementos / Acessórios"
            if str(x).strip() == "Implementos / Acessórios"
            else "Produto"
        )
        rel_funil["Família Exibida"] = rel_funil.apply(
            lambda r: r["Tipo de Adicional"]
            if r["Categoria"] == "Implementos / Acessórios"
            else r["Família"],
            axis=1
        )

        if rel_funil.empty:
            st.info("Nenhum produto encontrado para os filtros selecionados.")
        else:
            grand_total_prod = len(rel_funil)

            # Eixo Y sempre = Razão do Status
            # Cor: Categoria (padrão) ou Família Exibida (por_familia)
            cor_col = "Família Exibida" if por_familia else "Categoria"

            prod_df = (
                rel_funil.groupby(["Razão do Status", cor_col])
                .size()
                .reset_index(name="Quantidade")
            )
            prod_df["% Total"] = (prod_df["Quantidade"] / grand_total_prod * 100).round(1)

            # Totais por razão (rótulo no final da barra)
            totais_grupo = (
                prod_df.groupby("Razão do Status")["Quantidade"]
                .sum().reset_index(name="Total")
            )
            totais_grupo["% Total"] = (totais_grupo["Total"] / grand_total_prod * 100).round(1)
            totais_grupo["Label %"] = totais_grupo["% Total"].apply(
                lambda x: f"{x:.1f}%".replace(".", ",")
            )

            # Ordem do eixo Y
            if por_familia:
                # maior total no topo → lista crescente (Altair: 1º item = base)
                ordem_y = (
                    totais_grupo.sort_values("Total", ascending=True)
                    ["Razão do Status"].tolist()
                )
                y_sort = ordem_y
            else:
                y_sort = alt.EncodingSortField(field="Razão do Status", order="descending")

            # Paleta de cores
            if por_familia:
                color_enc = alt.Color(
                    f"{cor_col}:N",
                    legend=alt.Legend(title="Família", symbolLimit=40)
                )
            else:
                color_enc = alt.Color(
                    f"{cor_col}:N",
                    scale=alt.Scale(
                        domain=["Produto", "Implementos / Acessórios"],
                        range=["#1565C0", "#E65100"]
                    ),
                    legend=alt.Legend(title="Tipo")
                )

            chart_prod = (
                alt.Chart(prod_df)
                .mark_bar(cornerRadiusTopRight=3, cornerRadiusBottomRight=3)
                .encode(
                    y=alt.Y(
                        "Razão do Status:N",
                        sort=y_sort,
                        axis=alt.Axis(labelLimit=300, title=None)
                    ),
                    x=alt.X(
                        "Quantidade:Q",
                        stack="zero",
                        axis=alt.Axis(title="Quantidade")
                    ),
                    color=color_enc,
                    tooltip=[
                        alt.Tooltip("Razão do Status:N", title="Razão do Status"),
                        alt.Tooltip(f"{cor_col}:N",      title=cor_col),
                        alt.Tooltip("Quantidade:Q",       title="Quantidade"),
                        alt.Tooltip("% Total:Q",          title="% do Total", format=".1f"),
                    ]
                )
                .properties(height=max(200, prod_df["Razão do Status"].nunique() * 45))
            )

            text_prod = (
                alt.Chart(totais_grupo)
                .mark_text(align="left", dx=5, color="#333", fontSize=12)
                .encode(
                    y=alt.Y("Razão do Status:N", sort=y_sort),
                    x=alt.X("Total:Q", stack="zero"),
                    text=alt.Text("Label %:N")
                )
            )

            st.altair_chart(chart_prod + text_prod, use_container_width=True)

# =========================
# PAINEL ADMINISTRAÇÃO
# =========================
if _perfil == "admin" and tab_admin is not None:
    with tab_admin:
        st.markdown("## ⚙️ Gerenciamento de Usuários")

        _db = _load_usuarios()

        _perfil_labels = {
            "admin":           "👑 Administrador",
            "geral":           "👁️ Geral",
            "filial_restrita": "📍 Filial Restrita",
            "divisao":         "🗺️ Divisão",
        }

        # ── Cabeçalho da tabela ───────────────────────────
        _hdr = st.columns([2.3, 1.0, 1.5, 1.8, 1.8, 1.3])
        for _hc, _ht in zip(
            _hdr,
            ["E-mail", "Nome", "Perfil", "Restrição",
             "Último Acesso", "Senha Atual"]
        ):
            _hc.markdown(f"**{_ht}**")
        st.divider()

        # ── Linhas ───────────────────────────────────────
        for _uemail, _udata in _db.items():
            _c0, _c1, _c2, _c3, _c4, _c5 = st.columns(
                [2.3, 1.0, 1.5, 1.8, 1.8, 1.3]
            )
            _c0.write(_uemail)
            _c1.write(_udata.get("nome", ""))
            _c2.write(
                _perfil_labels.get(_udata.get("perfil", ""), _udata.get("perfil", ""))
            )
            # Restrição: filial(is) ou região
            if _udata.get("regiao_restrita"):
                _restr = f"🗺️ {_udata['regiao_restrita']}"
            elif _udata.get("filial_restrita"):
                _restr = f"📍 {_udata['filial_restrita']}"
            else:
                _restr = "—"
            _c3.write(_restr)
            _c4.write(_udata.get("ultimo_acesso") or "Nunca")
            _c5.write(_udata.get("senha", ""))

            # ── Formulário de edição ──────────────────────
            _form_key = _uemail.replace("@", "_").replace(".", "_")
            with st.expander(
                f"✏️ Editar — {_udata.get('nome', _uemail)}", expanded=False
            ):
                with st.form(f"_fedit_{_form_key}"):
                    _fa, _fb = st.columns(2)
                    _novo_nome = _fa.text_input(
                        "Nome", value=_udata.get("nome", "")
                    )
                    _opcoes_p = ["admin", "geral", "filial_restrita", "divisao"]
                    _idx_p = (
                        _opcoes_p.index(_udata.get("perfil", "geral"))
                        if _udata.get("perfil") in _opcoes_p else 1
                    )
                    _novo_perfil = _fb.selectbox(
                        "Perfil",
                        options=_opcoes_p,
                        format_func=lambda x: _perfil_labels.get(x, x),
                        index=_idx_p,
                    )
                    _fc, _fd = st.columns(2)
                    _nova_filial_r = _fc.text_input(
                        "Filial Restrita (vírgula p/ múltiplas)",
                        value=_udata.get("filial_restrita") or "",
                    )
                    _nova_regiao_r = _fd.text_input(
                        "Região Restrita",
                        value=_udata.get("regiao_restrita") or "",
                    )
                    _nova_senha = st.text_input(
                        "Nova Senha (vazio = manter atual)",
                        type="password",
                    )
                    _btn_salvar = st.form_submit_button(
                        "💾 Salvar alterações",
                        use_container_width=True,
                        type="primary",
                    )
                    if _btn_salvar:
                        _db[_uemail]["nome"]   = _novo_nome
                        _db[_uemail]["perfil"] = _novo_perfil
                        _db[_uemail]["filial_restrita"] = (
                            _nova_filial_r.strip().upper() or None
                        )
                        _db[_uemail]["regiao_restrita"] = (
                            _nova_regiao_r.strip().upper() or None
                        )
                        if _nova_senha:
                            _db[_uemail]["senha"] = _nova_senha
                        _save_usuarios(_db)
                        st.success(
                            f"✅ Usuário **{_uemail}** atualizado com sucesso!"
                        )
                        st.rerun()

            st.divider()