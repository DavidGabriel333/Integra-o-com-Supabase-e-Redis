"""
Diagnóstico de conexão: confere o .env, o Supabase e o Redis, um passo de cada vez.

Uso:  python testar_conexao.py
(Nenhuma senha ou chave é exibida.)
"""

import sys


def ok(msg):
    print(f"[OK]    {msg}")


def erro(msg):
    print(f"[ERRO]  {msg}")


def testar_env():
    try:
        import config
    except Exception as e:
        erro(f"Arquivo .env: {e}")
        return None
    ok("Arquivo .env lido e variáveis preenchidas.")
    return config


def testar_supabase(config):
    import urllib.error
    import urllib.request

    host = config.SUPABASE_URL.replace("https://", "")
    print(f"\nSupabase -> {host}")
    url = f"{config.SUPABASE_URL}/rest/v1/produto?select=id_produto&limit=1"
    requisicao = urllib.request.Request(url, headers={
        "apikey": config.SUPABASE_KEY, "Authorization": f"Bearer {config.SUPABASE_KEY}"})
    try:
        with urllib.request.urlopen(requisicao, timeout=20) as resp:
            status, tipo, corpo = resp.status, resp.headers.get("Content-Type", ""), resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        status, tipo, corpo = e.code, e.headers.get("Content-Type", ""), e.read().decode("utf-8", "replace")
    except Exception as e:
        erro(f"Não foi possível acessar {host} ({type(e).__name__}). "
             "Confira a SUPABASE_URL (o ID do projeto) e a sua internet.")
        return False

    if "json" not in tipo.lower():
        erro(f"O endereço respondeu (status {status}), mas não é a API do Supabase. "
             "A SUPABASE_URL está errada: use https://SEU-ID.supabase.co")
        return False
    if status in (401, 403):
        erro("A chave foi recusada. Confira a SUPABASE_KEY (use a Publishable key ou, "
             "na aba Legacy API Keys, a chave anon public).")
        return False
    if status == 404 or "PGRST205" in corpo or "42P01" in corpo:
        erro("A conexão e a chave estão certas, mas a tabela 'produto' não existe. "
             "Execute o arquivo database/schema_supabase.sql no SQL Editor do Supabase.")
        return False
    if status != 200:
        erro(f"Resposta inesperada (status {status}): {corpo[:200]}")
        return False
    ok("Conexão, chave e tabela 'produto' funcionando.")
    return True


def testar_redis(config):
    import redis
    from redis.exceptions import AuthenticationError

    print(f"\nRedis -> {config.REDIS_HOST}:{config.REDIS_PORT}")
    r = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, username=config.REDIS_USER,
                    password=config.REDIS_PASSWORD, ssl=config.REDIS_SSL, decode_responses=True,
                    socket_connect_timeout=15, socket_timeout=15)
    try:
        r.ping()
        r.setex("teste:conexao", 10, "ok")
        valor = r.get("teste:conexao")
    except AuthenticationError:
        erro("Usuário ou senha recusados. Confira REDIS_USER (default) e REDIS_PASSWORD.")
        return False
    except Exception as e:
        erro(f"Não foi possível conectar ({type(e).__name__}: {e}). Confira REDIS_HOST, REDIS_PORT "
             "e REDIS_SSL (tente trocar entre false e true).")
        return False
    ok(f"Redis respondeu ao PING e gravou/leu um valor de teste ({valor}).")
    return True


def main():
    config = testar_env()
    if not config:
        return 1
    resultados = [testar_supabase(config), testar_redis(config)]
    print()
    if all(resultados):
        print("Tudo certo! Pode rodar: python main.py")
        return 0
    print("Corrija o item marcado com [ERRO], salve o .env e rode este teste de novo.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
