# -*- coding: utf-8 -*-
"""
Atualiza dados/Vendas Analisadas.xlsx — a fila de clientes a identificar.

Roda depois do download das bases: compara as vendas com o cadastro do CRM
e acrescenta à fila o cliente cujo município não resolveu, com a data de
hoje. O que já estava na fila é preservado, inclusive o preenchimento
manual de CÓD IBGE / Município.
"""
import os
import sys

import pandas as pd

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)

import analisadas  # noqa: E402  (precisa do sys.path acima)

ARQ_VENDAS = "dados/vendas.xlsx"
ARQ_CLIENTES = "dados/clientes.xlsx"


def levantar_pendentes():
    cli = pd.read_excel(ARQ_CLIENTES).rename(columns={
        "Nome da Conta": "Cliente", "CÓD": "CD_MUN", "Cidade": "Municipio"})
    cli["K"] = analisadas.chave(cli["Cliente"])
    cli["CD_MUN"] = cli["CD_MUN"].astype(str).str.strip()
    cli["valido"] = cli["CD_MUN"].str.fullmatch(r"\d{7}", na=False)

    nome_crm = cli.drop_duplicates(subset=["K"]).set_index("K")["Cliente"].to_dict()
    n_mun = cli[cli["valido"]].groupby("K")["CD_MUN"].nunique()
    resolvidos = set(n_mun[n_mun == 1].index)
    ambiguos = set(n_mun[n_mun > 1].index)

    v = analisadas.apenas_agricola(pd.read_excel(ARQ_VENDAS))
    v["K"] = analisadas.chave(v["Cliente"])
    pend = v[~v["K"].isin(resolvidos)].copy()
    if pend.empty:
        return pd.DataFrame(columns=analisadas.COLUNAS)

    def situacao(k):
        if k in ambiguos:
            return "Mais de um município"
        if k in nome_crm:
            return "Cadastro sem município"
        return "Não encontrado no CRM"

    pend["Nome CRM"] = pend["K"].map(nome_crm).fillna("")
    pend["Situação"] = pend["K"].map(situacao)
    pend["Empresa"] = pend["Empresa"].astype(str).str.replace(
        r"^PME\s*-\s*", "", regex=True).str.strip()

    por_cliente = (
        pend.groupby("Cliente")
        .agg(
            **{
                "Nome CRM": ("Nome CRM", "first"),
                "Situação": ("Situação", "first"),
                "Vendas": ("Vl NFVenda", "size"),
                "Faturamento": ("Vl NFVenda", "sum"),
                "Filial": ("Empresa", "first"),
                "Vendedor": ("Vendedor", "first"),
            }
        )
        .reset_index()
    )
    return por_cliente


def main():
    pendentes = levantar_pendentes()
    total, novos = analisadas.atualizar(pendentes)
    falta = analisadas.quantos_pendentes()

    print(f"  Clientes na fila: {total} (novos hoje: {novos})")
    if falta:
        print(f"  ATENCAO: {falta} cliente(s) sem municipio identificado.")
        print(f"  Preencha CÓD IBGE e Município em {analisadas.ARQ}")
    else:
        print("  Nenhum cliente pendente de identificacao.")
    return falta


if __name__ == "__main__":
    main()
