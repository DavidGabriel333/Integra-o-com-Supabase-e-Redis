"""
CRUD de produtos no Supabase, com cache no Redis.

Leitura  (listar / buscar por ID): tenta o Redis; se não achar, consulta o Supabase
                                   e grava o resultado no Redis com expiração (SETEX).
Escrita  (cadastrar / atualizar / excluir): altera o Supabase e apaga o cache
                                   (invalidação), para a próxima leitura vir atualizada.
"""

import json

import config
from conexoes import r, supabase

TABELA = "produto"
CHAVE_LISTA = "produtos:lista"
PREFIXO_PRODUTO = "produto:"

# Chaves de cache que dependem dos dados do Supabase (o carrinho não entra aqui)
PADROES_CACHE = ("produtos:*", "produto:*", "vendas:*")


# ----------------------------- cache -----------------------------
def invalidar_cache():
    """Remove do Redis o cache de produtos e do relatório de vendas. Retorna quantas chaves apagou."""
    chaves = []
    for padrao in PADROES_CACHE:
        chaves.extend(r.scan_iter(padrao))
    if chaves:
        r.delete(*chaves)
    return len(chaves)


# ----------------------------- READ -----------------------------
def listar():
    """Retorna (lista_de_produtos, origem)."""
    cache = r.get(CHAVE_LISTA)
    if cache:
        return json.loads(cache), "Redis (cache)"

    dados = supabase.table(TABELA).select("*").order("id_produto").execute().data
    r.setex(CHAVE_LISTA, config.TEMPO_CACHE, json.dumps(dados))
    return dados, "Supabase (salvo no Redis)"


def buscar_por_id(id_produto):
    """Retorna (produto ou None, origem)."""
    chave = f"{PREFIXO_PRODUTO}{id_produto}"
    cache = r.get(chave)
    if cache:
        return json.loads(cache), "Redis (cache)"

    dados = supabase.table(TABELA).select("*").eq("id_produto", id_produto).execute().data
    if not dados:
        return None, "Supabase"
    r.setex(chave, config.TEMPO_CACHE, json.dumps(dados[0]))
    return dados[0], "Supabase (salvo no Redis)"


def buscar_por_nome(termo):
    """Busca por parte do nome (consulta direta ao Supabase, sem cache)."""
    return (supabase.table(TABELA).select("*").ilike("nome", f"%{termo}%")
            .order("id_produto").execute().data)


# ----------------------------- CREATE -----------------------------
def cadastrar(nome, marca, preco, estoque):
    produto = {"nome": nome, "marca": marca, "preco": preco, "estoque": estoque}
    resultado = supabase.table(TABELA).insert(produto).execute()
    invalidar_cache()
    return resultado.data[0] if resultado.data else produto


# ----------------------------- UPDATE -----------------------------
def atualizar(id_produto, campos):
    existe = supabase.table(TABELA).select("id_produto").eq("id_produto", id_produto).execute().data
    if not existe:
        return False
    supabase.table(TABELA).update(campos).eq("id_produto", id_produto).execute()
    invalidar_cache()
    return True


# ----------------------------- DELETE -----------------------------
def excluir(id_produto):
    existe = supabase.table(TABELA).select("id_produto").eq("id_produto", id_produto).execute().data
    if not existe:
        return False
    supabase.table(TABELA).delete().eq("id_produto", id_produto).execute()
    invalidar_cache()
    return True
