# Loja de Suplementos - Supabase + Redis

Segue o link do video de aprensetação: https://drive.google.com/file/d/15jPa44YHohRY1HlqQZRGJeeYx4j24Qzp/view?usp=sharing

Aplicação desktop com interface gráfica que integra **Supabase** (banco de dados PostgreSQL na nuvem) e **Redis** (cache e carrinho de compras) para gerenciar produtos, carrinho e vendas de uma loja de suplementos.

Trabalho individual da disciplina de Banco de Dados. Evolui o sistema da loja de suplementos desenvolvido anteriormente (clientes, produtos, pedidos e itens), acrescentando a persistência em nuvem e o uso do Redis.

## Problema que o projeto resolve

Uma loja precisa consultar o catálogo de produtos e o relatório de vendas o tempo todo, e esses dados mudam pouco em comparação com a quantidade de consultas. Fazer uma ida ao banco de dados na nuvem a cada clique deixa a aplicação lenta e sobrecarrega o banco. Além disso, o carrinho de compras é um dado temporário que não deveria ficar misturado aos pedidos definitivos.

## Objetivo e principais funcionalidades

**Objetivo:** aplicar na prática persistência de dados, integração entre tecnologias e uso do Redis, com uma interface gráfica para o usuário.

| Aba | Funcionalidade |
|---|---|
| **Produtos** | Cadastrar, listar, consultar, atualizar e excluir produtos; busca por nome |
| **Loja / Carrinho** | Escolher o cliente, adicionar produtos ao carrinho, remover itens, ver o total e o tempo para o carrinho expirar, finalizar o pedido |
| **Vendas** | Relatório de pedidos com itens, cliente, forma de pagamento, total por pedido e faturamento total |
| **Painel Redis** | Estado da conexão, chaves existentes com tipo e tempo de expiração, conteúdo de cada chave, limpeza do cache e teste de desempenho Supabase x Redis |

Em todas as telas, o rodapé mostra a **origem dos dados** (Redis ou Supabase) e o tempo da operação em milissegundos.

## Tecnologias utilizadas

- **Python 3** e **Tkinter** (interface gráfica, já incluído no Python)
- **Supabase** (PostgreSQL na nuvem) com a biblioteca `supabase`
- **Redis Cloud** com a biblioteca `redis`
- **python-dotenv** (leitura das variáveis de ambiente)

## Instalação, configuração e execução

