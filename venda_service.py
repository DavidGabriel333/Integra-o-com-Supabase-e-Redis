"""
Relatório de vendas: consulta pedidos, itens, clientes e produtos no Supabase,
calcula o total de cada pedido e o faturamento, e guarda o resultado no Redis.

Esse relatório exige várias consultas ao banco, por isso é um bom candidato a cache.
Ele é invalidado quando um pedido é finalizado ou um produto é alterado.
"""

import json

import config
from conexoes import r, supabase

CHAVE_RELATORIO = "vendas:relatorio"


def relatorio():
    """Retorna (lista_de_vendas, faturamento_total, origem)."""
    cache = r.get(CHAVE_RELATORIO)
    if cache:
        dados = json.loads(cache)
        return dados["vendas"], dados["faturamento"], "Redis (cache)"

    pedidos = supabase.table("pedido").select("*").order("id_pedido", desc=True).execute().data
    clientes = {c["id_cliente"]: c["nome"]
                for c in supabase.table("cliente").select("id_cliente, nome").execute().data}
    produtos = {p["id_produto"]: p
                for p in supabase.table("produto").select("id_produto, nome, preco").execute().data}
    itens_por_pedido = {}
    for item in supabase.table("item_pedido").select("*").execute().data:
        itens_por_pedido.setdefault(item["id_pedido"], []).append(item)

    vendas, faturamento = [], 0.0
    for pedido in pedidos:
        total, resumo = 0.0, []
        for item in itens_por_pedido.get(pedido["id_pedido"], []):
            produto = produtos.get(item["id_produto"])
            if not produto:
                continue
            total += float(produto["preco"]) * item["quantidade"]
            resumo.append(f"{produto['nome']} x{item['quantidade']}")
        faturamento += total
        vendas.append({
            "id_pedido": pedido["id_pedido"],
            "data": str(pedido.get("data_pedido") or "")[:16].replace("T", " "),
            "cliente": clientes.get(pedido["id_cliente"], "-"),
            "itens": ", ".join(resumo),
            "pagamento": pedido.get("pagamento") or "-",
            "total": total,
        })

    r.setex(CHAVE_RELATORIO, config.TEMPO_CACHE, json.dumps({"vendas": vendas, "faturamento": faturamento}))
    return vendas, faturamento, "Supabase (salvo no Redis)"
