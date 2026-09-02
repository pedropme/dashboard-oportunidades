import streamlit as st
import pandas as pd
import unicodedata
import altair as alt
import geopandas as gpd
import os
import datetime
import subprocess
import json
import time
from streamlit_cookies_controller import CookieController

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
        return True
    except Exception:
        return False  # No Streamlit Cloud o disco é efêmero


def _usuarios_via_secrets():
    """True quando a fonte de usuários é o st.secrets (Streamlit Cloud)."""
    try:
        return "usuarios" in st.secrets
    except Exception:
        return False


def _toml_usuario(email, dados):
    """Gera o bloco TOML de um usuário para colar nos Secrets."""
    linhas = [
        f'[usuarios."{email}"]',
        f'senha = "{dados.get("senha", "")}"',
        f'perfil = "{dados.get("perfil", "geral")}"',
        f'nome = "{dados.get("nome", "")}"',
    ]
    if dados.get("filial_restrita"):
        linhas.append(f'filial_restrita = "{dados["filial_restrita"]}"')
    if dados.get("regiao_restrita"):
        linhas.append(f'regiao_restrita = "{dados["regiao_restrita"]}"')
    return "\n".join(linhas)

# Controlador de cookies — inicializado antes de qualquer st.stop()
# para que funcione tanto na tela de login quanto no dashboard.
_cookies = CookieController(key="pme_cookies")

if "usuario" not in st.session_state:
    # ── Tentar restaurar sessão a partir do cookie (login persistente) ──
    # O CookieController lê cookies via JavaScript (assíncrono): no primeiro
    # render self.__cookies pode ser None e .get() lança TypeError.
    try:
        _auth_raw = _cookies.get("pme_auth")
    except Exception:
        _auth_raw = None

    if _auth_raw:
        try:
            _auth_data = json.loads(_auth_raw)
            if _auth_data.get("exp", 0) > time.time():
                st.session_state.usuario         = _auth_data["usuario"]
                st.session_state.perfil          = _auth_data.get("perfil", "geral")
                st.session_state.nome            = _auth_data.get("nome", "")
                st.session_state.filial_restrita = _auth_data.get("filial_restrita")
                st.session_state.regiao_restrita = _auth_data.get("regiao_restrita")
                st.rerun()
        except Exception:
            pass  # Cookie inválido ou corrompido — segue para login

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
            # Busca tolerante a maiúsculas/espaços (autofill costuma
            # inserir espaço ou capitalizar a primeira letra)
            _email_busca = _email_input.strip().lower()
            _email_input = _email_busca
            _u = None
            for _k, _v in _usuarios_db.items():
                if _k.strip().lower() == _email_busca:
                    _u, _email_input = _v, _k
                    break
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
                # Grava cookie com validade de 8 horas
                _cookies.set(
                    "pme_auth",
                    json.dumps({
                        "usuario":         _email_input,
                        "perfil":          _u.get("perfil", "geral"),
                        "nome":            _u.get(
                            "nome",
                            _email_input.split("@")[0].split(".")[0].capitalize()
                        ),
                        "filial_restrita": _u.get("filial_restrita"),
                        "regiao_restrita": _u.get("regiao_restrita"),
                        "exp":             time.time() + 28800,
                    }),
                    max_age=28800,
                )
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
    "🗺️ Resumo em Mapas",
    "📈 Matriz de Performance",
    "🔽 Funil de Vendas",
]
if _perfil == "admin":
    _tabs_labels.append("⚙️ Administração")
_all_tabs = st.tabs(_tabs_labels)
tab1, tab2, tab3, tab4 = _all_tabs[:4]
tab_admin = _all_tabs[4] if _perfil == "admin" else None

# =========================
# INVALIDAÇÃO DE CACHE POR ARQUIVO
# =========================
def _sig(*paths):
    """
    Assinatura (mtime, tamanho) dos arquivos de dados.

    Entra como argumento das funções @st.cache_data: quando um arquivo é
    atualizado a assinatura muda, a chave do cache muda e o Streamlit relê
    do disco. Sem isso o cache só é limpo no restart do app — foi o que fez
    o dashboard continuar mostrando dados antigos após uma atualização.
    """
    marcas = []
    for p in paths:
        try:
            s = os.stat(p)
            marcas.append((p, s.st_mtime_ns, s.st_size))
        except OSError:
            marcas.append((p, None, None))
    return tuple(marcas)


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
# GUID que identifica a oportunidade. Na base de oportunidades é a coluna
# "(Não Modificar) Oportunidade"; no relatório de produtos é o
# "Identificador da Oportunidade" — permite ligar produtos à oportunidade.
COL_OPP_ID = "ID Oportunidade"

# Consórcio é preenchido à mão e fica em arquivo próprio: vendas.xlsx é
# recriado do zero pelo download diário, o que apagaria uma aba manual.
ARQ_CONSORCIO = "dados/vendas - Consórcio.xlsx"

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
    """
    Mapeia a linha de venda para o nome do produto usado nas METAS.
    Retornar None faz a linha ser descartada do realizado, então todo
    produto que existe em metas.xlsx precisa ter uma regra aqui.
    """
    de_para  = row["Calc dim De Para Familia 2"]
    segmento = row["Segmento Maq"]
    familia  = row["Familia"]
    tipo     = row["Tipo Produto"]
    grupo    = row["Grupo Modelo"]
    regiao   = row["Regiao"]
    # "Usado" vem em De Para ("USADOS NH" / "USADOS OUTRAS MARCAS"), nunca
    # na Familia, e tem precedência sobre o tipo de máquina: a meta de
    # USADOS é por faturamento e independe de ser plataforma, trator etc.
    #
    # Só no CERRADO existe meta de USADOS. No SUDESTE não há essa meta: o
    # equipamento usado conta na categoria dele, como se fosse novo (trator
    # usado -> TRATOR). Essas linhas caem nas regras abaixo e, quando o
    # De Para não revela a categoria, são resolvidas pela Família em
    # _load_vendas_e_realizado.
    if "USADO" in de_para and "SUDESTE" not in regiao:
        return "USADOS"
    if "TRATOR"               in de_para:  return "TRATOR"
    if "VEICULOS OFF ROAD"    in segmento: return "VEICULOS OFF ROAD"
    if "IMPLEMENTO"           in familia:  return "IMPLEMENTO"
    if "EMPILHADEIRA"         in familia:  return "EMPILHADEIRA"
    if "PLATAFORMA"           in familia:  return "PLATAFORMA"
    # Colheitadeira de grão (modelos CR*). Não confundir com a meta "CR",
    # que é da linha de café (mesmos 6 consultores da meta "2 CR").
    if "COLHEITADEIRA"        in de_para:  return "COLHEITADEIRA"
    if "DRONE"                in tipo:     return "DRONE"
    if "RECOLHEDORA AUTOMOTRIZ" in tipo:   return "RECOLHEDORA AUTOMOTRIZ"
    # Meta "CR" da linha de café = Arruador Soprador (ASM-1S / ASM-2S).
    # A Colhedeira Automotriz K.3000 (Grupo Modelo AUTOPROPELIDO) NÃO entra
    # aqui: terá meta própria de colhedeira autopropelida no futuro, e até
    # lá fica sem classificação de propósito.
    if "ARRUADOR"             in grupo:    return "CR"
    if "MASTER CAFE"          in grupo:    return "CR"
    if "2 CR"                 in grupo:    return "2 CR"
    if "MASTER GRAOS"         in grupo:    return "MASTER GRAOS"
    # De Para distingue o autopropelido do pulverizador implemento (que
    # já foi capturado acima). O nome precisa bater com o das metas.
    if "PULVERIZADOR AUTOPROPELIDO" in de_para: return "PULVERIZADOR AUTOPROPELIDO"
    if "PLANTADEIRA"          in grupo:    return "PLANTADEIRA"
    return None

# =========================
# BASES (cacheadas)
# =========================
def load_clientes():
    return _load_clientes(_sig("dados/clientes.xlsx"))

@st.cache_data
def _load_clientes(_assinatura):
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

def load_opp():
    return _load_opp(_sig("dados/oportunidades.xlsx"))

