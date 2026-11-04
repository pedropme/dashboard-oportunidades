"""
dados/Vendas Analisadas.xlsx — fila permanente de clientes a identificar.

Uma linha por cliente cujo município não saiu do CRM. O arquivo é
permanente: o que o Pedro preenche à mão (CÓD IBGE / Município) nunca é
sobrescrito pela atualização, e o cliente guarda a data em que apareceu
pela primeira vez — sempre haverá cliente que nunca será identificado.

Sem import de streamlit: o painel lê daqui e o atualizar.py escreve aqui.
"""
import os
import unicodedata
from datetime import date

import pandas as pd

ARQ = "dados/Vendas Analisadas.xlsx"
ABA = "Clientes a identificar"

# A marca de construção não faz parte deste painel.
MARCA_FORA = "CONSTRUCTION"

COLUNAS = [
    "Data Detecção", "Cliente", "Nome CRM", "Situação", "Vendas",
    "Faturamento", "Filial", "Vendedor", "CÓD IBGE", "Município",
]


def chave(serie):
    """Nome do cliente normalizado — a mesma chave no painel e no arquivo."""
    return (serie.fillna("").astype(str)
            .apply(lambda x: unicodedata.normalize("NFKD", x))
            .str.encode("ascii", errors="ignore").str.decode("utf-8")
            .str.upper().str.strip().str.replace(r"\s+", " ", regex=True))


def apenas_agricola(df, col_marca="Emp Marca Venda"):
    """Tira as vendas da marca de construção."""
    if col_marca not in df.columns:
        return df
    marca = chave(df[col_marca])
    return df[~marca.str.contains(MARCA_FORA, na=False)]


def carregar():
    """Devolve a fila atual. Arquivo ausente = fila vazia."""
    if not os.path.exists(ARQ):
        return pd.DataFrame(columns=COLUNAS)
    df = pd.read_excel(ARQ, sheet_name=ABA)
    for c in COLUNAS:
        if c not in df.columns:
            df[c] = None
    df["CÓD IBGE"] = (
        df["CÓD IBGE"].astype(str).str.strip()
        .str.replace(r"\.0$", "", regex=True).replace({"nan": "", "None": ""})
    )
    return df[COLUNAS]


def municipios_preenchidos():
    """Chave do cliente -> (código IBGE, município) preenchidos à mão."""
    df = carregar()
    if df.empty:
        return {}
    ok = df[df["CÓD IBGE"].str.fullmatch(r"\d{7}", na=False)]
    return {
        k: (ibge, mun)
        for k, ibge, mun in zip(chave(ok["Cliente"]), ok["CÓD IBGE"], ok["Município"])
    }


def atualizar(pendentes, hoje=None):
    """Mescla os pendentes de hoje com a fila já existente.

    `pendentes`: DataFrame com Cliente, Nome CRM, Situação, Vendas,
    Faturamento, Filial, Vendedor. Devolve (total_na_fila, novos_hoje).
    """
    hoje = hoje or date.today()
    atual = carregar()
    antigos = set(chave(atual["Cliente"])) if not atual.empty else set()

    novos = pendentes[~chave(pendentes["Cliente"]).isin(antigos)].copy()
    novos["Data Detecção"] = hoje.strftime("%d/%m/%Y")
    novos["CÓD IBGE"] = ""
    novos["Município"] = ""

    # Linha que já existe: só atualiza o que é contagem; o preenchido fica.
    if not atual.empty:
        stats = pendentes.set_index(chave(pendentes["Cliente"]))
        k_atual = chave(atual["Cliente"])
        for col in ("Vendas", "Faturamento", "Filial", "Vendedor", "Nome CRM", "Situação"):
            novo_valor = k_atual.map(stats[col]) if col in stats.columns else None
            if novo_valor is not None:
                atual[col] = novo_valor.fillna(atual[col])

    fila = pd.concat([atual, novos[COLUNAS]], ignore_index=True)
    fila = fila.sort_values("Faturamento", ascending=False, na_position="last")
    _gravar(fila)
    return len(fila), len(novos)


def quantos_pendentes():
    """Clientes na fila que ainda não têm município preenchido."""
    df = carregar()
    if df.empty:
        return 0
    return int((~df["CÓD IBGE"].str.fullmatch(r"\d{7}", na=False)).sum())


