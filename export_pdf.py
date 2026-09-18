# -*- coding: utf-8 -*-
"""
Ficha de Performance do Consultor — exportação em PDF.

Consome os DataFrames que a aba Matriz de Performance (app.py) já carregou
(metas, território, realizado) — não lê nada do disco por conta própria,
para nunca divergir dos números que aparecem na tela.

Modelo aprovado pelo Pedro em 18/09/2026, a partir de uma planilha de
referência (PRÊMIO ANUAL / "matriz SANDRO.pdf"): mesma disposição de
colunas (meses/trimestres/ano-atual/total), sem transpor nem empilhar,
em retrato. Decisões tomadas nessa aprovação:
  - Sem linha de CRM (70%) e sem "Código" do consultor — sem fonte de
    dado hoje.
  - Sem os gráficos de velocímetro do modelo original.
  - Card de pontuação dividido: Média de Pontuação (mesma fórmula do
    Ranking de Consultores, _rk_media em app.py) + Pontuação do
    trimestre vigente (o mais recente já iniciado).
  - "R$" sai da célula e vai para o rótulo da linha ("Meta (R$)") — é o
    que permite a tabela larga original caber em retrato.
"""
from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER

MESES = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN",
         "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]

AZUL = colors.HexColor("#1F3864")
AZUL_CLARO = colors.HexColor("#DCE6F1")
CINZA_TRI = colors.HexColor("#D9D9D9")     # 1 TRI..4 TRI
CINZA_ESCURO = colors.HexColor("#767171")  # ANO ATM / TOTAL — propositalmente mais escuro
VERDE = colors.HexColor("#2E7D32")
AMARELO = colors.HexColor("#F9A825")
VERMELHO = colors.HexColor("#C62828")

MARGEM = 8 * mm
LARGURA_UTIL = A4[0] - 2 * MARGEM  # A4 retrato: 210mm - 16mm = 194mm

_st_titulo = ParagraphStyle("titulo", fontSize=13, leading=15, fontName="Helvetica-Bold")
_st_sub = ParagraphStyle("sub", fontSize=8, leading=10, textColor=colors.HexColor("#555555"))
_st_label = ParagraphStyle("label", fontSize=7.5, textColor=colors.HexColor("#666666"), alignment=TA_CENTER)
_st_produto = ParagraphStyle("produto", fontSize=7.5, fontName="Helvetica-Bold",
                             alignment=TA_CENTER, textColor=colors.white)
_st_nota = ParagraphStyle("nota", fontSize=6, textColor=colors.HexColor("#888888"))


def _cor_faixa(pct: float):
    if pct >= 80: return VERDE
    if pct >= 60: return AMARELO
    return VERMELHO


def _fmt_valor(v, monetario: bool) -> str:
    # "R$" fica no rotulo da linha, nao na celula — e o que da espaco pra
    # tabela larga caber em retrato.
    if monetario:
        return f"{round(v):,}".replace(",", ".")
    return f"{v:.0f}"


def _calc_ponto(real, meta, base_pct):
    """Mesma fórmula usada na aba Matriz de Performance / Ranking de Consultores."""
    real = 0 if pd.isna(real) else real
    if pd.isna(meta):
        return 0.0
    if meta == 0:
        return base_pct  # meta zerada = já batida
    if real < meta:
        return 0.0
    excess_ratio = min((real - meta) / meta, 1.0)
    return base_pct + base_pct * excess_ratio * 0.20