@st.cache_data
def _load_opp(_assinatura):
    df = pd.read_excel("dados/oportunidades.xlsx")
    df = df.rename(columns={
        "Vendedor (Conta) (Conta)":                   COL_VEND,
        "Conta":                                      "Cliente",
        "Documento (BR: CPF/CNPJ) (Conta) (Conta)":  COL_DOC,
        "Concessionária (Conta) (Conta)":             COL_CONC,
        "(Não Modificar) Oportunidade":               COL_OPP_ID,
    })
    if COL_OPP_ID in df.columns:
        df[COL_OPP_ID] = df[COL_OPP_ID].astype(str).str.strip()
    df[COL_VEND] = normalizar(df[COL_VEND])
    df[COL_DOC]  = df[COL_DOC].astype(str).str.strip()
    df[COL_CONC] = normalizar(df[COL_CONC])
    df["Data de Criação"] = pd.to_datetime(df["Data de Criação"], errors="coerce")
    return df

def load_territorio():
    return _load_territorio(_sig("dados/territorio.xlsx"))

@st.cache_data
def _load_territorio(_assinatura):
    df = pd.read_excel("dados/territorio.xlsx")
    for col in ["NOME CRM", "NOME BI", "Filial", "Região", "Marca", "UF"]:
        df[col] = normalizar(df[col])
    return df

def load_vendas_e_realizado():
    return _load_vendas_e_realizado(_sig("dados/vendas.xlsx", ARQ_CONSORCIO))

@st.cache_data
def _load_vendas_e_realizado(_assinatura):
    df = pd.read_excel("dados/vendas.xlsx")
    for col in ["Segmento Maq", "Familia", "Tipo Produto", "Grupo Modelo",
                "Vendedor", "Calc dim De Para Familia 2", "Regiao", "Modelo"]:
        df[col] = normalizar(df[col].astype(str))
    df["PRODUTO_MATRIZ"]   = df.apply(classificar_produto, axis=1)

    # ── Usados do Sudeste que as regras não classificaram ────────────────
    # No Sudeste o usado entra como novo, mas o De Para diz "USADOS NH" e
    # não revela a categoria (ex.: família TL = trator). Deduz a categoria
    # a partir de como a mesma Família aparece nas vendas novas.
    _usado   = df["Calc dim De Para Familia 2"].str.contains("USADO", na=False)
    _sudeste = df["Regiao"].str.contains("SUDESTE", na=False)
    _pendente = _usado & _sudeste & df["PRODUTO_MATRIZ"].isna()
    if _pendente.any():
        _mapa_familia = (
            df.loc[~_usado & df["PRODUTO_MATRIZ"].notna()]
            .groupby("Familia")["PRODUTO_MATRIZ"]
            .agg(lambda s: s.mode().iat[0])
        )
        df.loc[_pendente, "PRODUTO_MATRIZ"] = (
            df.loc[_pendente, "Familia"].map(_mapa_familia)
        )
        # Família sem equivalente novo (ex.: marca concorrente): usa o Modelo
        _resta = _usado & _sudeste & df["PRODUTO_MATRIZ"].isna()
        df.loc[_resta & df["Modelo"].str.contains("TRATOR", na=False),
               "PRODUTO_MATRIZ"] = "TRATOR"
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

    # ── Consórcio: base manual, realizado já agregado por consultor/mês ──
    # Só a ausência do arquivo é tolerada. Erro de formato propaga de
    # propósito: um "except: pass" aqui já escondeu a perda do consórcio
    # inteiro quando o download diário apagou a aba que ficava no vendas.xlsx.
    _MES_MAP = {"JAN":1,"FEV":2,"MAR":3,"ABR":4,"MAI":5,"JUN":6,
                "JUL":7,"AGO":8,"SET":9,"OUT":10,"NOV":11,"DEZ":12}
    if os.path.exists(ARQ_CONSORCIO):
        df_cons = pd.read_excel(ARQ_CONSORCIO, sheet_name="Vendas")
        df_cons["CONSULTOR"] = normalizar(df_cons["CONSULTOR"].astype(str))
        df_cons["PRODUTO"]   = normalizar(df_cons["PRODUTO"].astype(str))
        df_cons_long = df_cons.melt(
            id_vars=["CONSULTOR", "PRODUTO"],
            value_vars=list(_MES_MAP.keys()),
            var_name="MES_STR",
            value_name="REALIZADO",
        )
        df_cons_long["MES"] = df_cons_long["MES_STR"].map(_MES_MAP)
        df_cons_long["REALIZADO"] = pd.to_numeric(
            df_cons_long["REALIZADO"], errors="coerce"
        ).fillna(0)
        # != 0 e não > 0: estorno de cota vem negativo e precisa abater
        df_cons_agg = (
            df_cons_long[df_cons_long["REALIZADO"] != 0]
            .groupby(["CONSULTOR", "PRODUTO", "MES"])["REALIZADO"]
            .sum()
            .reset_index()
        )
        realizado = pd.concat([realizado, df_cons_agg], ignore_index=True)

    return df, realizado

def load_rel_prod():
    return _load_rel_prod(_sig("dados/Relatorio de Oportunidades e Produtos.xlsx"))

@st.cache_data
def _load_rel_prod(_assinatura):
    # A coluna 0 é o Identificador da Oportunidade (mesmo GUID da coluna
    # "(Não Modificar) Oportunidade" da base de oportunidades). O relatório
    # tem uma linha por produto, então o ID repete — usá-lo permite contar
    # oportunidades distintas em vez de linhas de produto.
    # Colunas AI (34, "Produto") e AV (47, "Tipo de Adicional") são
    # complementares: máquinas preenchem Produto, implementos preenchem
    # Tipo de Adicional.
    df = pd.read_excel(
        "dados/Relatorio de Oportunidades e Produtos.xlsx",
        usecols=[0, 2, 3, 4, 5, 13, 20, 32, 33, 34, 35, 36, 37, 38, 46, 47]
    )
    df.columns = [
        COL_OPP_ID,
        "Cliente", COL_DOC, COL_CONC, COL_VEND,
        "Data de Criação", "Razão do Status",
        "Valor Total", "Tipo de Produto", "Produto", "Família", "Modelo",
        "Preço por Unidade", "Quantidade",
        "Descrição Implemento", "Tipo de Adicional",
    ]
    # O relatório vem agrupado por oportunidade: o ID só aparece na primeira
    # linha e as demais linhas de produto vêm em branco. O ffill reconstitui
    # a qual oportunidade cada produto pertence.
    df[COL_OPP_ID] = df[COL_OPP_ID].ffill().astype(str).str.strip()

    # "Valor Total" é da OPORTUNIDADE (repetido em cada linha de produto);
    # somá-lo por linha duplica. O valor da linha é preço x quantidade.
    df["Preço por Unidade"] = pd.to_numeric(df["Preço por Unidade"], errors="coerce").fillna(0)
    df["Quantidade"]        = pd.to_numeric(df["Quantidade"], errors="coerce").fillna(0)
    df["Valor Total"]       = pd.to_numeric(df["Valor Total"], errors="coerce").fillna(0)
    df["Valor do Item"]     = df["Preço por Unidade"] * df["Quantidade"]
    df[COL_VEND]          = normalizar(df[COL_VEND])
    df["Data de Criação"] = pd.to_datetime(df["Data de Criação"], dayfirst=True, errors="coerce")
    return df

def _normalizar_sheet_loja(df):
    for col in ["NOME", "PRODUTO", "FILIAL", "REGIÃO"]:
        if col in df.columns:
            df[col] = normalizar(df[col])
    df["FILIAL_NOME"] = df["NOME"].str.replace(
        r"^PME\s*-\s*", "", regex=True
    ).str.strip()
    return df

def load_metas_loja():
    return _load_metas_loja(_sig("dados/metas.xlsx"))

@st.cache_data
def _load_metas_loja(_assinatura):
    return _normalizar_sheet_loja(
        pd.read_excel("dados/metas.xlsx", sheet_name="LOJA")
    )

def load_metas_orcamento():
    return _load_metas_orcamento(_sig("dados/metas.xlsx"))

@st.cache_data
def _load_metas_orcamento(_assinatura):
    return _normalizar_sheet_loja(
        pd.read_excel("dados/metas.xlsx", sheet_name="ORÇAMENTO")
    )