def _gravar(fila):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    FONTE = "Arial"
    wb = Workbook()
    ws = wb.active
    ws.title = ABA
    borda = Border(*[Side(style="thin", color="BFBFBF")] * 4)

    ws.append(COLUNAS)
    for c in range(1, len(COLUNAS) + 1):
        cel = ws.cell(row=1, column=c)
        cel.fill = PatternFill("solid", fgColor="1F3864")
        cel.font = Font(name=FONTE, size=10, bold=True, color="FFFFFF")
        cel.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cel.border = borda

    col_crm = COLUNAS.index("Nome CRM") + 1
    col_ibge = COLUNAS.index("CÓD IBGE") + 1
    col_fat = COLUNAS.index("Faturamento") + 1

    for i, linha in enumerate(fila[COLUNAS].itertuples(index=False), start=2):
        for c, valor in enumerate(linha, start=1):
            cel = ws.cell(row=i, column=c)
            cel.value = valor if (pd.notna(valor) and valor != "") else None
            cel.font = Font(name=FONTE, size=10)
            cel.border = borda
        ws.cell(row=i, column=col_fat).number_format = "R$ #,##0"
        ws.cell(row=i, column=col_ibge).alignment = Alignment(horizontal="left")
        # Vermelho enquanto o município não for preenchido.
        falta = not str(ws.cell(row=i, column=col_ibge).value or "").strip()
        if falta:
            ws.cell(row=i, column=col_crm).font = Font(
                name=FONTE, size=10, color="FF0000", bold=True
            )

    larguras = {"Data Detecção": 13, "Cliente": 42, "Nome CRM": 42, "Situação": 26,
                "Vendas": 9, "Faturamento": 15, "Filial": 18, "Vendedor": 20,
                "CÓD IBGE": 11, "Município": 24}
    for c, nome in enumerate(COLUNAS, start=1):
        ws.column_dimensions[get_column_letter(c)].width = larguras[nome]
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUNAS))}{len(fila) + 1}"

    _legenda(wb, len(fila) + 1)
    os.makedirs(os.path.dirname(ARQ), exist_ok=True)
    wb.save(ARQ)


def _legenda(wb, ult):
    from openpyxl.styles import Font

    lg = wb.create_sheet("Legenda")
    linhas = [
        ("Clientes a identificar — o que preencher", True),
        ("", False),
        ("Cada linha é um cliente cujas vendas não puderam ser colocadas no mapa,", False),
        ("porque o nome não resolveu um município único no CRM (clientes.xlsx).", False),
        ("", False),
        ("Preencha CÓD IBGE (7 dígitos) e Município. O painel passa a usar o que", False),
        ("estiver preenchido aqui, sem depender de corrigir o CRM.", False),
        ("Exemplo:  CÓD IBGE = 3203205   Município = LINHARES", False),
        ("", False),
        ("VERMELHO em 'Nome CRM' = ainda falta preencher.", False),
        ("'Data Detecção' é o dia em que o cliente apareceu pela primeira vez —", False),
        ("a linha nunca é apagada pela atualização, e o que você preencher fica.", False),
        ("Vendas da marca de construção não entram neste painel.", False),
        ("", False),
        ("Situação atual", True),
    ]
    for i, (t, b) in enumerate(linhas, start=1):
        lg.cell(row=i, column=1, value=t).font = Font(name="Arial", size=11, bold=b)

    base = len(linhas) + 1
    resumo = [
        ("Clientes na fila", f"=COUNTA('{ABA}'!B2:B{ult})", "0"),
        ("Já identificados", f"=COUNTA('{ABA}'!I2:I{ult})", "0"),
        ("Falta identificar", f"=COUNTBLANK('{ABA}'!I2:I{ult})", "0"),
        ("Faturamento sem município",
         f"=SUMIF('{ABA}'!I2:I{ult},\"\",'{ABA}'!F2:F{ult})", "R$ #,##0"),
    ]
    for i, (rot, f, fmt) in enumerate(resumo, start=base):
        lg.cell(row=i, column=1, value=rot).font = Font(name="Arial", size=11)
        c = lg.cell(row=i, column=2, value=f)
        c.font = Font(name="Arial", size=11, bold=True)
        c.number_format = fmt
    lg.column_dimensions["A"].width = 76
    lg.column_dimensions["B"].width = 20
