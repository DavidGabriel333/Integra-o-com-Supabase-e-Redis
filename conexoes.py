"""Cria as conexões com o Supabase (banco de dados) e com o Redis (cache e carrinho)."""

import redis
from supabase import create_client

import config

supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

r = redis.Redis(
    host=config.REDIS_HOST,
    port=config.REDIS_PORT,
    username=config.REDIS_USER,
    password=config.REDIS_PASSWORD,
    ssl=config.REDIS_SSL,
    decode_responses=True,
)
