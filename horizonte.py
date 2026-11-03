"""
Projeto Horizonte — opção "Vendas realizadas" da aba Resumo em Mapas.

Chamado por app.py: usa os mesmos filtros da barra lateral (Região, Filial,
Estado, Status, Vendedor) e as mesmas funções de apoio (card, _tabela).
"""
import pandas as pd
import streamlit as st

ARQ_VENDAS = "dados/horizonte_vendas_gv.xlsx"

COR_FORA    = "#C62828"   # vermelho, mesmo da Matriz de Performance
COR_BORDA   = "#0D47A1"
FAIXAS_AZUL = ["#BBDEFB", "#64B5F6", "#1E88E5", "#1565C0", "#0D47A1"]
FAIXAS_NOME = ["Muito baixo", "Baixo", "Médio", "Alto", "Muito alto"]


def _fmt(v):
    return f"{v:,.0f}".replace(",", ".")


def _brl(v):
    return "R$ " + _fmt(v)


def _mi(v):
    if v >= 1_000_000:
        return f"R$ {v / 1_000_000:.1f} mi".replace(".", ",")
    if v >= 1_000:
        return f"R$ {v / 1_000:.0f} mil"
    return _brl(v)


@st.cache_data
def _ler_vendas(_assinatura, _normalizar):
    df = pd.read_excel(ARQ_VENDAS, sheet_name="GV")
    df = df.rename(columns={
        "Vendedor": "NOME BI",
        "Vl NFVenda": "Valor",
        "Segmento Maq": "Segmento",
        "CPF": "Documento",
    })
    df["NOME BI"] = _normalizar(df["NOME BI"])
    df["Cliente"] = df["Cliente"].astype(str).str.strip()
    df["Documento"] = df["Documento"].fillna("").astype(str).str.strip()
    df["CD_MUN"] = (
        pd.to_numeric(df["IBGE"], errors="coerce")
        .astype("Int64").astype("string").str.strip()
    )
    df["Ano"] = df["Ano"].astype(str)
    df["Quantidade"] = pd.to_numeric(df["Quantidade"], errors="coerce").fillna(0)
    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0)
    df["Segmento"] = df["Segmento"].fillna("").astype(str).str.strip().str.title()
    return df


def carregar_vendas(assinatura, normalizar):
    return _ler_vendas(assinatura, normalizar)


def anos_disponiveis(vendas):
    return sorted(vendas["Ano"].dropna().unique(), reverse=True)