def montar_dados_consultor(consultor_bi, matriz, realizado, col_vend="CONSULTOR"):
    """
    Calcula tudo que a ficha precisa para UM consultor: bloco por produto
    (Meta/Realizado/Diferença/Pontos em Jan..Dez + trimestres + ano-atual +
    total), média de pontuação e pontuação do trimestre vigente (mesma
    fórmula do Ranking de Consultores), e o indicador R$ Impl/Trator.

    `matriz` é o metas.xlsx (já filtrado a ATIVOS) mesclado com território
    — o mesmo DataFrame que a aba já monta. `realizado` é o DataFrame
    global de vendas por CONSULTOR/PRODUTO/MES (sem filtro de sidebar).
    """
    linhas = matriz[matriz[col_vend] == consultor_bi]
    n_produtos = len(linhas)
    base_pct = (100 / n_produtos) if n_produtos > 0 else 0
    mes_hoje = pd.Timestamp.today().month
    tri_vigente = (mes_hoje - 1) // 3
    quarters_iniciados = sum(1 for m in (1, 4, 7, 10) if mes_hoje >= m)

    filial = linhas["Filial"].dropna().iloc[0] if not linhas["Filial"].dropna().empty else "-"
    regiao = linhas["Região"].dropna().iloc[0] if not linhas["Região"].dropna().empty else "-"

    def buscar_realizado(produto, mes):
        f = realizado[
            (realizado["CONSULTOR"] == consultor_bi)
            & (realizado["PRODUTO"] == produto)
            & (realizado["MES"] == mes)
        ]
        return f["REALIZADO"].sum() if len(f) else 0

    blocos = []
    soma_pontos_q = [0.0, 0.0, 0.0, 0.0]
    impl_real = 0.0
    trator_real = 0.0

    for _, row in linhas.iterrows():
        produto = row["PRODUTO"]
        is_monetary = produto in ("IMPLEMENTO", "USADOS")

        meses_meta = [row[m] for m in MESES]
        meses_real = [buscar_realizado(produto, i + 1) for i in range(12)]

        def tri(vals, i):
            return sum(vals[i * 3: i * 3 + 3])

        meta_q = [tri(meses_meta, i) for i in range(4)]
        real_q = [tri(meses_real, i) for i in range(4)]
        dif_mes = [r - m for r, m in zip(meses_real, meses_meta)]
        dif_q = [r - m for r, m in zip(real_q, meta_q)]
        meta_total = sum(meses_meta)
        real_total = sum(meses_real)

        p_q = [
            _calc_ponto(real_q[0], meta_q[0], base_pct),
            _calc_ponto(real_q[1], meta_q[1], base_pct) if mes_hoje >= 4 else 0.0,
            _calc_ponto(real_q[2], meta_q[2], base_pct) if mes_hoje >= 7 else 0.0,
            _calc_ponto(real_q[3], meta_q[3], base_pct) if mes_hoje >= 10 else 0.0,
        ]
        for i in range(4):
            soma_pontos_q[i] += p_q[i]

        ano_atm_meta = sum(meta_q[:quarters_iniciados])
        ano_atm_real = sum(real_q[:quarters_iniciados])
        pontuacao_total_produto = sum(p_q)

        if produto == "IMPLEMENTO":
            impl_real = real_total
        if produto == "TRATOR":
            trator_real = real_total

        blocos.append(dict(
            produto=produto, is_monetary=is_monetary,
            meses_meta=meses_meta, meses_real=meses_real, dif_mes=dif_mes,
            meta_q=meta_q, real_q=real_q, dif_q=dif_q,
            meta_total=meta_total, real_total=real_total, dif_total=real_total - meta_total,
            ano_atm_meta=ano_atm_meta, ano_atm_real=ano_atm_real, ano_atm_dif=ano_atm_real - ano_atm_meta,
            p_q=p_q, ano_atm_pontos=pontuacao_total_produto, total_pontos=pontuacao_total_produto,
        ))

    vals_iniciados = soma_pontos_q[:quarters_iniciados]
    media_pontuacao = (sum(vals_iniciados) / len(vals_iniciados)) if vals_iniciados else 0
    pontuacao_tri_vigente = soma_pontos_q[tri_vigente]
    rs_impl_trator = (impl_real / trator_real) if trator_real else None

    return dict(
        consultor_bi=consultor_bi, filial=filial, regiao=regiao,
        n_produtos=n_produtos, base_pct=base_pct, mes_hoje=mes_hoje,
        tri_vigente=tri_vigente, quarters_iniciados=quarters_iniciados,
        blocos=blocos, media_pontuacao=media_pontuacao,
        pontuacao_tri_vigente=pontuacao_tri_vigente, rs_impl_trator=rs_impl_trator,
    )