def load_metas_status():
    return _load_metas_status(_sig("dados/metas.xlsx"))

@st.cache_data
def _load_metas_status(_assinatura):
    df = pd.read_excel("dados/metas.xlsx")
    df["CONSULTOR"] = normalizar(df["CONSULTOR"])
    df["STATUS"]    = normalizar(df["STATUS"])
    return df[["CONSULTOR", "STATUS"]].drop_duplicates(subset=["CONSULTOR"])

clientes            = load_clientes()
opp                 = load_opp()
territorio          = load_territorio()
vendas, realizado   = load_vendas_e_realizado()
rel_prod            = load_rel_prod()
metas_loja          = load_metas_loja()
metas_orcamento     = load_metas_orcamento()
metas_status        = load_metas_status()

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
            "Região",
            "UF"
        ]
    ]
    .drop_duplicates(subset=["NOME CRM"])
    .rename(columns={
        "NOME CRM": COL_VEND,
        "UF": "Estado"
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
    _cookies.remove("pme_auth")
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
    estado = st.sidebar.selectbox(
        "Estado",
        ["Todos"] + sorted(dashboard["Estado"].dropna().unique())
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
    estado = st.sidebar.selectbox(
        "Estado",
        ["Todos"] + sorted(dashboard["Estado"].dropna().unique())
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

    estado = st.sidebar.selectbox(
        "Estado",
        ["Todos"] + sorted(
            dashboard["Estado"]
            .dropna()
            .unique()
        )
    )

# base filtrada até filial/região/estado
base_filtro_vendedor = dashboard.copy()

if regiao != "Todas":
    base_filtro_vendedor = base_filtro_vendedor[
        base_filtro_vendedor["Região"] == regiao
    ]

if filial != "Todas":
    base_filtro_vendedor = base_filtro_vendedor[
        base_filtro_vendedor["Filial"] == filial
    ]

if estado != "Todos":
    base_filtro_vendedor = base_filtro_vendedor[
        base_filtro_vendedor["Estado"] == estado
    ]

# ── Filtro de status (Ativos / Inativos / Todos) ─────────────────────────────
_nome_bi_to_status = dict(zip(metas_status["CONSULTOR"], metas_status["STATUS"]))
_crm_to_status = {
    row["NOME CRM"]: _nome_bi_to_status.get(row["NOME BI"])
    for _, row in territorio[["NOME CRM", "NOME BI"]].drop_duplicates(subset=["NOME CRM"]).iterrows()
}

status_filtro = st.sidebar.radio(
    "Status",
    ["Ativos", "Inativos", "Todos"],
    index=0,
)

if status_filtro == "Ativos":
    _crms_ok = {crm for crm, s in _crm_to_status.items() if s == "ATIVO"}
    base_filtro_vendedor = base_filtro_vendedor[
        base_filtro_vendedor[COL_VEND].isin(_crms_ok)
    ]
elif status_filtro == "Inativos":
    _crms_ok = {crm for crm, s in _crm_to_status.items() if s == "INATIVO"}
    base_filtro_vendedor = base_filtro_vendedor[
        base_filtro_vendedor[COL_VEND].isin(_crms_ok)
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

if estado != "Todos":
    df_base = df_base[
        df_base["Estado"] == estado
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
# HELPER: tabela com filtros por coluna (AgGrid)
# =========================
def _tabela(df, key, height=None, show_index=False, pct_cols=(),
            tooltip_col=None, tooltip_on=()):
    """
    Exibe DataFrame com filtros Excel-like clicáveis nos cabeçalhos e botão de download.

    tooltip_col: coluna cujo conteúdo aparece ao passar o mouse. Ela fica
                 oculta na grade (mas segue no CSV baixado).
    tooltip_on:  colunas que exibem esse tooltip; vazio = todas.
    """
    from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
    _df = df.reset_index() if show_index else df.reset_index(drop=True)

    # Botão de download (CSV separado por ; para abrir corretamente no Excel BR)
    _csv = _df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
    _dl_col, _ = st.columns([1, 6])
    with _dl_col:
        st.download_button(
            label="⬇️ Baixar CSV",
            data=_csv,
            file_name=f"{key}.csv",
            mime="text/csv",
            key=f"dl_{key}",
        )

    gb = GridOptionsBuilder.from_dataframe(_df)
    gb.configure_default_column(
        filter=True,
        sortable=True,
        resizable=True,
        suppressMenu=False,
    )
    for col in pct_cols:
        if col in _df.columns:
            gb.configure_column(
                col,
                type=["numericColumn", "numericFilter"],
                valueFormatter="value != null ? parseFloat(value).toFixed(1) + '%' : ''",
            )

    if tooltip_col and tooltip_col in _df.columns:
        # Tooltip nativo do navegador: respeita quebras de linha do texto
        gb.configure_grid_options(
            enableBrowserTooltips=True,
            tooltipShowDelay=200,
        )
        gb.configure_column(tooltip_col, hide=True)
        alvos = [c for c in (tooltip_on or _df.columns) if c != tooltip_col]
        for col in alvos:
            if col in _df.columns:
                gb.configure_column(col, tooltipField=tooltip_col)

    kw = {"height": height} if height else {}
    AgGrid(
        _df,
        gridOptions=gb.build(),
        update_mode=GridUpdateMode.NO_UPDATE,
        use_container_width=True,
        theme="streamlit",
        key=key,
        **kw,
    )

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

    _tabela(tabela_vendedor, key="tv_vendedor", height=500)

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

    # ── Produtos de cada oportunidade (tooltip ao passar o mouse) ─────
    # O relatório de produtos tem uma linha por item; agrupa pelo ID da
    # oportunidade para montar a lista exibida no hover.
    _itens = rel_prod.copy()

    def _texto(serie):
        """
        Normaliza para string, tratando NA e placeholders como ausente.
        Colapsa quebras de linha: o tooltip usa \\n para separar os itens,
        e algumas descrições do CRM vêm com quebras dentro do texto.
        """
        s = (
            serie.astype("string")
            .str.replace(r"\s*\n\s*", " / ", regex=True)
            .str.strip()
        )
        return s.mask(s.isin(["", "nan", "None", "<NA>"]))

    # Máquina preenche "Produto" (e traz Modelo); implemento/acessório
    # preenche "Tipo de Adicional" (e traz Descrição Implemento).
    # Mostra o modelo para máquinas e a descrição para os demais.
    # Sem Modelo, cai na categoria ("Tratores"): a coluna Descrição Produto
    # é campo de observação livre e não serve como rótulo.
    _eh_maquina = _texto(_itens["Produto"]).notna()
    _desc_maquina = (
        _texto(_itens["Modelo"])
        .fillna(_texto(_itens["Produto"]))
    )
    _desc_implemento = (
        _texto(_itens["Descrição Implemento"])
        .fillna(_texto(_itens["Tipo de Adicional"]))
    )
    _nome_item = (
        _desc_maquina.where(_eh_maquina, _desc_implemento)
        .fillna("Item sem descrição")
    )
    _itens["_linha"] = (
        "• "
        + _itens["Quantidade"].fillna(0).astype(int).astype("string") + "x "
        + _nome_item
        + _itens["Valor do Item"].apply(
            lambda v: f" — R$ {round(v):,}".replace(",", ".") if v else ""
        ).astype("string")
    )
    _produtos_por_opp = (
        _itens.groupby(COL_OPP_ID)["_linha"]
        .apply(lambda s: "\n".join(s))
    )
    df_detail["Produtos"] = (
        df_detail[COL_OPP_ID].map(_produtos_por_opp)
        .fillna("Sem produto cadastrado nesta oportunidade")
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
                "Razão do Status",
                "Valor Total",
                "Dias desde Criação",
                "Criador",
                "Produtos",
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

    st.caption(
        "💡 Passe o mouse sobre uma linha para ver os produtos da oportunidade."
    )
    _tabela(tabela_opp, key="tv_opp", tooltip_col="Produtos")

    # =========================
    # TAB 2 - MAPA MUNICÍPIO
    # =========================
    with tab2:

        st.subheader("Resumo em Mapas")

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
        mostrar_dados = st.toggle("Mostrar dados no mapa", value=True)

        # ── Tipo de informação ────────────────────────────────────────────────
        _lbl_m = "font-size:14px; font-weight:500; margin:0; padding-top:5px;"
        st.markdown(
            "<p style='font-size:14px; font-weight:600; margin:6px 0 2px 0;'>Tipo de informação</p>",
            unsafe_allow_html=True,
        )
        _ma, _mb, _mc, _ = st.columns([1.3, 0.5, 2.0, 6], gap="small")
        with _ma:
            st.markdown(
                f"<p style='{_lbl_m} text-align:right;'>Oportunidades</p>",
                unsafe_allow_html=True,
            )
        with _mb:
            _mapa_matriz = st.toggle("", key="mapa_tipo_toggle", label_visibility="collapsed")
        with _mc:
            st.markdown(
                f"<p style='{_lbl_m}'>Matriz de Performance</p>",
                unsafe_allow_html=True,
            )

        _tipo_mapa = "Matriz de Performance" if _mapa_matriz else "Oportunidades"

        # ── Exibição de oportunidades (apenas no modo Oportunidades) ─────────
        if _tipo_mapa == "Oportunidades":
            somente_abertas = st.radio(
                "Exibição de oportunidades (municípios)",
                options=["Todos com oportunidades", "Somente em aberto"],
                index=1,
                horizontal=True,
            )
        else:
            somente_abertas = "Todos com oportunidades"

        # =========================
        # MAPA INTERATIVO
        # =========================
        import folium
        from streamlit_folium import st_folium

        mapa_geo = mapa.to_crs(epsg=4326)

        if _tipo_mapa == "Oportunidades":
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
            # OpenStreetMap: CartoDB passou a exigir API key no endpoint
            # gratuito (basemaps.cartocdn.com/light_all), causando o erro
            # "api key required" no mapa.
            m = folium.Map(
                location=[-15, -55],
                zoom_start=4,
                tiles="OpenStreetMap"
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

            _tabela(tabela_municipios, key="tv_municipios")

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

            _tabela(tabela_desc_mun, key="tv_desc_mun")
        else:
            # ── MAPA MATRIZ DE PERFORMANCE ────────────────────────────────────
            # Usa a mesma lógica do ranking de consultores (Tab 3):
            # pontuação trimestral acumulada, média dos trimestres já iniciados.
            _mes_atual_mp = pd.Timestamp.today().month

            # Metas dos consultores ativos
            _mp_metas = pd.read_excel("dados/metas.xlsx")
            _mp_metas["CONSULTOR"] = normalizar(_mp_metas["CONSULTOR"])
            _mp_metas["PRODUTO"]   = normalizar(_mp_metas["PRODUTO"])
            _mp_metas["STATUS"]    = normalizar(_mp_metas["STATUS"])
            # Igualdade exata: "INATIVO" contém "ATIVO", então str.contains
            # deixaria os inativos passarem.
            _mp_metas = _mp_metas[_mp_metas["STATUS"] == "ATIVO"].copy()

            # Território filtrado pelos seletores da sidebar
            _mp_ter = (
                territorio[["NOME BI", "NOME CRM", "Código IBGE", "Filial", "Região", "UF"]]
                .drop_duplicates(subset=["NOME BI", "Código IBGE"])
                .copy()
            )
            _mp_ter["Código IBGE"] = _mp_ter["Código IBGE"].astype(str).str.strip()

            if regiao != "Todas":
                _mp_ter = _mp_ter[_mp_ter["Região"] == regiao]
            if _filiais_restritas:
                _mp_ter = _mp_ter[_mp_ter["Filial"].isin(_filiais_restritas)]
            elif filial != "Todas":
                _mp_ter = _mp_ter[_mp_ter["Filial"] == filial]
            if estado != "Todos":
                _mp_ter = _mp_ter[_mp_ter["UF"] == estado]
            if vendedor != "Todos":
                _mp_ter = _mp_ter[_mp_ter["NOME CRM"] == vendedor]

            def _mp_real(cons, prod, mes):
                f = realizado[
                    (realizado["CONSULTOR"] == cons) &
                    (realizado["PRODUTO"]   == prod) &
                    (realizado["MES"]       == mes)
                ]
                return f["REALIZADO"].sum() if not f.empty else 0

            def _mp_score(real, meta, base):
                if pd.isna(real) or pd.isna(meta): return 0.0
                if meta == 0:  return base           # meta zerada = já batida
                if real < meta: return 0.0
                return base + base * min((real - meta) / meta, 1.0) * 0.20

            # Média de performance (idêntica ao ranking do Tab 3) por consultor
            _mp_rows = []
            for _nome_bi in _mp_ter["NOME BI"].dropna().unique():
                _cons_metas = _mp_metas[_mp_metas["CONSULTOR"] == _nome_bi]
                if _cons_metas.empty:
                    continue
                _n    = len(_cons_metas)
                _base = (100 / _n) if _n > 0 else 0
                _pq1 = _pq2 = _pq3 = _pq4 = 0.0
                for _, _mr in _cons_metas.iterrows():
                    _p   = _mr["PRODUTO"]
                    _mq1 = _mr["JAN"] + _mr["FEV"] + _mr["MAR"]
                    _mq2 = _mr["ABR"] + _mr["MAI"] + _mr["JUN"]
                    _mq3 = _mr["JUL"] + _mr["AGO"] + _mr["SET"]
                    _mq4 = _mr["OUT"] + _mr["NOV"] + _mr["DEZ"]
                    _rq1 = sum(_mp_real(_nome_bi, _p, m) for m in [1,2,3])
                    _rq2 = sum(_mp_real(_nome_bi, _p, m) for m in [4,5,6])
                    _rq3 = sum(_mp_real(_nome_bi, _p, m) for m in [7,8,9])
                    _rq4 = sum(_mp_real(_nome_bi, _p, m) for m in [10,11,12])
                    _pq1 += _mp_score(_rq1, _mq1, _base)
                    _pq2 += _mp_score(_rq2, _mq2, _base) if _mes_atual_mp >= 4  else 0
                    _pq3 += _mp_score(_rq3, _mq3, _base) if _mes_atual_mp >= 7  else 0
                    _pq4 += _mp_score(_rq4, _mq4, _base) if _mes_atual_mp >= 10 else 0
                _vals = (
                    [round(_pq1, 1)] * int(_mes_atual_mp >= 1)
                    + [round(_pq2, 1)] * int(_mes_atual_mp >= 4)
                    + [round(_pq3, 1)] * int(_mes_atual_mp >= 7)
                    + [round(_pq4, 1)] * int(_mes_atual_mp >= 10)
                )
                _mp_rows.append({
                    "NOME BI":    _nome_bi,
                    "Atingimento": sum(_vals) / len(_vals) if _vals else 0.0,
                })

            if not _mp_rows:
                st.info("Nenhum dado de performance encontrado para os filtros selecionados.")
            else:
                _df_mp = pd.DataFrame(_mp_rows)

                # Média de atingimento por município (vários consultores → média)
                _mp_ter_mun = _mp_ter[["NOME BI", "Código IBGE"]].drop_duplicates()
                _df_mp_mun = (
                    _df_mp
                    .merge(_mp_ter_mun, on="NOME BI", how="left")
                    .groupby("Código IBGE")["Atingimento"]
                    .mean()
                    .reset_index()
                    .rename(columns={"Código IBGE": "CD_MUN"})
                )

                # Join com camada geográfica
                _mapa_mp = (
                    gdf_mun[["CD_MUN", "NM_MUN", "SIGLA_UF", "geometry"]]
                    .merge(_df_mp_mun, on="CD_MUN", how="right")
                    .to_crs(epsg=4326)
                )

                def _cor_ating(pct):
                    if pct >= 60: return "#2E7D32"   # verde
                    if pct >= 20: return "#F9A825"   # amarelo
                    return "#C62828"                  # vermelho

                m = folium.Map(
                    location=[-15, -55], zoom_start=4, tiles="OpenStreetMap"
                )

                for _, _row in _mapa_mp.iterrows():
                    if _row["geometry"] is None:
                        continue
                    _cor = _cor_ating(_row["Atingimento"])
                    _tip = (
                        f"<b>Município:</b> {_row.get('NM_MUN','')}<br>"
                        f"<b>UF:</b> {_row.get('SIGLA_UF','')}<br>"
                        f"<b>Atingimento:</b> {_row['Atingimento']:.1f}%"
                    )
                    folium.GeoJson(
                        _row["geometry"],
                        style_function=lambda x, c=_cor: {
                            "fillColor": c,
                            "color": "#333",
                            "weight": 1,
                            "fillOpacity": 0.65,
                        },
                        tooltip=_tip,
                    ).add_to(m)

                st_folium(m, width=None, height=650)

                # Legenda de cores
                st.markdown(
                    "<div style='display:flex;gap:24px;margin-top:6px;font-size:14px;'>"
                    "<span>🟢 &ge; 60%</span>"
                    "<span>🟡 20 – 59,9%</span>"
                    "<span>🔴 &lt; 20%</span>"
                    "</div>",
                    unsafe_allow_html=True,
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
    # Igualdade exata: "INATIVO" contém "ATIVO" como substring, então
    # str.contains("ATIVO") não filtrava nada e os inativos apareciam.
    metas = metas[metas["STATUS"] == "ATIVO"].copy()

    # =====================================================
    # BASE TERRITÓRIO
    # =====================================================
    base_territorio_matriz = (
        territorio[
            [
                "NOME BI",
                "Filial",
                "Região",
                "UF"
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

    if estado != "Todos":
        matriz = matriz[
            matriz["UF"] == estado
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
    # CONTROLES DE VISÃO E TIPO DE META (toggles)
    # =====================================================
    _lbl = "font-size:14px; font-weight:500; margin:0; padding-top:5px;"

    # Toggle 1 — Consultor / Loja
    _c1, _c2, _c3, _c_sp = st.columns([1.1, 0.5, 0.7, 8], gap="small")
    with _c1:
        st.markdown(
            f"<p style='{_lbl} text-align:right;'>Consultor</p>",
            unsafe_allow_html=True,
        )
    with _c2:
        _loja = st.toggle("", key="seg_loja", label_visibility="collapsed")
    with _c3:
        st.markdown(
            f"<p style='{_lbl}'>Loja</p>",
            unsafe_allow_html=True,
        )

    _seg_visao = "Loja" if _loja else "Consultor"

    # Toggle 2 — Matriz de Performance / Orçamento
    _c4, _c5, _c6, _ = st.columns([1.1, 0.5, 0.7, 8], gap="small")
    with _c4:
        st.markdown(
            f"<p style='{_lbl} text-align:right;'>Matriz de Performance</p>",
            unsafe_allow_html=True,
        )
    with _c5:
        _orcamento = st.toggle(
            "", key="tipo_meta_toggle",
            label_visibility="collapsed",
            disabled=not _loja,
        )
    with _c6:
        st.markdown(
            f"<p style='{_lbl}'>Orçamento</p>",
            unsafe_allow_html=True,
        )

    _tipo_meta = "Orçamento" if _orcamento else "Matriz de Performance"

    st.markdown("---")

    # =====================================================
    # SELECT LOJA / SELECT CONSULTOR  (condicional por toggle)
    # =====================================================
    pontuacao_produtos = []  # inicializado antes do branch

    if _seg_visao == "Loja":

        # ── MODO LOJA ──────────────────────────────────────────────────────────

        # Fonte de metas: LOJA ou ORÇAMENTO conforme toggle 2
        _fonte_loja = metas_orcamento if _tipo_meta == "Orçamento" else metas_loja

        # Realizado agregado por filial/loja (usando nome do território)
        _ter_map = (
            territorio[["NOME BI", "Filial"]]
            .drop_duplicates(subset=["NOME BI"])
        )
        _real_loja = (
            realizado
            .merge(_ter_map, left_on="CONSULTOR", right_on="NOME BI", how="left")
            .groupby(["Filial", "PRODUTO", "MES"])["REALIZADO"]
            .sum()
            .reset_index()
        )

        # Mapeamento NOME_LOJA → FILIAL_NOME (nome do território)
        _nome_to_filial = dict(
            zip(_fonte_loja["NOME"], _fonte_loja["FILIAL_NOME"])
        )

        def buscar_realizado_loja(nome, produto, mes):
            filial_nome = _nome_to_filial.get(nome, nome)
            f = _real_loja[
                (_real_loja["Filial"] == filial_nome)
                & (_real_loja["PRODUTO"] == produto)
                & (_real_loja["MES"] == mes)
            ]
            return f["REALIZADO"].sum() if not f.empty else 0

        # Filtrar fonte de metas pelos filtros do sidebar
        _ml = _fonte_loja.copy()

        if regiao != "Todas":
            _ml = _ml[_ml["REGIÃO"].str.upper() == regiao.upper()]

        if _filiais_restritas:
            _ml = _ml[_ml["FILIAL_NOME"].isin(_filiais_restritas)]
        elif filial != "Todas":
            _ml = _ml[_ml["FILIAL_NOME"] == filial]

        if estado != "Todos":
            # metas_loja/orçamento não trazem UF direto; usa o território
            # (Filial -> UF é 1:1) para mapear FILIAL_NOME -> Estado.
            _filial_to_uf = dict(zip(territorio["Filial"], territorio["UF"]))
            _ml = _ml[_ml["FILIAL_NOME"].map(_filial_to_uf) == estado]

        lista_lojas = sorted(_ml["NOME"].dropna().unique().tolist())

        if not lista_lojas:
            st.warning("Nenhuma loja ativa encontrada para os filtros selecionados.")
            st.stop()

        loja_matriz = st.selectbox("Loja", lista_lojas, key="loja_sel")
        _ml_sel = _ml[_ml["NOME"] == loja_matriz].copy()

        # Acumuladores loja
        _lp_q1 = _lp_q2 = _lp_q3 = _lp_q4 = 0.0
        _n_prod_loja = len(_ml_sel)
        _bpct_loja   = (100 / _n_prod_loja) if _n_prod_loja > 0 else 0

        # Resumo trimestral (placeholder, preenchido pós-loop)
        lcol_q1, lcol_q2, lcol_q3, lcol_q4, lcol_qf = st.columns(5)

        # Loop de produtos (loja)
        for _, _lrow in _ml_sel.iterrows():
            _lprod  = _lrow["PRODUTO"]
            _ljan   = _lrow["JAN"];  _lfev = _lrow["FEV"];  _lmar = _lrow["MAR"]
            _labr   = _lrow["ABR"];  _lmai = _lrow["MAI"];  _ljun = _lrow["JUN"]
            _ljul   = _lrow["JUL"];  _lago = _lrow["AGO"];  _lset = _lrow["SET"]
            _lout   = _lrow["OUT"];  _lnov = _lrow["NOV"];  _ldez = _lrow["DEZ"]
            _ltotal = _lrow["TOTAL"]

            _lr_jan = buscar_realizado_loja(loja_matriz, _lprod, 1)
            _lr_fev = buscar_realizado_loja(loja_matriz, _lprod, 2)
            _lr_mar = buscar_realizado_loja(loja_matriz, _lprod, 3)
            _lr_abr = buscar_realizado_loja(loja_matriz, _lprod, 4)
            _lr_mai = buscar_realizado_loja(loja_matriz, _lprod, 5)
            _lr_jun = buscar_realizado_loja(loja_matriz, _lprod, 6)
            _lr_jul = buscar_realizado_loja(loja_matriz, _lprod, 7)
            _lr_ago = buscar_realizado_loja(loja_matriz, _lprod, 8)
            _lr_set = buscar_realizado_loja(loja_matriz, _lprod, 9)
            _lr_out = buscar_realizado_loja(loja_matriz, _lprod, 10)
            _lr_nov = buscar_realizado_loja(loja_matriz, _lprod, 11)
            _lr_dez = buscar_realizado_loja(loja_matriz, _lprod, 12)

            _lmq1 = _ljan + _lfev + _lmar
            _lmq2 = _labr + _lmai + _ljun
            _lmq3 = _ljul + _lago + _lset
            _lmq4 = _lout + _lnov + _ldez

            _lrq1 = _lr_jan + _lr_fev + _lr_mar
            _lrq2 = _lr_abr + _lr_mai + _lr_jun
            _lrq3 = _lr_jul + _lr_ago + _lr_set
            _lrq4 = _lr_out + _lr_nov + _lr_dez

            with st.expander(f"{_lprod}"):
                st.markdown(f"### {_lprod}")

                _l_is_mon = _lprod in ["IMPLEMENTO", "USADOS"]
                if _l_is_mon:
                    _lfmt = lambda x: (
                        "R$ " + f"{round(x):,}".replace(",", ".")
                        if pd.notna(x) else ""
                    )
                else:
                    _lfmt = lambda x: f"{x:.0f}" if pd.notna(x) else ""

                def _lhigh(col):
                    if col.name in ["1 TRI", "2 TRI", "3 TRI", "4 TRI"]:
                        return [
                            "background-color: #d6d6d6; color: black; font-weight: bold"
                        ] * len(col)
                    return [""] * len(col)

                _l17 = [
                    "Jan", "Fev", "Mar", "1 TRI",
                    "Abr", "Mai", "Jun", "2 TRI",
                    "Jul", "Ago", "Set", "3 TRI",
                    "Out", "Nov", "Dez", "4 TRI", "TOTAL",
                ]
                _lcol_cfg = {
                    c: st.column_config.TextColumn(c, width="small") for c in _l17
                }

                st.markdown("#### Meta")
                _lmeta_df = pd.DataFrame({
                    "Jan": [_ljan],  "Fev": [_lfev],  "Mar": [_lmar],  "1 TRI": [_lmq1],
                    "Abr": [_labr],  "Mai": [_lmai],  "Jun": [_ljun],  "2 TRI": [_lmq2],
                    "Jul": [_ljul],  "Ago": [_lago],  "Set": [_lset],  "3 TRI": [_lmq3],
                    "Out": [_lout],  "Nov": [_lnov],  "Dez": [_ldez],  "4 TRI": [_lmq4],
                    "TOTAL": [_ltotal],
                })
                st.dataframe(
                    _lmeta_df.style.format(_lfmt).apply(_lhigh, axis=0),
                    use_container_width=True, hide_index=True, column_config=_lcol_cfg,
                )

                st.markdown("#### Realizado")
                _lreal_df = pd.DataFrame({
                    "Jan": [_lr_jan], "Fev": [_lr_fev], "Mar": [_lr_mar], "1 TRI": [_lrq1],
                    "Abr": [_lr_abr], "Mai": [_lr_mai], "Jun": [_lr_jun], "2 TRI": [_lrq2],
                    "Jul": [_lr_jul], "Ago": [_lr_ago], "Set": [_lr_set], "3 TRI": [_lrq3],
                    "Out": [_lr_out], "Nov": [_lr_nov], "Dez": [_lr_dez], "4 TRI": [_lrq4],
                    "TOTAL": [_lrq1 + _lrq2 + _lrq3 + _lrq4],
                })
                st.dataframe(
                    _lreal_df.style.format(_lfmt).apply(_lhigh, axis=0),
                    use_container_width=True, hide_index=True, column_config=_lcol_cfg,
                )

                st.markdown("#### Diferença")
                _ldif_df = (
                    _lreal_df.iloc[0]
                    .subtract(_lmeta_df.iloc[0], fill_value=0)
                    .to_frame().T.reset_index(drop=True)
                )
                st.dataframe(
                    _ldif_df.style.format(_lfmt).apply(_lhigh, axis=0),
                    use_container_width=True, hide_index=True, column_config=_lcol_cfg,
                )

                def _lcalc(real, meta):
                    if pd.isna(real) or pd.isna(meta): return 0.0
                    if meta <= 0 or real < meta: return 0.0
                    return _bpct_loja + _bpct_loja * min((real - meta) / meta, 1.0) * 0.20

                _lpq1 = _lcalc(_lrq1, _lmq1)
                _lpq2 = _lcalc(_lrq2, _lmq2)
                _lpq3 = _lcalc(_lrq3, _lmq3)
                _lpq4 = _lcalc(_lrq4, _lmq4)

                _lp_q1 += _lpq1
                _lp_q2 += _lpq2
                _lp_q3 += _lpq3
                _lp_q4 += _lpq4

                _lpontos = _lpq1 + _lpq2 + _lpq3 + _lpq4
                pontuacao_produtos.append({"produto": _lprod, "pontuacao": _lpontos})

                st.markdown("### Pontuação por Trimestre")
                _lsc = st.columns([4, 4, 4, 4, 1])
                for _lc, _ll, _lv in zip(
                    _lsc,
                    ["Q1", "Q2", "Q3", "Q4", "TOTAL"],
                    [_lpq1, _lpq2, _lpq3, _lpq4, _lpontos],
                ):
                    with _lc:
                        st.metric(_ll, f"{_lv:.1f}%")

        # Preencher resumo trimestral
        with lcol_q1: st.metric("Q1",    f"{_lp_q1:.1f}%")
        with lcol_q2: st.metric("Q2",    f"{_lp_q2:.1f}%")
        with lcol_q3: st.metric("Q3",    f"{_lp_q3:.1f}%")
        with lcol_q4: st.metric("Q4",    f"{_lp_q4:.1f}%")
        with lcol_qf: st.metric("FINAL", "0")

        # Ranking de lojas
        st.markdown("---")
        mostrar_ranking = st.checkbox(
            "🏆 Mostrar ranking de lojas", value=False, key="ranking_lojas"
        )
        if mostrar_ranking:
            st.markdown("### 🏆 Ranking de Lojas")
            _mes_atual = pd.Timestamp.today().month
            _ranking_rows_l = []

            for _lnome in sorted(_ml["NOME"].dropna().unique()):
                _lml_r = _ml[_ml["NOME"] == _lnome]
                _ln_r  = len(_lml_r)
                if _ln_r == 0:
                    continue
                _lb_r  = 100 / _ln_r
                _lpq1r = _lpq2r = _lpq3r = _lpq4r = 0.0

                for _, _lr in _lml_r.iterrows():
                    _lrp   = _lr["PRODUTO"]
                    _lrmq1 = _lr["JAN"] + _lr["FEV"] + _lr["MAR"]
                    _lrmq2 = _lr["ABR"] + _lr["MAI"] + _lr["JUN"]
                    _lrmq3 = _lr["JUL"] + _lr["AGO"] + _lr["SET"]
                    _lrmq4 = _lr["OUT"] + _lr["NOV"] + _lr["DEZ"]
                    _lrrq1 = sum(buscar_realizado_loja(_lnome, _lrp, m) for m in [1, 2, 3])
                    _lrrq2 = sum(buscar_realizado_loja(_lnome, _lrp, m) for m in [4, 5, 6])
                    _lrrq3 = sum(buscar_realizado_loja(_lnome, _lrp, m) for m in [7, 8, 9])
                    _lrrq4 = sum(buscar_realizado_loja(_lnome, _lrp, m) for m in [10, 11, 12])

                    def _lrs(real, meta, base):
                        if pd.isna(real) or pd.isna(meta): return 0.0
                        if meta == 0:  return base           # meta zerada = já batida
                        if real < meta: return 0.0
                        return base + base * min((real - meta) / meta, 1.0) * 0.20

                    _lpq1r += _lrs(_lrrq1, _lrmq1, _lb_r)
                    _lpq2r += _lrs(_lrrq2, _lrmq2, _lb_r) if _mes_atual >= 4  else 0
                    _lpq3r += _lrs(_lrrq3, _lrmq3, _lb_r) if _mes_atual >= 7  else 0
                    _lpq4r += _lrs(_lrrq4, _lrmq4, _lb_r) if _mes_atual >= 10 else 0

                _lq1p = round(_lpq1r, 1)
                _lq2p = round(_lpq2r, 1)
                _lq3p = round(_lpq3r, 1)
                _lq4p = round(_lpq4r, 1)

                _lvs = (
                    [_lq1p] * int(_mes_atual >= 1)
                    + [_lq2p] * int(_mes_atual >= 4)
                    + [_lq3p] * int(_mes_atual >= 7)
                    + [_lq4p] * int(_mes_atual >= 10)
                )
                _lmed = round(sum(_lvs) / len(_lvs), 1) if _lvs else 0

                _ranking_rows_l.append({
                    "Loja":  _lnome,
                    "Q1 %":  _lq1p,
                    "Q2 %":  _lq2p,
                    "Q3 %":  _lq3p,
                    "Q4 %":  _lq4p,
                    "Média": _lmed,
                })

            if _ranking_rows_l:
                _df_rk_l = pd.DataFrame(_ranking_rows_l)
                _rkl_col, _ = st.columns([2, 5])
                with _rkl_col:
                    _rk_sort_l = st.selectbox(
                        "Ordenar por",
                        ["Média", "Q1 %", "Q2 %", "Q3 %", "Q4 %"],
                        index=0,
                        key="rk_sort_loja",
                    )
                _df_rk_l = (
                    _df_rk_l
                    .sort_values(_rk_sort_l, ascending=False)
                    .reset_index(drop=True)
                )
                _df_rk_l.index += 1
                _df_rk_l.index.name = "Pos"
                _tabela(
                    _df_rk_l,
                    key="tv_rk_loja",
                    show_index=True,
                    pct_cols=("Q1 %", "Q2 %", "Q3 %", "Q4 %", "Média"),
                )
            else:
                st.info("Nenhuma loja encontrada para os filtros selecionados.")

    else:

        # ── MODO CONSULTOR ─────────────────────────────────────────────────────

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

        _mes_hoje = pd.Timestamp.today().month
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
        _base_pct  = (100 / n_produtos) if n_produtos > 0 else 0  # % base por produto

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
                    if pd.isna(meta): return 0.0          # período sem meta definida
                    if meta == 0: return _base_pct         # meta zerada = já batida
                    if real < meta: return 0.0
                    excess_ratio = min((real - meta) / meta, 1.0)
                    return _base_pct + _base_pct * excess_ratio * 0.20

                # =========================
                # PONTUAÇÃO POR TRIMESTRE
                # =========================
                p_q1 = calc_ponto(real_q1, meta_q1)
                p_q2 = calc_ponto(real_q2, meta_q2) if _mes_hoje >= 4  else 0.0
                p_q3 = calc_ponto(real_q3, meta_q3) if _mes_hoje >= 7  else 0.0
                p_q4 = calc_ponto(real_q4, meta_q4) if _mes_hoje >= 10 else 0.0

                total_p_q1 += p_q1
                total_p_q2 += p_q2
                total_p_q3 += p_q3
                total_p_q4 += p_q4

                pontuacao_total_produto = p_q1 + p_q2 + p_q3 + p_q4

                pontuacao_produtos.append({
                    "produto": produto,
                    "pontuacao": pontuacao_total_produto
                })

                pontos_total = p_q1 + p_q2 + p_q3 + p_q4

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
                        st.metric(_lbl, f"{_val:.1f}%")
          
        # =====================================================
        # PONTUAÇÃO PONDERADA POR TRIMESTRE (calculada pós-loop)
        # =====================================================
        # Máximo por trimestre = n_produtos × 10 pts
        # q_final = (pontos_obtidos / máximo) × 100
        # total_p_qN já acumula % direto (soma das pontuações por produto no trimestre)
        q1_final = total_p_q1
        q2_final = total_p_q2
        q3_final = total_p_q3
        q4_final = total_p_q4

        with col_q1:
            st.metric("Q1", f"{q1_final:.1f}%")

        with col_q2:
            st.metric("Q2", f"{q2_final:.1f}%")

        with col_q3:
            st.metric("Q3", f"{q3_final:.1f}%")

        with col_q4:
            st.metric("Q4", f"{q4_final:.1f}%")

        with col_qf:
            st.metric("FINAL", "0")

        # =====================================================
        # RANKING DE CONSULTORES
        # =====================================================
        st.markdown("---")
        mostrar_ranking = st.checkbox(
            "🏆 Mostrar ranking de consultores", value=False
        )

        if mostrar_ranking:
            st.markdown("### 🏆 Ranking de Consultores")

            # Trimestres que já iniciaram (para calcular a média)
            _mes_atual = pd.Timestamp.today().month

            _ranking_rows = []
            for _rk_cons in sorted(matriz["CONSULTOR"].dropna().unique()):
                _rk_mc = matriz[matriz["CONSULTOR"] == _rk_cons]
                _rk_n  = len(_rk_mc)
                if _rk_n == 0:
                    continue

                _rk_base = (100 / _rk_n) if _rk_n > 0 else 0
                _rk_pq1 = _rk_pq2 = _rk_pq3 = _rk_pq4 = 0.0

                for _, _rk_row in _rk_mc.iterrows():
                    _rk_prod = _rk_row["PRODUTO"]
                    _rk_mq1  = _rk_row["JAN"] + _rk_row["FEV"] + _rk_row["MAR"]
                    _rk_mq2  = _rk_row["ABR"] + _rk_row["MAI"] + _rk_row["JUN"]
                    _rk_mq3  = _rk_row["JUL"] + _rk_row["AGO"] + _rk_row["SET"]
                    _rk_mq4  = _rk_row["OUT"] + _rk_row["NOV"] + _rk_row["DEZ"]
                    _rk_rq1  = sum(buscar_realizado(_rk_cons, _rk_prod, m) for m in [1, 2, 3])
                    _rk_rq2  = sum(buscar_realizado(_rk_cons, _rk_prod, m) for m in [4, 5, 6])
                    _rk_rq3  = sum(buscar_realizado(_rk_cons, _rk_prod, m) for m in [7, 8, 9])
                    _rk_rq4  = sum(buscar_realizado(_rk_cons, _rk_prod, m) for m in [10, 11, 12])

                    def _rk_score(real, meta, base):
                        if pd.isna(real) or pd.isna(meta): return 0.0
                        if meta == 0:  return base           # meta zerada = já batida
                        if real < meta: return 0.0
                        return base + base * min((real - meta) / meta, 1.0) * 0.20

                    _rk_pq1 += _rk_score(_rk_rq1, _rk_mq1, _rk_base)
                    _rk_pq2 += _rk_score(_rk_rq2, _rk_mq2, _rk_base) if _mes_atual >= 4  else 0
                    _rk_pq3 += _rk_score(_rk_rq3, _rk_mq3, _rk_base) if _mes_atual >= 7  else 0
                    _rk_pq4 += _rk_score(_rk_rq4, _rk_mq4, _rk_base) if _mes_atual >= 10 else 0

                _rk_filial = (
                    _rk_mc["Filial"].dropna().iloc[0]
                    if not _rk_mc["Filial"].dropna().empty else "-"
                )

                _rk_q1pct = round(_rk_pq1, 1)
                _rk_q2pct = round(_rk_pq2, 1)
                _rk_q3pct = round(_rk_pq3, 1)
                _rk_q4pct = round(_rk_pq4, 1)

                # Média apenas dos trimestres já iniciados
                _rk_vals = (
                    [_rk_q1pct] * int(_mes_atual >= 1)
                    + [_rk_q2pct] * int(_mes_atual >= 4)
                    + [_rk_q3pct] * int(_mes_atual >= 7)
                    + [_rk_q4pct] * int(_mes_atual >= 10)
                )
                _rk_media = round(sum(_rk_vals) / len(_rk_vals), 1) if _rk_vals else 0

                _ranking_rows.append({
                    "Consultor": _rk_cons,
                    "Filial":    _rk_filial,
                    "Q1 %":      _rk_q1pct,
                    "Q2 %":      _rk_q2pct,
                    "Q3 %":      _rk_q3pct,
                    "Q4 %":      _rk_q4pct,
                    "Média":     _rk_media,
                })

            if _ranking_rows:
                _df_rk = pd.DataFrame(_ranking_rows)

                # Ordenação por trimestre (dropdown compacto)
                _rk_col, _ = st.columns([2, 5])
                with _rk_col:
                    _rk_sort = st.selectbox(
                        "Ordenar por",
                        ["Média", "Q1 %", "Q2 %", "Q3 %", "Q4 %"],
                        index=0,
                        key="rk_sort_col",
                    )

                _df_rk = (
                    _df_rk
                    .sort_values(_rk_sort, ascending=False)
                    .reset_index(drop=True)
                )
                _df_rk.index += 1
                _df_rk.index.name = "Pos"

                _tabela(
                    _df_rk,
                    key="tv_rk_consultor",
                    show_index=True,
                    pct_cols=("Q1 %", "Q2 %", "Q3 %", "Q4 %", "Média"),
                )
            else:
                st.info("Nenhum consultor encontrado para os filtros selecionados.")

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
        _tabela(
            tabela_funil.rename(columns={COL_RAZAO: "Razão do Status", "Quantidade": "Qtd"}),
            key="tv_funil",
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

            # O relatório tem uma linha por produto: o total de barras conta
            # produtos, não oportunidades. Explicita os dois para o número
            # poder ser reconciliado com o card de oportunidades em aberto.
            _n_opp_prod = rel_funil[COL_OPP_ID].nunique()
            st.caption(
                f"{format_br(grand_total_prod)} produtos em "
                f"{format_br(_n_opp_prod)} oportunidades em aberto — "
                "uma oportunidade pode ter mais de um produto."
            )

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

            # Gráfico à esquerda, quantitativos à direita
            _c_graf, _c_qtd = st.columns([2.2, 1])

            with _c_graf:
                st.altair_chart(chart_prod + text_prod, use_container_width=True)

            with _c_qtd:
                # Produto (coluna AI) e Tipo de Adicional (coluna AV) são
                # complementares no relatório: máquina preenche uma,
                # implemento/acessório preenche a outra.
                for _titulo, _coluna in [
                    ("Produtos", "Produto"),
                    ("Tipos de Adicional", "Tipo de Adicional"),
                ]:
                    _b = rel_funil[[_coluna, "Valor do Item"]].copy()
                    _b[_coluna] = _b[_coluna].astype(str).str.strip()
                    _b = _b[_b[_coluna].notna() & ~_b[_coluna].isin(["", "nan", "None"])]

                    st.markdown(f"**{_titulo}**")
                    if _b.empty:
                        st.caption("Nenhum registro para os filtros atuais.")
                        continue

                    # Volume financeiro = preço x quantidade da linha de produto
                    # (Valor Total é da oportunidade e duplicaria entre produtos).
                    _tab = (
                        _b.groupby(_coluna)
                        .agg(Qtd=("Valor do Item", "size"),
                             Volume=("Valor do Item", "sum"))
                        .reset_index()
                        .sort_values("Qtd", ascending=False)
                    )
                    _tab["%"] = (_tab["Qtd"] / _tab["Qtd"].sum() * 100).round(1)
                    _tab = _tab[[_coluna, "Qtd", "%", "Volume"]]

                    st.dataframe(
                        _tab,
                        hide_index=True,
                        use_container_width=True,
                        height=min(320, 38 + 35 * len(_tab)),
                        column_config={
                            "Qtd": st.column_config.NumberColumn(width="small"),
                            "%":   st.column_config.NumberColumn(
                                format="%.1f%%", width="small"
                            ),
                            "Volume": st.column_config.NumberColumn(
                                "Volume R$", format="R$ %.0f"
                            ),
                        },
                    )
                    st.caption(
                        f"Total: {format_br(int(_tab['Qtd'].sum()))} itens · "
                        f"R$ {format_br(int(_tab['Volume'].sum()))}"
                    )

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

        # Listas de filiais e regiões vindas do território (já normalizadas)
        _terr_adm      = load_territorio()
        _opcoes_filial = sorted(_terr_adm["Filial"].dropna().unique())
        _opcoes_regiao = sorted(_terr_adm["Região"].dropna().unique())

        # ── Criação de novo usuário ───────────────────────
        with st.expander("➕ Criar novo usuário", expanded=False):
            with st.form("_fnovo_usuario", clear_on_submit=True):
                _na, _nb = st.columns(2)
                _novo_email = _na.text_input(
                    "E-mail *", placeholder="usuario@pmemaquinas.com.br"
                )
                _novo_nome_u = _nb.text_input("Nome *", placeholder="Fulano")

                _nc, _nd = st.columns(2)
                _nova_senha_u = _nc.text_input("Senha *", type="password")
                _novo_perfil_u = _nd.selectbox(
                    "Perfil",
                    options=["admin", "geral", "filial_restrita", "divisao"],
                    format_func=lambda x: _perfil_labels.get(x, x),
                    index=1,
                )

                _ne, _nf = st.columns(2)
                _nova_filial_u = _ne.multiselect(
                    "Filial Restrita", options=_opcoes_filial,
                    help="Use apenas com o perfil 📍 Filial Restrita",
                )
                _nova_regiao_u = _nf.selectbox(
                    "Região Restrita", options=["—"] + _opcoes_regiao, index=0,
                    help="Use apenas com o perfil 🗺️ Divisão",
                )

                _btn_criar = st.form_submit_button(
                    "➕ Criar usuário", use_container_width=True, type="primary"
                )

                if _btn_criar:
                    _email_novo = _novo_email.strip().lower()
                    if not _email_novo or not _novo_nome_u.strip() or not _nova_senha_u:
                        st.error("Preencha e-mail, nome e senha.")
                    elif "@" not in _email_novo:
                        st.error("E-mail inválido.")
                    elif _email_novo in _db:
                        st.error(f"O usuário **{_email_novo}** já existe.")
                    else:
                        _novo_reg = {
                            "senha":           _nova_senha_u,
                            "perfil":          _novo_perfil_u,
                            "nome":            _novo_nome_u.strip(),
                            "filial_restrita": ",".join(_nova_filial_u) or None,
                            "regiao_restrita": (
                                None if _nova_regiao_u == "—" else _nova_regiao_u
                            ),
                            "ultimo_acesso":   None,
                        }
                        _db[_email_novo] = _novo_reg
                        _gravou = _save_usuarios(_db)
                        st.session_state["_novo_user_msg"] = (
                            _email_novo, _gravou, _toml_usuario(_email_novo, _novo_reg)
                        )

        # Resultado da criação — fora do expander para ficar sempre visível
        _msg = st.session_state.pop("_novo_user_msg", None)
        if _msg:
            _em, _gravou, _toml = _msg
            st.success(f"✅ Usuário **{_em}** criado.")
            if _usuarios_via_secrets() or not _gravou:
                st.warning(
                    "Este ambiente lê os usuários dos **Secrets** do Streamlit "
                    "Cloud, então a criação acima vale só até o app reiniciar. "
                    "Para tornar permanente, cole o bloco abaixo em "
                    "**Manage app → Settings → Secrets**:"
                )
                st.code(_toml, language="toml")

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
                    _filiais_atuais = [
                        f for f in (_udata.get("filial_restrita") or "").split(",")
                        if f in _opcoes_filial
                    ]
                    _nova_filial_r = _fc.multiselect(
                        "Filial Restrita",
                        options=_opcoes_filial,
                        default=_filiais_atuais,
                    )
                    _regiao_atual = _udata.get("regiao_restrita") or "—"
                    _nova_regiao_r = _fd.selectbox(
                        "Região Restrita",
                        options=["—"] + _opcoes_regiao,
                        index=(
                            (["—"] + _opcoes_regiao).index(_regiao_atual)
                            if _regiao_atual in (["—"] + _opcoes_regiao) else 0
                        ),
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
                            ",".join(_nova_filial_r) or None
                        )
                        _db[_uemail]["regiao_restrita"] = (
                            None if _nova_regiao_r == "—" else _nova_regiao_r
                        )
                        if _nova_senha:
                            _db[_uemail]["senha"] = _nova_senha
                        _gravou_ed = _save_usuarios(_db)
                        st.success(
                            f"✅ Usuário **{_uemail}** atualizado com sucesso!"
                        )
                        if _usuarios_via_secrets() or not _gravou_ed:
                            st.warning(
                                "Alteração temporária — este ambiente lê os "
                                "usuários dos **Secrets**. Atualize o bloco "
                                "abaixo em **Manage app → Settings → Secrets**:"
                            )
                            st.code(
                                _toml_usuario(_uemail, _db[_uemail]),
                                language="toml",
                            )

            st.divider()