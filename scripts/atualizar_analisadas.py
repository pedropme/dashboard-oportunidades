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


def levantar_pendentes():
    v = analisadas.apenas_agricola(pd.read_excel(ARQ_VENDAS))
    achado = analisadas.resolver_municipios(v)
    v = v.assign(Motivo=achado["Motivo"], CD_MUN=achado["CD_MUN"])

    pend = v[v["CD_MUN"].isna()].copy()
    if pend.empty:
        return pd.DataFrame(columns=analisadas.COLUNAS)

    # Nome como está no CRM: ajuda a achar o cadastro na hora de corrigir.
    cli = pd.read_excel(analisadas.ARQ_CLIENTES).rename(
        columns={"Nome da Conta": "Cliente"})
    nome_crm = dict(zip(analisadas.chave(cli["Cliente"]), cli["Cliente"]))

    pend["Nome CRM"] = analisadas.chave(pend["Cliente"]).map(nome_crm).fillna("")
    pend["Situação"] = pend["Motivo"]
    pend["Empresa"] = analisadas.filial_da_venda(pend["Empresa"])

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
