"""
Configurações lidas de variáveis de ambiente.

Os valores ficam no arquivo ".env" (que não vai para o GitHub). Use o
".env.example" como modelo. Nenhuma senha ou chave fica escrita no código.
"""

import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")


class ConfigErro(RuntimeError):
    """Variável de ambiente ausente ou inválida."""


def _obrigatoria(nome):
    valor = os.getenv(nome, "").strip()
    if not valor or valor.startswith("COLE_AQUI"):
        raise ConfigErro(
            f"A variável {nome} não foi preenchida.\n"
            "Copie o arquivo .env.example para .env e preencha os dados "
            "do Supabase e do Redis."
        )
    return valor


def _inteiro(nome, padrao=None):
    bruto = os.getenv(nome, "").strip()
    if not bruto and padrao is not None:
        return padrao
    try:
        return int(bruto)
    except ValueError:
        raise ConfigErro(f"A variável {nome} deve ser um número inteiro (valor atual: '{bruto}').")


def _url_supabase():
    """Valida o endereço do projeto: precisa ser https://SEU-ID.supabase.co"""
    url = _obrigatoria("SUPABASE_URL").strip("\"'").rstrip("/")
    for sufixo in ("/rest/v1", "/rest"):
        if url.lower().endswith(sufixo):
            url = url[: -len(sufixo)]
    if not re.fullmatch(r"https://[a-z0-9-]+\.supabase\.co", url.lower()):
        raise ConfigErro(
            f"A SUPABASE_URL parece incorreta: {url}\n\n"
            "Ela deve ter o formato https://SEU-ID-DO-PROJETO.supabase.co\n"
            "Não use o endereço do painel (supabase.com/dashboard/...).\n"
            "O ID do projeto aparece em Project Settings > General (Project ID)."
        )
    return url


# --- Supabase ---
SUPABASE_URL = _url_supabase()
SUPABASE_KEY = _obrigatoria("SUPABASE_KEY")

# --- Redis ---
REDIS_HOST = _obrigatoria("REDIS_HOST")
REDIS_PORT = _inteiro("REDIS_PORT")
REDIS_USER = os.getenv("REDIS_USER", "default").strip() or "default"
REDIS_PASSWORD = _obrigatoria("REDIS_PASSWORD")
REDIS_SSL = os.getenv("REDIS_SSL", "false").strip().lower() in ("1", "true", "sim", "yes")

# --- Tempos de expiração (segundos) ---
TEMPO_CACHE = _inteiro("TEMPO_CACHE", 60)
TEMPO_CARRINHO = _inteiro("TEMPO_CARRINHO", 1800)
