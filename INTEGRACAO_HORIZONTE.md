# Integração — Vendas realizadas (Projeto Horizonte) no Dashboard de Oportunidades

Adiciona a opção **Vendas realizadas** na aba **🗺️ Resumo em Mapas**, ao lado de
*Oportunidades* e *Matriz de Performance*. Com ela selecionada, o subfiltro passa a
ser **Período** (Todos / 2026 / 2025 / 2024). Segue todos os filtros da barra
lateral (Região, Filial, Estado, Status, Vendedor) e as restrições de acesso por
filial/região do usuário.

---

## 1. Arquivos

| Arquivo | Ação | Observação |
|---|---|---|
| `horizonte.py` | **novo** (raiz do projeto, ao lado de `app.py`) | toda a lógica: carga, filtros, cards, mapa, tabelas |
| `dados/horizonte_vendas_gv.xlsx` | **novo** | aba `GV`, vendas 2024–2026 já com CPF/IBGE/Município preenchidos |
| `app.py` | **alterar** | 3 trechos (abaixo) |

Não há dependência nova: usa `pandas`, `geopandas`, `folium`, `streamlit-folium`
e `streamlit-aggrid`, que já estão no `requirements.txt`.

Bases já existentes que o módulo reaproveita: `dados/territorio.xlsx`,
`dados/metas.xlsx`, `maps/municipios.geojson`.

---

## 2. Alterações no `app.py`

### 2.1 Import (topo do arquivo)

```python
import export_pdf
import horizonte          # ← adicionar
```

### 2.2 Seletor "Tipo de informação" (aba Resumo em Mapas)

**Remover** o bloco do toggle Oportunidades ↔ Matriz:

```python
        _ma, _mb, _mc, _ = st.columns([1.3, 0.5, 2.0, 6], gap="small")
        with _ma:
            ...
        with _mb:
            _mapa_matriz = st.toggle("", key="mapa_tipo_toggle", label_visibility="collapsed")
        with _mc:
            ...
        _tipo_mapa = "Matriz de Performance" if _mapa_matriz else "Oportunidades"

        # ── Exibição de oportunidades (apenas no modo Oportunidades) ─────────
        if _tipo_mapa == "Oportunidades":
            somente_abertas = st.radio(...)
        else:
            somente_abertas = "Todos com oportunidades"
```

**Colocar no lugar** (logo abaixo do título "Tipo de informação"):

```python
        _tipo_mapa = st.radio(
            "Tipo de informação",
            options=["Oportunidades", "Matriz de Performance", "Vendas realizadas"],
            index=0,
            horizontal=True,
            key="mapa_tipo",
            label_visibility="collapsed",
        )

        # ── Subfiltro de cada tipo ───────────────────────────────────────────
        somente_abertas = "Todos com oportunidades"
        if _tipo_mapa == "Oportunidades":
            somente_abertas = st.radio(
                "Exibição de oportunidades (municípios)",
                options=["Todos com oportunidades", "Somente em aberto"],
                index=1,
                horizontal=True,
            )
        elif _tipo_mapa == "Vendas realizadas":
            _vendas_hz = horizonte.carregar_vendas(
                _sig(horizonte.ARQ_VENDAS), normalizar
            )
            _periodo_hz = st.radio(
                "Período",
                options=["Todos"] + horizonte.anos_disponiveis(_vendas_hz),
                index=0,
                horizontal=True,
                key="mapa_periodo_vendas",
            )
```

### 2.3 Novo ramo do mapa

No final do bloco `if _tipo_mapa == "Oportunidades":` (depois de
`_tabela(tabela_desc_mun, key="tv_desc_mun")`) e **antes** do `else:` da Matriz
de Performance, inserir:

```python
        elif _tipo_mapa == "Vendas realizadas":
            # ── MAPA VENDAS REALIZADAS (Projeto Horizonte) ────────────────────
            horizonte.renderizar(
                vendas=_vendas_hz,
                periodo=_periodo_hz,
                territorio=territorio,
                gdf_mun=gdf_mun,
                filial_do_consultor=_mapa_filial_consultor()[0],
                status_do_consultor=_nome_bi_to_status,
                regiao=regiao,
                filial=filial,
                estado=estado,
                status_filtro=status_filtro,
                vendedor=vendedor,
                filiais_restritas=_filiais_restritas,
                regiao_restrita=_regiao_restrita,
                mostrar_dados=mostrar_dados,
                card=card,
                tabela=_tabela,
            )
        else:
            # ── MAPA MATRIZ DE PERFORMANCE ──── (já existente, não muda)
```

Todas as variáveis passadas já existem no `app.py` (`territorio`, `gdf_mun`,
`_mapa_filial_consultor`, `_nome_bi_to_status`, filtros da sidebar, `card`,
`_tabela`, `mostrar_dados`).

---

## 3. Regras de negócio

- **Chave:** Código IBGE do município (`CD_MUN`).
- **Vendedor:** a base de vendas usa o NOME BI (ex.: `SANDRO.FERNANDES`); é
  convertido para o NOME CRM pelo `territorio.xlsx`. Ex-consultores sem cadastro
  no território aparecem pelo NOME BI.
- **Filial / Região / Estado:** do vendedor (filial via `metas.xlsx`, como no
  resto do dashboard). Sem filial em metas → usa a filial do município.
- **Status:** `metas.xlsx` (ATIVO / INATIVO). Atenção: o dashboard abre em
  *Ativos*, o que esconde vendas de inativos (R$ 9,0 mi em Ativos × R$ 12,7 mi em Todos).
- **Dentro / fora do território:** o município está (ou não) no território da
  filial **do vendedor**. Hoje dá 6 municípios fora: Marliéria, Santo Antônio do
  Rio Abaixo, José Gonçalves de Minas (vendas GV fora da área) e Itabira, Nova
  Era, Serro (vendedores cadastrados em Manhuaçu vendendo na área GV).
- **Cores:** azul em 5 faixas por quartil de faturamento
  (`#BBDEFB → #0D47A1`), vermelho `#C62828` para fora do território, contorno
  tracejado azul do território. Mapa OpenStreetMap, borda `#333`, opacidade 0,65.
- **Sem município:** 5 vendas sem IBGE não vão para o mapa, mas entram nos cards
  e no Descritivo (com aviso abaixo do mapa).

## 4. Conteúdo exibido

1. Cards: Faturamento (Total), Unidades vendidas, Clientes, Municípios com venda, Fora do território.
2. Mapa com tooltip (município, UF, situação, vendedor, faturamento, unidades, clientes, por segmento).
3. Legenda de cores.
4. Tabela por município (filtrável, Baixar CSV).
5. **Descritivo das Vendas** (mês, cliente, documento, município, vendedor, filial, segmento, modelo, quantidade, valor, território).

## 5. Atualização da base

Substituir `dados/horizonte_vendas_gv.xlsx` mantendo a aba `GV` e as colunas:
`Ano, Ano Mes, Cliente, CPF, IBGE, MUNICIPIO (UF), Data Emissao, Familia, Modelo,
Segmento Maq, Quantidade, Vendedor, Vl NFVenda`. O cache se renova sozinho
(assinatura do arquivo via `_sig`).

Para outras filiais no futuro: gerar outras abas/arquivos no mesmo formato e
concatenar em `horizonte.carregar_vendas` — o resto (filtros, dentro/fora) já é genérico.

## 6. Conferência após integrar

- [ ] Aba Resumo em Mapas mostra as 3 opções; Oportunidades e Matriz seguem iguais.
- [ ] Vendas realizadas + Status **Todos** → R$ 12.702.612 · 141 un · 81 clientes · 37 municípios.
- [ ] Período 2025 → R$ 4.714.326 · 22 municípios.
- [ ] Filtro de Vendedor e de Filial alteram cards, mapa e tabelas.
- [ ] Usuário com filial restrita só vê vendas da própria filial.
