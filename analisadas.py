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
ARQ_CLIENTES = "dados/clientes.xlsx"

# A marca de construção não faz parte deste painel.
MARCA_FORA = "CONSTRUCTION"

MOTIVO_OK_FILIAL = "Resolvido pela filial"
MOTIVO_OK_UNANIME = "Resolvido (município unânime)"
MOTIVO_SEM_CRM = "Não encontrado no CRM"
MOTIVO_MULTI_CPF = "Mais de um CPF para o mesmo nome"
MOTIVO_SEM_FILIAL = "Mais de um município, sem cadastro na filial"

COLUNAS = [
    "Data Detecção", "Cliente", "Nome CRM", "CPF/CNPJ", "Situação", "Vendas",
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


def filial_da_venda(serie_empresa):
    """'PME - LUIS EDUARDO' -> 'LUIS EDUARDO'."""
    return (chave(serie_empresa)
            .str.replace(r"^PME\s*-\s*", "", regex=True).str.strip())


def _casa_filial(filial, concessionaria):
    """A filial da venda corresponde à concessionária do cadastro?

    Cada palavra do nome da filial precisa ser prefixo de alguma palavra da
    concessionária: resolve TEIXEIRA/TEIXEIRA DE FREITAS, LUIS EDUARDO/LUIS
    EDUARDO MAGALHAES e GOV/GOVERNADOR VALADARES sem lista de/para.
    """
    palavras = concessionaria.split()
    return all(
        any(p.startswith(tok) for p in palavras) for tok in filial.split()
    )


def resolver_municipios(vendas, arq_clientes=ARQ_CLIENTES):
    """Município de cada venda, a partir do cadastro do CRM.

    O mesmo cliente é cadastrado uma vez por filial, então o nome sozinho
    não decide: vale o cadastro da filial que faturou a venda. O CPF liga
    os cadastros da mesma pessoa mesmo quando o nome varia entre eles
    ("FULANO" na venda, "FULANO E OUTROS" no cadastro de uma das lojas).

    `vendas` precisa de Cliente e Empresa. Devolve um DataFrame com
    CD_MUN, Municipio, Motivo e CPF, no mesmo índice das vendas. O CPF é o
    do cadastro usado; quando o nome cai em mais de um CPF, vêm todos, que
    é o que mostra o conflito a quem for corrigir.
    """
    cli = pd.read_excel(arq_clientes).rename(columns={
        "Nome da Conta": "Nome", "Documento (BR: CPF/CNPJ)": "CPF",
        "Concessionária": "Conc", "CÓD": "CD_MUN", "MUNICIPIO": "Municipio"})
    cli["K"] = chave(cli["Nome"])
    cli["CPF"] = cli["CPF"].fillna("").astype(str).str.strip()
    cli["CD_MUN"] = cli["CD_MUN"].astype(str).str.strip()
    cli["ConcN"] = chave(cli["Conc"])
    cli = cli[cli["CD_MUN"].str.fullmatch(r"\d{7}", na=False)]

    por_nome = {k: g for k, g in cli.groupby("K")}
    por_cpf = {k: g for k, g in cli.groupby("CPF")}
    nomes = sorted(por_nome)

    k_venda = chave(vendas["Cliente"])
    filiais = filial_da_venda(vendas["Empresa"])
    concs = sorted(cli["ConcN"].unique())
    # filial -> concessionárias, calculado uma vez
    alvo_por_filial = {
        f: [c for c in concs if _casa_filial(f, c)] for f in filiais.unique()
    }

    cache = {}

    def resolver(k, filial):
        cand = por_nome.get(k)
        if cand is None:
            # nome da venda é começo do nome do cadastro, ou o contrário
            pref = [n for n in nomes
                    if n.startswith(k + " ") or k.startswith(n + " ")]
            if not pref:
                return None, None, MOTIVO_SEM_CRM, ""
            cand = pd.concat([por_nome[n] for n in pref])

        cpfs = sorted({x for x in cand["CPF"] if x})
        if len(cpfs) > 1:
            return None, None, MOTIVO_MULTI_CPF, "; ".join(cpfs)
        cpf = cpfs[0] if cpfs else ""
        if cpf:
            cand = por_cpf[cpf]

        da_filial = cand[cand["ConcN"].isin(alvo_por_filial.get(filial, []))]
        if not da_filial.empty:
            r = da_filial.iloc[0]
            return r["CD_MUN"], r["Municipio"], MOTIVO_OK_FILIAL, cpf
        if cand["CD_MUN"].nunique() == 1:
            r = cand.iloc[0]
            return r["CD_MUN"], r["Municipio"], MOTIVO_OK_UNANIME, cpf
        return None, None, MOTIVO_SEM_FILIAL, cpf

    saida = []
    for k, f in zip(k_venda, filiais):
        if (k, f) not in cache:
            cache[(k, f)] = resolver(k, f)
        saida.append(cache[(k, f)])

    return pd.DataFrame(
        saida, columns=["CD_MUN", "Municipio", "Motivo", "CPF"],
        index=vendas.index,
    )


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
    k_pend = set(chave(pendentes["Cliente"])) if not pendentes.empty else set()

    if atual.empty:
        manter = atual
    else:
        k_atual = chave(atual["Cliente"])
        preenchido = atual["CÓD IBGE"].str.fullmatch(r"\d{7}", na=False)
        # Fica quem foi preenchido à mão (o painel usa) e quem segue pendente.
        # Sai quem o CRM passou a resolver sozinho, para a fila não cobrar
        # um cliente já identificado.
        manter = atual[preenchido | k_atual.isin(k_pend)].copy()

        stats = pendentes.set_index(chave(pendentes["Cliente"]))
        k_manter = chave(manter["Cliente"])
        for col in ("Vendas", "Faturamento", "Filial", "Vendedor",
                    "Nome CRM", "CPF/CNPJ", "Situação"):
            if col in stats.columns:
                manter[col] = k_manter.map(stats[col]).fillna(manter[col])

    antigos = set(chave(manter["Cliente"])) if not manter.empty else set()
    novos = pendentes[~chave(pendentes["Cliente"]).isin(antigos)].copy()
    novos["Data Detecção"] = hoje.strftime("%d/%m/%Y")
    novos["CÓD IBGE"] = ""
    novos["Município"] = ""

    fila = pd.concat([manter, novos[COLUNAS]], ignore_index=True)
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

    larguras = {"Data Detecção": 13, "Cliente": 42, "Nome CRM": 42,
                "CPF/CNPJ": 20, "Situação": 26, "Vendas": 9,
                "Faturamento": 15, "Filial": 18, "Vendedor": 20,
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

    # Letras vindas de COLUNAS: acrescentar coluna não quebra as fórmulas.
    from openpyxl.utils import get_column_letter

    col = {n: get_column_letter(i) for i, n in enumerate(COLUNAS, start=1)}
    cli, ibge, fat = col["Cliente"], col["CÓD IBGE"], col["Faturamento"]
    base = len(linhas) + 1
    resumo = [
        ("Clientes na fila", f"=COUNTA('{ABA}'!{cli}2:{cli}{ult})", "0"),
        ("Já identificados", f"=COUNTA('{ABA}'!{ibge}2:{ibge}{ult})", "0"),
        ("Falta identificar", f"=COUNTBLANK('{ABA}'!{ibge}2:{ibge}{ult})", "0"),
        ("Faturamento sem município",
         f"=SUMIF('{ABA}'!{ibge}2:{ibge}{ult},\"\",'{ABA}'!{fat}2:{fat}{ult})",
         "R$ #,##0"),
    ]
    for i, (rot, f, fmt) in enumerate(resumo, start=base):
        lg.cell(row=i, column=1, value=rot).font = Font(name="Arial", size=11)
        c = lg.cell(row=i, column=2, value=f)
        c.font = Font(name="Arial", size=11, bold=True)
        c.number_format = fmt
    lg.column_dimensions["A"].width = 76
    lg.column_dimensions["B"].width = 20