def _bloco_produto_flowables(bloco, base_pct, quarters_iniciados):
    produto = bloco["produto"]
    mon = bloco["is_monetary"]
    sufixo = " (R$)" if mon else ""
    fmt = lambda x: _fmt_valor(x, mon)

    cols_header = ["", "JAN", "FEV", "MAR", "1 TRI", "ABR", "MAI", "JUN", "2 TRI",
                   "JUL", "AGO", "SET", "3 TRI", "OUT", "NOV", "DEZ", "4 TRI",
                   "ANO ATM", "TOTAL"]

    def linha(rotulo, meses, q, anoatm, total):
        vals = []
        for i in range(4):
            vals += [meses[i * 3], meses[i * 3 + 1], meses[i * 3 + 2], q[i]]
        return [rotulo] + [fmt(v) for v in vals] + [fmt(anoatm), fmt(total)]

    dados = [cols_header]
    dados.append(linha("Meta" + sufixo, bloco["meses_meta"], bloco["meta_q"], bloco["ano_atm_meta"], bloco["meta_total"]))
    dados.append(linha("Realizado" + sufixo, bloco["meses_real"], bloco["real_q"], bloco["ano_atm_real"], bloco["real_total"]))
    dados.append(linha("Diferença" + sufixo, bloco["dif_mes"], bloco["dif_q"], bloco["ano_atm_dif"], bloco["dif_total"]))

    pontos_row = ["Pontos"]
    for i in range(4):
        pontos_row += ["", "", "", f"{bloco['p_q'][i]:.1f}"]
    pontos_row += [f"{bloco['ano_atm_pontos']:.1f}", f"{bloco['total_pontos']:.1f}"]
    dados.append(pontos_row)

    col_label, col_mes, col_tri, col_anoatm, col_total = 15 * mm, 8.6 * mm, 11 * mm, 17 * mm, 18 * mm
    col_w = [col_label]
    for _ in range(4):
        col_w += [col_mes, col_mes, col_mes, col_tri]
    col_w += [col_anoatm, col_total]
    col_w[0] += LARGURA_UTIL - sum(col_w)  # fecha exato na largura util

    n_col = len(cols_header)
    tabela = Table(dados, colWidths=col_w, rowHeights=3.6 * mm)
    estilo = [
        ("FONTSIZE", (0, 0), (-1, -1), 5.2),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (0, -1), 4.8),
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#BFBFBF")),
        ("BACKGROUND", (0, 1), (0, -1), AZUL_CLARO),
        ("TOPPADDING", (0, 0), (-1, -1), 0.6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0.6),
        ("LEFTPADDING", (0, 0), (-1, -1), 1.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1.5),
    ]
    for idx, nome in enumerate(cols_header):
        if nome in ("1 TRI", "2 TRI", "3 TRI", "4 TRI"):
            estilo += [("BACKGROUND", (idx, 1), (idx, 3), CINZA_TRI),
                       ("FONTNAME", (idx, 1), (idx, 3), "Helvetica-Bold")]
        if nome in ("ANO ATM", "TOTAL"):
            estilo += [("BACKGROUND", (idx, 1), (idx, 3), CINZA_ESCURO),
                       ("TEXTCOLOR", (idx, 1), (idx, 3), colors.white),
                       ("FONTNAME", (idx, 1), (idx, 3), "Helvetica-Bold")]

    for i in range(4):
        col_idx = 4 + i * 4
        pct_rel = (bloco["p_q"][i] / base_pct * 100) if base_pct else 0
        estilo += [("BACKGROUND", (col_idx, 4), (col_idx, 4), _cor_faixa(pct_rel)),
                   ("TEXTCOLOR", (col_idx, 4), (col_idx, 4), colors.white),
                   ("FONTNAME", (col_idx, 4), (col_idx, 4), "Helvetica-Bold")]
    for col_idx in (n_col - 2, n_col - 1):
        val = bloco["ano_atm_pontos"] if col_idx == n_col - 2 else bloco["total_pontos"]
        maxv = base_pct * quarters_iniciados
        pct_rel = (val / maxv * 100) if maxv else 0
        estilo += [("BACKGROUND", (col_idx, 4), (col_idx, 4), _cor_faixa(pct_rel)),
                   ("TEXTCOLOR", (col_idx, 4), (col_idx, 4), colors.white),
                   ("FONTNAME", (col_idx, 4), (col_idx, 4), "Helvetica-Bold")]

    tabela.setStyle(TableStyle(estilo))

    rotulo = Table([[Paragraph(produto, _st_produto)]], colWidths=[LARGURA_UTIL], rowHeights=4.5 * mm)
    rotulo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), AZUL),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 0.4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0.4),
    ]))

    return [rotulo, tabela, Spacer(1, 1.5 * mm)]