### 1. Pré-requisitos
- Python 3 instalado (marque "Add python.exe to PATH" na instalação)
- Conta e projeto no [Supabase](https://supabase.com)
- Conta e banco gratuito no [Redis Cloud](https://cloud.redis.io)

### 2. Instalar as dependências
```bash
python -m pip install -r requirements.txt
```

### 3. Criar as tabelas no Supabase
No painel do Supabase, abra **SQL Editor**, cole o conteúdo de [`database/schema_supabase.sql`](database/schema_supabase.sql) e execute. O script cria as tabelas `cliente`, `produto`, `pedido` e `item_pedido` e insere dados de exemplo.

### 4. Configurar as variáveis de ambiente
Copie o arquivo de exemplo e preencha com os seus dados:

```bash
# Windows (PowerShell)
copy .env.example .env
```

| Variável | Onde encontrar |
|---|---|
| `SUPABASE_URL` | Supabase > Project Settings > API (URL do projeto) |
| `SUPABASE_KEY` | Supabase > Project Settings > API Keys (chave *publishable* ou *anon*) |
| `REDIS_HOST` e `REDIS_PORT` | Redis Cloud > banco de dados > Connect (endpoint `host:porta`) |
| `REDIS_USER` | normalmente `default` |
| `REDIS_PASSWORD` | Redis Cloud > banco de dados > Security (senha do usuário padrão) |
| `REDIS_SSL` | `false` para bancos gratuitos sem TLS; `true` se o seu exigir |

O arquivo `.env` está no `.gitignore`: **senhas e chaves nunca vão para o repositório.**

### 5. Executar
```bash
python main.py
```

## Integração com o Supabase

O Supabase é a **fonte principal e persistente dos dados**. A aplicação se comunica com ele pela API oficial (`supabase-py`), sem montar SQL manualmente.

| Operação | Método | Onde é usado |
|---|---|---|
| Cadastrar | `insert()` | Novo produto; gravação do pedido e dos itens |
| Consultar | `select()` | Listagem, relatório de vendas, clientes |
| Filtrar | `eq()` e `ilike()` | Produto por ID; busca por parte do nome |
| Atualizar | `update()` | Edição de produto; baixa de estoque ao finalizar pedido |
| Excluir | `delete()` | Exclusão de produto |

Funcionalidades práticas que usam os dados armazenados:
- **Finalizar pedido:** confere estoque e preço direto no banco, grava `pedido` e `item_pedido`, atualiza o estoque e desfaz as alterações se algum passo falhar.
- **Relatório de vendas:** cruza pedidos, itens, clientes e produtos para calcular o total de cada venda e o faturamento.

Código: `produto_service.py`, `carrinho_service.py` e `venda_service.py`.

## Onde e como o Redis foi utilizado, e por que foi escolhido

O Redis é um banco de dados em memória, baseado em chave-valor, com acesso muito rápido e suporte a expiração automática. Ele foi usado em **três pontos** da aplicação:

| Uso | Onde na aplicação | Chave no Redis | Comandos | Expira em |
|---|---|---|---|---|
| **1. Cache de produtos** | Aba Produtos e lista da aba Loja | `produtos:lista`, `produto:<id>` | `SETEX`, `GET`, `DEL` | 60 s |
| **2. Carrinho de compras** | Aba Loja / Carrinho | `carrinho:<id_cliente>` (hash) | `HINCRBY`, `HGETALL`, `HDEL`, `EXPIRE`, `TTL` | 30 min (renovado a cada alteração) |
| **3. Cache do relatório de vendas** | Aba Vendas | `vendas:relatorio` | `SETEX`, `GET`, `DEL` | 60 s |

### Qual problema motivou o uso
- **Lentidão e excesso de consultas:** o catálogo e o relatório de vendas são lidos com muito mais frequência do que são alterados. O relatório, em especial, exige quatro consultas ao Supabase. Guardar o resultado no Redis evita repetir essas consultas.
- **Carrinho é um dado temporário:** ele não precisa ser gravado no banco enquanto o cliente ainda não decidiu comprar. No Redis, o carrinho expira sozinho se for abandonado, sem lixo no banco de dados.

### Como funciona o cache
```
Primeira consulta:   Aplicação -> Supabase -> grava no Redis -> exibe
Consulta seguinte:   Aplicação -> Redis -> exibe  (enquanto não expirar)
Após uma alteração:  cache removido -> a próxima consulta vai ao Supabase
```
Cadastrar, atualizar ou excluir um produto, e finalizar um pedido, **invalidam o cache**. Assim a aplicação nunca mostra estoque, preço ou vendas desatualizados. O carrinho não é apagado nessa limpeza.

### Benefícios
- Menos consultas ao banco de dados na nuvem e respostas mais rápidas nas leituras repetidas.
- Carrinho com expiração automática e sem poluir as tabelas.
- Possibilidade de demonstrar o ganho: o botão **Testar desempenho: Supabase x Redis** do Painel Redis mede a mesma consulta nas duas fontes.

### Por que o Redis não substitui o Supabase
O Supabase continua sendo a fonte confiável dos dados (pedidos, clientes, produtos), com tabelas relacionais e persistência. O Redis guarda apenas cópias temporárias e o carrinho.

## Capturas de tela

Adicione as imagens na pasta `docs/prints/` com estes nomes:

![Aba Produtos](docs/prints/produtos.png)
![Aba Loja / Carrinho](docs/prints/loja.png)
![Aba Vendas](docs/prints/vendas.png)
![Painel Redis](docs/prints/painel_redis.png)

## Estrutura do projeto

```
loja_supabase_redis/
├── main.py                 # ponto de entrada
├── gui.py                  # interface gráfica (Tkinter)
├── config.py               # leitura das variáveis de ambiente
├── conexoes.py             # conexões com Supabase e Redis
├── produto_service.py      # CRUD de produtos (Supabase) + cache (Redis)
├── carrinho_service.py     # carrinho (Redis) + finalização de pedido (Supabase)
├── venda_service.py        # relatório de vendas (Supabase) + cache (Redis)
├── redis_painel.py         # apoio ao Painel Redis
├── database/
│   └── schema_supabase.sql # criação das tabelas e dados de exemplo
├── docs/
│   ├── roteiro_video.md    # roteiro do vídeo demonstrativo
│   └── prints/             # capturas de tela
├── .env.example            # modelo das variáveis de ambiente
├── .gitignore
└── requirements.txt
```

## Limitações

- No projeto original, uma Procedure fazia o pedido em uma única transação no PostgreSQL. Aqui o acesso é pela API do Supabase, que executa cada comando separadamente. Por isso `finalizar()` confere o estoque no banco e desfaz manualmente as alterações se um passo falhar.
- O acesso às tabelas usa a chave pública com o RLS desativado, adequado apenas para fins acadêmicos. Em um sistema real, seriam usadas políticas de acesso e autenticação.
- Os valores de cada item de pedido usam o preço atual do produto, pois a tabela `item_pedido` do projeto original não guarda o preço da venda.
