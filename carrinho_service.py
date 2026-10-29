"""
Carrinho de compras guardado no Redis e finalização do pedido no Supabase.

O carrinho de cada cliente é um HASH no Redis:
    chave:  carrinho:<id_cliente>
    campos: <id_produto> -> <quantidade>
    expira em config.TEMPO_CARRINHO segundos (renovado a cada alteração).

Ao finalizar, o pedido e os itens são gravados no Supabase (tabelas pedido e
item_pedido), o estoque é atualizado e o carrinho é apagado do Redis.
"""

import config
import produto_service
from conexoes import r, supabase


def _chave(id_cliente):
    return f"carrinho:{id_cliente}"


def listar_clientes():
    return supabase.table("cliente").select("id_cliente, nome").order("id_cliente").execute().data


def adicionar(id_cliente, id_produto, quantidade):
    """Retorna (sucesso, mensagem)."""
    if quantidade <= 0:
        return False, "A quantidade deve ser maior que zero."

    produto, _ = produto_service.buscar_por_id(id_produto)
    if not produto:
        return False, "Produto não encontrado."

    chave = _chave(id_cliente)
    no_carrinho = int(r.hget(chave, str(id_produto)) or 0)
    if no_carrinho + quantidade > produto["estoque"]:
        return False, (f"Estoque insuficiente (disponível: {produto['estoque']}, "
                       f"já no carrinho: {no_carrinho}).")

    r.hincrby(chave, str(id_produto), quantidade)
    r.expire(chave, config.TEMPO_CARRINHO)
    return True, f"{produto['nome']} adicionado ao carrinho."


def ver(id_cliente):
    """Retorna (lista_de_itens, total, segundos_para_expirar)."""
    chave = _chave(id_cliente)
    itens, total = [], 0.0
    for id_produto, quantidade in r.hgetall(chave).items():
        produto, _ = produto_service.buscar_por_id(int(id_produto))
        if not produto:
            continue
        subtotal = float(produto["preco"]) * int(quantidade)
        total += subtotal
        itens.append({
            "id_produto": produto["id_produto"],
            "nome": produto["nome"],
            "preco": float(produto["preco"]),
            "quantidade": int(quantidade),
            "subtotal": subtotal,
        })
    itens.sort(key=lambda i: i["id_produto"])
    ttl = r.ttl(chave) if itens else None
    return itens, total, ttl


def remover_item(id_cliente, id_produto):
    return r.hdel(_chave(id_cliente), str(id_produto)) > 0


def limpar(id_cliente):
    r.delete(_chave(id_cliente))


def finalizar(id_cliente, pagamento):
    """
    Grava o pedido no Supabase. Retorna (id_pedido, total).
    Levanta ValueError para erros de validação (cliente, carrinho vazio, estoque).
    """
    cliente = supabase.table("cliente").select("id_cliente").eq("id_cliente", id_cliente).execute().data
    if not cliente:
        raise ValueError("Cliente não encontrado.")

    no_carrinho = r.hgetall(_chave(id_cliente))
    if not no_carrinho:
        raise ValueError("O carrinho está vazio.")

    # Confere estoque e preço direto no Supabase (nunca pelo cache)
    itens, total = [], 0.0
    for id_produto, quantidade in no_carrinho.items():
        quantidade = int(quantidade)
        dados = (supabase.table("produto").select("id_produto, nome, preco, estoque")
                 .eq("id_produto", int(id_produto)).execute().data)
        if not dados:
            raise ValueError(f"O produto {id_produto} não existe mais.")
        produto = dados[0]
        if produto["estoque"] < quantidade:
            raise ValueError(f"Estoque insuficiente para {produto['nome']} "
                             f"(disponível: {produto['estoque']}, pedido: {quantidade}).")
        itens.append((produto, quantidade))
        total += float(produto["preco"]) * quantidade

    pedido = supabase.table("pedido").insert({
        "id_cliente": id_cliente,
        "status": "FINALIZADO",
        "pagamento": pagamento,
    }).execute().data[0]
    id_pedido = pedido["id_pedido"]

    baixas = []  # estoques já alterados, para desfazer em caso de erro
    try:
        supabase.table("item_pedido").insert([
            {"id_pedido": id_pedido, "id_produto": p["id_produto"], "quantidade": q}
            for p, q in itens
        ]).execute()
        for produto, quantidade in itens:
            novo_estoque = produto["estoque"] - quantidade
            supabase.table("produto").update({"estoque": novo_estoque}).eq(
                "id_produto", produto["id_produto"]).execute()
            baixas.append((produto["id_produto"], produto["estoque"]))
    except Exception:
        for id_produto, estoque_original in baixas:
            supabase.table("produto").update({"estoque": estoque_original}).eq(
                "id_produto", id_produto).execute()
        supabase.table("item_pedido").delete().eq("id_pedido", id_pedido).execute()
        supabase.table("pedido").delete().eq("id_pedido", id_pedido).execute()
        raise

    limpar(id_cliente)
    produto_service.invalidar_cache()  # estoque e vendas mudaram
    return id_pedido, total