def renderizar(*, vendas, periodo, territorio, gdf_mun, filial_do_consultor,
               status_do_consultor, regiao, filial, estado, status_filtro,
               vendedor, filiais_restritas, regiao_restrita, mostrar_dados,
               card, tabela):
    """Desenha cards, mapa e tabelas das vendas realizadas."""
    import folium
    from streamlit_folium import st_folium

    # ── Atributos do vendedor (Filial/Região/Estado/Status) ───────────────
    # Mesma origem do painel de oportunidades: território + metas.
    ter = territorio.copy()
    ter["Código IBGE"] = ter["Código IBGE"].astype(str).str.strip()

    ter_filial = (
        ter.groupby("Filial")[["Região", "UF"]]
        .agg(lambda s: s.mode().iat[0]).reset_index()
    )
    bi_para_crm = dict(zip(ter["NOME BI"], ter["NOME CRM"]))

    # Filial do município (usada quando o vendedor não tem filial em metas)
    mun_filial = (
        ter.drop_duplicates(subset=["Código IBGE"])
        .set_index("Código IBGE")["Filial"].to_dict()
    )

    v = vendas.copy()
    v["Filial"] = v["NOME BI"].map(filial_do_consultor)
    v["Filial"] = v["Filial"].fillna(v["CD_MUN"].map(mun_filial))
    v = v.merge(ter_filial.rename(columns={"UF": "Estado"}), on="Filial", how="left")
    v["Vendedor"] = v["NOME BI"].map(bi_para_crm).fillna(v["NOME BI"])
    v["Status"] = v["NOME BI"].map(status_do_consultor)

    # ── Filtros da barra lateral ─────────────────────────────────────────
    if filiais_restritas:
        v = v[v["Filial"].isin(filiais_restritas)]
    elif regiao_restrita:
        v = v[v["Região"] == regiao_restrita]
    if regiao != "Todas":
        v = v[v["Região"] == regiao]
    if filial != "Todas":
        v = v[v["Filial"] == filial]
    if estado != "Todos":
        v = v[v["Estado"] == estado]
    if status_filtro == "Ativos":
        v = v[v["Status"] == "ATIVO"]
    elif status_filtro == "Inativos":
        v = v[v["Status"] == "INATIVO"]
    if vendedor != "Todos":
        v = v[(v["Vendedor"] == vendedor) | (v["NOME BI"] == vendedor)]
    if periodo != "Todos":
        v = v[v["Ano"] == periodo]
    v = v.copy()

    if v.empty:
        st.info("Nenhuma venda encontrada para os filtros selecionados.")
        return

    # Dentro/fora: município pertence ao território da filial do vendedor
    terr_por_filial = ter.groupby("Filial")["Código IBGE"].agg(set).to_dict()
    v["Dentro"] = [
        (m in terr_por_filial.get(f, set())) if pd.notna(m) else False
        for m, f in zip(v["CD_MUN"], v["Filial"])
    ]
    sem_mun = v["CD_MUN"].isna()
    v_mapa = v[~sem_mun]

    # ── Cards ────────────────────────────────────────────────────────────
    c1, c2 = st.columns(2)
    with c1:
        card("Faturamento (Total)", _brl(v["Valor"].sum()))
    with c2:
        card("Unidades vendidas", _fmt(v["Quantidade"].sum()))
    c3, c4, c5 = st.columns(3)
    with c3:
        card("Clientes", _fmt(v["Cliente"].nunique()))
    with c4:
        card("Municípios com venda", _fmt(v_mapa["CD_MUN"].nunique()))
    with c5:
        card(
            "Fora do território",
            _fmt(v_mapa.loc[~v_mapa["Dentro"], "CD_MUN"].nunique()),
        )

    # ── Agregação por município ──────────────────────────────────────────
    por_mun = (
        v_mapa.groupby("CD_MUN")
        .agg(
            Faturamento=("Valor", "sum"),
            Unidades=("Quantidade", "sum"),
            Clientes=("Cliente", "nunique"),
            Vendedores=("Vendedor", lambda s: ", ".join(sorted(s.dropna().unique()))),
            Filial=("Filial", "first"),
            Região=("Região", "first"),
            Dentro=("Dentro", "min"),
        )
        .reset_index()
    )
    seg_mun = v_mapa.groupby(["CD_MUN", "Segmento"])["Valor"].sum().reset_index()

    mapa = gdf_mun[["CD_MUN", "NM_MUN", "SIGLA_UF", "geometry"]].merge(
        por_mun, on="CD_MUN", how="inner"
    )
    mapa_geo = mapa.to_crs(epsg=4326)

    # Faixas por quartil (5 classes) só entre os municípios dentro do território
    mapa_geo["Faixa"] = -1
    dentro = mapa_geo[mapa_geo["Dentro"]]
    if not dentro.empty:
        pct = dentro["Faturamento"].rank(method="first", pct=True)
        mapa_geo.loc[dentro.index, "Faixa"] = pd.cut(
            pct, bins=[0, .2, .4, .6, .8, 1.0], labels=False, include_lowest=True
        ).astype(int)

    # ── Mapa ─────────────────────────────────────────────────────────────
    ter_ibge = set().union(*(terr_por_filial.get(f, set()) for f in v["Filial"].dropna().unique()))
    geo_terr = gdf_mun[gdf_mun["CD_MUN"].isin(ter_ibge)].to_crs(epsg=4326)
    base = geo_terr if not geo_terr.empty else mapa_geo
    b = base.total_bounds
    centro = [(b[1] + b[3]) / 2, (b[0] + b[2]) / 2]
    # Centro e zoom fixos: o fit_bounds é desfeito pelo st_folium ao redesenhar
    zoom = 7 if (b[2] - b[0]) < 6 else 5

    m = folium.Map(location=centro, zoom_start=zoom, tiles="OpenStreetMap")

    if not geo_terr.empty:
        # buffer +/- fecha frestas entre vizinhos e evita linhas internas
        contorno = geo_terr.geometry.buffer(0.01).union_all().buffer(-0.01)
        folium.GeoJson(
            contorno,
            style_function=lambda x: {
                "fillColor": "none", "color": COR_BORDA, "weight": 3,
                "dashArray": "6 4", "fillOpacity": 0,
            },
            interactive=False,
        ).add_to(m)

    if mostrar_dados:
        for _, row in mapa_geo.iterrows():
            segs = (
                seg_mun[seg_mun["CD_MUN"] == row["CD_MUN"]]
                .sort_values("Valor", ascending=False)
            )
            seg_txt = "<br>".join(
                f"&nbsp;&nbsp;{r.Segmento}: {_mi(r.Valor)}" for r in segs.itertuples()
            )
            situacao = "Dentro do território" if row["Dentro"] else "⚠ Fora do território"
            tooltip = f"""
            <b>Município:</b> {row['NM_MUN']}<br>
            <b>UF:</b> {row['SIGLA_UF']}<br>
            <b>Situação:</b> {situacao}<br>
            <b>Vendedor:</b> {row['Vendedores']}<br>
            <b>Faturamento:</b> {_brl(row['Faturamento'])}<br>
            <b>Unidades:</b> {_fmt(row['Unidades'])}<br>
            <b>Clientes:</b> {int(row['Clientes'])}<br>
            <b>Por segmento:</b><br>{seg_txt}
            """
            cor = FAIXAS_AZUL[int(row["Faixa"])] if row["Dentro"] else COR_FORA
            folium.GeoJson(
                row["geometry"],
                style_function=lambda x, c=cor: {
                    "fillColor": c, "color": "#333", "weight": 1, "fillOpacity": 0.65,
                },
                tooltip=tooltip,
            ).add_to(m)

    st_folium(m, width=None, height=650, center=centro, zoom=zoom, returned_objects=[])

    chips = "".join(
        f"<span><span style='display:inline-block;width:12px;height:12px;"
        f"background:{c};border-radius:2px;margin-right:4px;'></span>{n}</span>"
        for c, n in zip(FAIXAS_AZUL, FAIXAS_NOME)
    )
    st.markdown(
        "<div style='display:flex;flex-wrap:wrap;gap:20px;margin-top:6px;font-size:14px;'>"
        f"<span><b>Faturamento por município:</b></span>{chips}"
        f"<span><span style='display:inline-block;width:12px;height:12px;"
        f"background:{COR_FORA};border-radius:2px;margin-right:4px;'></span>"
        "Fora do território</span></div>",
        unsafe_allow_html=True,
    )

    n_sem = int(sem_mun.sum())
    if n_sem:
        st.caption(
            f"ℹ️ {n_sem} venda(s) sem município identificado não aparecem no mapa, "
            "mas entram nos cards e no descritivo."
        )

    # ── Tabela de municípios ─────────────────────────────────────────────
    tab_mun = mapa[
        ["NM_MUN", "SIGLA_UF", "Filial", "Região", "Vendedores", "Faturamento",
         "Unidades", "Clientes", "Dentro"]
    ].copy()
    tab_mun["Dentro"] = tab_mun["Dentro"].map({True: "Dentro", False: "Fora"})
    tab_mun.columns = [
        "Município", "UF", "Filial", "Região", "Vendedor", "Faturamento",
        "Unidades", "Clientes", "Território",
    ]
    tab_mun["Faturamento"] = tab_mun["Faturamento"].round(0).astype(int)
    tab_mun["Unidades"] = tab_mun["Unidades"].astype(int)
    tab_mun = tab_mun.sort_values("Faturamento", ascending=False)
    tabela(tab_mun, key="tv_vendas_municipios")

    # ── Descritivo ───────────────────────────────────────────────────────
    st.markdown("### Descritivo das Vendas")
    st.markdown(
        f"<span style='font-size:15px;'>Total de vendas: <b>{len(v):,}</b></span>"
        .replace(",", "."),
        unsafe_allow_html=True,
    )
    nomes = gdf_mun[["CD_MUN", "NM_MUN", "SIGLA_UF"]]
    desc = v.merge(nomes, on="CD_MUN", how="left")
    desc["Território"] = desc["Dentro"].map({True: "Dentro", False: "Fora"})
    desc.loc[desc["CD_MUN"].isna(), "Território"] = "Sem município"
    desc["Valor Total"] = desc["Valor"].apply(lambda x: _brl(round(x)))
    tab_desc = (
        desc[[
            "Ano Mes", "Cliente", "Documento", "NM_MUN", "SIGLA_UF", "Vendedor",
            "Filial", "Região", "Segmento", "Modelo", "Quantidade", "Valor Total",
            "Território",
        ]]
        .rename(columns={"Ano Mes": "Mês", "NM_MUN": "Município", "SIGLA_UF": "UF"})
        .sort_values("Mês", ascending=False)
    )
    tab_desc["Quantidade"] = tab_desc["Quantidade"].astype(int)
    tabela(tab_desc, key="tv_vendas_descritivo")
