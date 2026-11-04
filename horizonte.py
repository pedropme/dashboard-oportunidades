"""
Projeto Horizonte — opção "Vendas realizadas" da aba Resumo em Mapas.

Chamado por app.py: usa os mesmos filtros da barra lateral (Região, Filial,
Estado, Status, Vendedor) e as mesmas funções de apoio (card, _tabela).
"""
import pandas as pd
import streamlit as st

import analisadas

ARQ_VENDAS     = "dados/vendas.xlsx"   # empresa inteira, download diário
ARQ_CLIENTES   = "dados/clientes.xlsx" # de onde vem o município
ARQ_ANALISADAS = analisadas.ARQ        # municípios preenchidos à mão

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


def _municipio_por_cliente(_normalizar):
    """Nome do cliente no CRM -> (código IBGE, município, documento).

    Casamento por nome exato, depois de normalizar acento/caixa/espaço. Nome
    que aparece em mais de um município fica de fora: sem um critério para
    escolher, a venda entra como município não identificado em vez de ir
    para o lugar errado.
    """
    cli = pd.read_excel(ARQ_CLIENTES).rename(columns={
        "Nome da Conta": "Cliente",
        "Documento (BR: CPF/CNPJ)": "Documento",
        "CÓD": "CD_MUN",
        "Cidade": "Municipio",
    })
    cli["K"] = _normalizar(cli["Cliente"])
    cli["CD_MUN"] = cli["CD_MUN"].astype(str).str.strip()
    cli = cli[cli["CD_MUN"].str.fullmatch(r"\d{7}", na=False)]

    g = cli.groupby("K").agg(
        n_mun=("CD_MUN", "nunique"),
        CD_MUN=("CD_MUN", "first"),
        Municipio=("Municipio", "first"),
        Documento=("Documento", "first"),
    )
    return g[g["n_mun"] == 1]


@st.cache_data
def _ler_vendas(_assinatura, _normalizar):
    crm = _municipio_por_cliente(_normalizar)

    df = pd.read_excel(ARQ_VENDAS)
    # A marca de construção não faz parte deste painel.
    df = analisadas.apenas_agricola(df)
    df = df.rename(columns={
        "Vendedor": "NOME BI",
        "Vl NFVenda": "Valor",
        "Segmento Maq": "Segmento",
    })
    df["NOME BI"] = _normalizar(df["NOME BI"])
    df["Cliente"] = df["Cliente"].astype(str).str.strip()

    # As duas colunas que posicionam a venda no mapa, vindas do CRM.
    _k = _normalizar(df["Cliente"])
    df["CD_MUN"] = _k.map(crm["CD_MUN"]).astype("string")
    df["Municipio"] = _k.map(crm["Municipio"])
    df["Documento"] = _k.map(crm["Documento"]).fillna("").astype(str).str.strip()

    # O que o CRM não resolveu pode ter sido preenchido à mão na fila de
    # clientes a identificar — ali o preenchimento é a fonte da verdade.
    manual = analisadas.municipios_preenchidos()
    if manual:
        falta = df["CD_MUN"].isna()
        df.loc[falta, "CD_MUN"] = (
            _k[falta].map({k: v[0] for k, v in manual.items()}).astype("string")
        )
        df.loc[falta, "Municipio"] = (
            df.loc[falta, "Municipio"]
            .fillna(_k[falta].map({k: v[1] for k, v in manual.items()}))
        )

    return _padronizar(df)


def _padronizar(df):
    df["Ano"] = df["Ano"].astype(str).str.strip()
    df["Quantidade"] = pd.to_numeric(df["Quantidade"], errors="coerce").fillna(0)
    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0)
    df["Segmento"] = df["Segmento"].fillna("").astype(str).str.strip().str.title()
    for col in ("Ano Mes", "Modelo", "Municipio"):
        if col not in df.columns:
            df[col] = None
    return df[[
        "Ano", "Ano Mes", "Cliente", "Documento", "CD_MUN", "Municipio",
        "NOME BI", "Segmento", "Modelo", "Quantidade", "Valor",
    ]]


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
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        card("Faturamento (Total)", _brl(v["Valor"].sum()))
    with c2:
        card("Unidades vendidas", _fmt(v["Quantidade"].sum()))
    with c3:
        card("Clientes", _fmt(v["Cliente"].nunique()))
    with c4:
        card("Municípios com venda", _fmt(v_mapa["CD_MUN"].nunique()))
    with c5:
        card(
            "Fora do território",
            _fmt(v_mapa.loc[~v_mapa["Dentro"], "CD_MUN"].nunique()),
        )
    with c6:
        card(
            "Clientes sem município",
            _fmt(v.loc[sem_mun, "Cliente"].nunique()),
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
            f"ℹ️ {n_sem} venda(s), {_brl(v.loc[sem_mun, 'Valor'].sum())}, sem "
            "município identificado: o nome do cliente na base de vendas não "
            "encontrou correspondência exata no cadastro do CRM. Entram nos "
            "cards e no descritivo, mas não são desenhadas no mapa."
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
    tab_mun["Unidades"] = tab_mun["Unidades"].astype(int)
    # Ordena pelo número e só depois formata em R$ (string não ordena direito).
    tab_mun = tab_mun.sort_values("Faturamento", ascending=False)
    tab_mun["Faturamento"] = tab_mun["Faturamento"].apply(lambda x: _brl(round(x)))
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
    desc["NM_MUN"] = desc["NM_MUN"].fillna(desc["Municipio"])
    desc["Território"] = desc["Dentro"].map({True: "Dentro", False: "Fora"})
    desc.loc[desc["CD_MUN"].isna(), "Território"] = "Sem município"
    desc.loc[desc["CD_MUN"].isna(), "NM_MUN"] = "Não identificado"
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
