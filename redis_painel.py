"""Funções de apoio ao Painel Redis da interface (inspeção das chaves e teste de desempenho)."""

import json
import time

import produto_service
from conexoes import r


def ping():
    return r.ping()


def chaves():
    """Lista (chave, tipo, ttl) de tudo o que existe no Redis."""
    resultado = []
    for chave in sorted(r.scan_iter("*")):
        resultado.append((chave, r.type(chave), r.ttl(chave)))
    return resultado


def valor_formatado(chave):
    """Retorna o conteúdo de uma chave em texto legível."""
    tipo = r.type(chave)
    if tipo == "string":
        bruto = r.get(chave) or ""
        try:
            return json.dumps(json.loads(bruto), indent=2, ensure_ascii=False)[:4000]
        except ValueError:
            return bruto[:4000]
    if tipo == "hash":
        return "\n".join(f"{campo}: {valor}" for campo, valor in r.hgetall(chave).items())
    return f"(tipo {tipo})"


def teste_desempenho():
    """
    Compara o tempo da mesma consulta feita no Supabase e no Redis.
    Retorna (ms_supabase, origem1, ms_redis, origem2).
    """
    produto_service.invalidar_cache()

    inicio = time.perf_counter()
    _, origem1 = produto_service.listar()
    ms_supabase = (time.perf_counter() - inicio) * 1000

    inicio = time.perf_counter()
    _, origem2 = produto_service.listar()
    ms_redis = (time.perf_counter() - inicio) * 1000

    return ms_supabase, origem1, ms_redis, origem2