def _cabecalho_flowables(dados):
    linha1 = Table([[
        Paragraph("PME MÁQUINAS", _st_titulo),
        Paragraph(f"<b>{dados['regiao']}</b> · {dados['filial']}<br/>{dados['consultor_bi']}", _st_sub),
        Paragraph(f"Status: <b>ATIVO</b><br/>Data: <b>{datetime.now().strftime('%d/%m/%Y')}</b>", _st_sub),
    ]], colWidths=[55 * mm, 75 * mm, LARGURA_UTIL - 130 * mm])
    linha1.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))

    meia = LARGURA_UTIL / 2
    cor_media = _cor_faixa(dados["media_pontuacao"])
    cor_tri = _cor_faixa(dados["pontuacao_tri_vigente"])
    card_pontuacao = Table([
        [Paragraph("MÉDIA DE PONTUAÇÃO", _st_label),
         Paragraph(f"PONTUAÇÃO {dados['tri_vigente'] + 1}º TRI (VIGENTE)", _st_label)],
        [Paragraph(f"{dados['media_pontuacao']:.1f}%", ParagraphStyle(
            "mp", fontSize=18, fontName="Helvetica-Bold", textColor=cor_media, alignment=TA_CENTER)),
         Paragraph(f"{dados['pontuacao_tri_vigente']:.1f}%", ParagraphStyle(
            "pt", fontSize=18, fontName="Helvetica-Bold", textColor=cor_tri, alignment=TA_CENTER))],
    ], colWidths=[meia, meia], rowHeights=[6 * mm, 10 * mm])
    card_pontuacao.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#BFBFBF")),
        ("LINEAFTER", (0, 0), (0, -1), 0.6, colors.HexColor("#BFBFBF")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F2F2")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    rs = dados["rs_impl_trator"]
    outros_legenda = Table([[
        Table([["OUTROS INDICADORES", ""], ["R$ IMPL/TRATOR", (_fmt_valor(rs, True) if rs else "-")]],
              colWidths=[meia / 2, meia / 2], rowHeights=5 * mm,
              style=TableStyle([
                  ("SPAN", (0, 0), (1, 0)),
                  ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F2F2")),
                  ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 7),
                  ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                  ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#BFBFBF")),
                  ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BFBFBF")),
              ])),
        Table([["LEGENDA"], ["Excelente  [80 - 100]"], ["Médio  [60 - 80]"], ["Baixo  [0 - 60]"]],
              colWidths=[meia], rowHeights=4 * mm,
              style=TableStyle([
                  ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#F2F2F2")),
                  ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 6.5),
                  ("BACKGROUND", (0, 1), (0, 1), VERDE), ("TEXTCOLOR", (0, 1), (0, 1), colors.white),
                  ("BACKGROUND", (0, 2), (0, 2), AMARELO),
                  ("BACKGROUND", (0, 3), (0, 3), VERMELHO), ("TEXTCOLOR", (0, 3), (0, 3), colors.white),
                  ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 5),
                  ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#BFBFBF")),
                  ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BFBFBF")),
              ])),
    ]], colWidths=[meia, meia])
    outros_legenda.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))

    return [linha1, Spacer(1, 2 * mm), card_pontuacao, Spacer(1, 2 * mm), outros_legenda, Spacer(1, 3.5 * mm)]


def gerar_pdf_bytes(dados) -> bytes:
    """Recebe o dict de montar_dados_consultor() e devolve os bytes do PDF."""
    elementos = list(_cabecalho_flowables(dados))
    for bloco in dados["blocos"]:
        elementos += _bloco_produto_flowables(bloco, dados["base_pct"], dados["quarters_iniciados"])
    elementos.append(Spacer(1, 2 * mm))
    elementos.append(Paragraph(
        "Pontuação calculada com a mesma fórmula já usada na aba Matriz de Performance / Ranking de "
        "Consultores do painel. Trimestres ainda não iniciados aparecem zerados. Linhas monetárias mostram "
        "valores em R$ (prefixo omitido nas células para caber no retrato).",
        _st_nota,
    ))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGEM, rightMargin=MARGEM, topMargin=MARGEM, bottomMargin=MARGEM,
        title=f"Ficha de Performance - {dados['consultor_bi']}",
    )
    doc.build(elementos)
    return buf.getvalue()


def gerar_pdf_consultor(consultor_bi, matriz, realizado, col_vend="CONSULTOR") -> bytes:
    dados = montar_dados_consultor(consultor_bi, matriz, realizado, col_vend=col_vend)
    return gerar_pdf_bytes(dados)


def gerar_zip_consultores(consultores, matriz, realizado, col_vend="CONSULTOR") -> bytes:
    """Uma ficha em PDF por consultor, todas dentro de um .zip."""
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for consultor_bi in consultores:
            pdf_bytes = gerar_pdf_consultor(consultor_bi, matriz, realizado, col_vend=col_vend)
            nome_arquivo = f"Ficha_Performance_{consultor_bi}.pdf".replace("/", "-")
            zf.writestr(nome_arquivo, pdf_bytes)
    return buf.getvalue()
