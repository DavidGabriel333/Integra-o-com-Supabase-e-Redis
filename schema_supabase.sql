-- ============================================================
-- Tabelas do sistema de loja de suplementos no Supabase
-- (mesma estrutura do ddl.sql do projeto original)
-- Execute no painel do Supabase: SQL Editor > New query > Run
-- ============================================================

CREATE TABLE cliente (
    id_cliente SERIAL PRIMARY KEY,
    nome       VARCHAR,
    email      VARCHAR UNIQUE,
    telefone   VARCHAR,
    endereco   TEXT,
    senha      VARCHAR,
    tipo       VARCHAR(10) NOT NULL DEFAULT 'CLIENTE' CHECK (tipo IN ('CLIENTE', 'GERENTE'))
);

CREATE TABLE produto (
    id_produto SERIAL PRIMARY KEY,
    nome       VARCHAR UNIQUE,
    marca      VARCHAR,
    preco      DECIMAL,
    estoque    INT
);

CREATE TABLE pedido (
    id_pedido   SERIAL PRIMARY KEY,
    id_cliente  INT REFERENCES cliente(id_cliente),
    data_pedido TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status      VARCHAR,
    pagamento   VARCHAR
);

CREATE TABLE item_pedido (
    id_item    SERIAL PRIMARY KEY,
    id_pedido  INT REFERENCES pedido(id_pedido),
    id_produto INT REFERENCES produto(id_produto),
    quantidade INT
);

-- Para a atividade acadêmica, o acesso pela chave pública fica liberado
-- desativando o RLS (Row Level Security). Em um sistema real, use policies.
ALTER TABLE cliente     DISABLE ROW LEVEL SECURITY;
ALTER TABLE produto     DISABLE ROW LEVEL SECURITY;
ALTER TABLE pedido      DISABLE ROW LEVEL SECURITY;
ALTER TABLE item_pedido DISABLE ROW LEVEL SECURITY;

-- Dados de exemplo
INSERT INTO cliente (nome, email, telefone, endereco, senha, tipo) VALUES
    ('Cliente Teste', 'cliente@email.com', '00000-0000', 'Rua Exemplo, 100', '123', 'CLIENTE'),
    ('Maria Souza',   'maria@email.com',   '00000-0001', 'Rua Exemplo, 200', '123', 'CLIENTE');

INSERT INTO produto (nome, marca, preco, estoque) VALUES
    ('Whey Protein 900g', 'Marca Alpha', 129.90, 20),
    ('Creatina 300g',     'Marca Beta',   89.90, 15),
    ('BCAA 120 caps',     'Marca Alpha',  59.90, 30),
    ('Pré-treino 300g',   'Marca Gama',   99.90, 12);
