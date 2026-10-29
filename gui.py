"""
Interface gráfica (Tkinter) da Loja de Suplementos.

Abas:
  Produtos      - CRUD de produtos (Supabase) com lista em cache (Redis)
  Loja/Carrinho - carrinho de compras guardado no Redis; o pedido é gravado no Supabase
  Vendas        - relatório de vendas calculado a partir do Supabase e guardado em cache no Redis
  Painel Redis  - mostra o que existe no Redis, o tempo de expiração e compara Supabase x Redis
"""

import functools
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

import carrinho_service as cs
import produto_service as ps
import redis_painel as rp
import venda_service as vs

COR_REDIS = "#b3261e"
COR_SUPABASE = "#1f7a4d"
COR_TITULO = "#1f3a5f"


# ----------------------------- utilitários -----------------------------
def moeda(valor):
    texto = f"{float(valor):,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def medir(funcao, *args, **kwargs):
    """Executa a função e retorna (resultado, milissegundos)."""
    inicio = time.perf_counter()
    resultado = funcao(*args, **kwargs)
    return resultado, (time.perf_counter() - inicio) * 1000


def cor_origem(origem):
    return COR_REDIS if origem.startswith("Redis") else COR_SUPABASE


def seguro(funcao):
    """Mostra mensagens amigáveis em vez de deixar a janela travar com um erro."""
    @functools.wraps(funcao)
    def interno(self, *args, **kwargs):
        try:
            return funcao(self, *args, **kwargs)
        except ValueError as erro:
            messagebox.showwarning("Atenção", str(erro))
        except Exception as erro:
            self.app.registrar(f"ERRO: {type(erro).__name__}: {erro}")
            messagebox.showerror("Erro", f"{type(erro).__name__}: {erro}")
    return interno


def criar_tabela(pai, colunas, altura=10):
    """Cria um Treeview com barra de rolagem. colunas = [(id, titulo, largura, alinhamento)]."""
    quadro = ttk.Frame(pai)
    tabela = ttk.Treeview(quadro, columns=[c[0] for c in colunas], show="headings",
                          height=altura, selectmode="browse")
    for ident, titulo, largura, alinhamento in colunas:
        tabela.heading(ident, text=titulo)
        tabela.column(ident, width=largura, anchor=alinhamento, stretch=True)
    barra = ttk.Scrollbar(quadro, orient="vertical", command=tabela.yview)
    tabela.configure(yscrollcommand=barra.set)
    tabela.pack(side="left", fill="both", expand=True)
    barra.pack(side="right", fill="y")
    return quadro, tabela


class AbaBase(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app

    def ao_exibir(self):
        pass


# ----------------------------- aba Produtos -----------------------------
class AbaProdutos(AbaBase):
    def __init__(self, master, app):
        super().__init__(master, app)
        self.dados = {}

        form = ttk.LabelFrame(self, text="Dados do produto", padding=10)
        form.pack(fill="x")
        self.v_nome, self.v_marca = tk.StringVar(), tk.StringVar()
        self.v_preco, self.v_estoque = tk.StringVar(), tk.StringVar()
        campos = [("Nome:", self.v_nome, 28), ("Marca:", self.v_marca, 18),
                  ("Preço (R$):", self.v_preco, 10), ("Estoque:", self.v_estoque, 8)]
        for coluna, (rotulo, variavel, largura) in enumerate(campos):
            ttk.Label(form, text=rotulo).grid(row=0, column=coluna * 2, sticky="e", padx=(8, 4))
            ttk.Entry(form, textvariable=variavel, width=largura).grid(row=0, column=coluna * 2 + 1, sticky="w")

        botoes = ttk.Frame(form)
        botoes.grid(row=1, column=0, columnspan=8, sticky="w", pady=(10, 0))
        ttk.Button(botoes, text="Cadastrar", style="Primario.TButton", command=self.cadastrar).pack(side="left", padx=4)
        ttk.Button(botoes, text="Atualizar selecionado", command=self.atualizar).pack(side="left", padx=4)
        ttk.Button(botoes, text="Excluir selecionado", command=self.excluir).pack(side="left", padx=4)
        ttk.Button(botoes, text="Limpar campos", command=self.limpar).pack(side="left", padx=4)

        busca = ttk.Frame(self)
        busca.pack(fill="x", pady=(12, 6))
        ttk.Label(busca, text="Buscar por nome:").pack(side="left")
        self.v_busca = tk.StringVar()
        entrada = ttk.Entry(busca, textvariable=self.v_busca, width=28)
        entrada.pack(side="left", padx=6)
        entrada.bind("<Return>", lambda _e: self.buscar())
        ttk.Button(busca, text="Buscar (Supabase)", command=self.buscar).pack(side="left", padx=4)
        ttk.Button(busca, text="Listar todos", command=self.carregar).pack(side="left", padx=4)

        quadro, self.tabela = criar_tabela(self, [
            ("id", "ID", 60, "center"), ("nome", "Nome", 280, "w"), ("marca", "Marca", 160, "w"),
            ("preco", "Preço", 110, "e"), ("estoque", "Estoque", 90, "center")], altura=14)
        quadro.pack(fill="both", expand=True)
        self.tabela.bind("<<TreeviewSelect>>", self._selecionar)

    def ao_exibir(self):
        self.carregar()

    def _preencher(self, produtos):
        self.dados = {p["id_produto"]: p for p in produtos}
        self.tabela.delete(*self.tabela.get_children())
        for p in produtos:
            self.tabela.insert("", "end", iid=str(p["id_produto"]),
                               values=(p["id_produto"], p["nome"], p["marca"], moeda(p["preco"]), p["estoque"]))

    def _selecionar(self, _evento=None):
        selecao = self.tabela.selection()
        if not selecao:
            return
        p = self.dados.get(int(selecao[0]))
        if p:
            self.v_nome.set(p["nome"])
            self.v_marca.set(p["marca"])
            self.v_preco.set(f"{float(p['preco']):.2f}")
            self.v_estoque.set(str(p["estoque"]))

    def _ler_formulario(self):
        nome, marca = self.v_nome.get().strip(), self.v_marca.get().strip()
        if not nome or not marca:
            raise ValueError("Preencha o nome e a marca do produto.")
        try:
            preco = float(self.v_preco.get().replace(",", "."))
            estoque = int(self.v_estoque.get())
        except ValueError:
            raise ValueError("Preço deve ser um número (ex.: 89.90) e estoque deve ser um número inteiro.")
        if preco < 0 or estoque < 0:
            raise ValueError("Preço e estoque não podem ser negativos.")
        return {"nome": nome, "marca": marca, "preco": preco, "estoque": estoque}

    def _id_selecionado(self):
        selecao = self.tabela.selection()
        if not selecao:
            raise ValueError("Selecione um produto na tabela.")
        return int(selecao[0])

    def limpar(self):
        for variavel in (self.v_nome, self.v_marca, self.v_preco, self.v_estoque):
            variavel.set("")
        self.tabela.selection_remove(self.tabela.selection())

    @seguro
    def carregar(self):
        (produtos, origem), ms = medir(ps.listar)
        self._preencher(produtos)
        self.app.mostrar(f"{len(produtos)} produto(s) listado(s)", origem, ms)

    @seguro
    def buscar(self):
        termo = self.v_busca.get().strip()
        if not termo:
            return self.carregar()
        produtos, ms = medir(ps.buscar_por_nome, termo)
        self._preencher(produtos)
        self.app.mostrar(f"{len(produtos)} produto(s) encontrado(s) para '{termo}'", "Supabase (busca direta)", ms)

    @seguro
    def cadastrar(self):
        campos = self._ler_formulario()
        try:
            ps.cadastrar(**campos)
        except Exception as erro:
            if "duplicate" in str(erro).lower() or "unique" in str(erro).lower():
                raise ValueError("Já existe um produto com esse nome.")
            raise
        self.app.registrar("Produto cadastrado no Supabase; cache do Redis invalidado.")
        self.limpar()
        self.carregar()
        messagebox.showinfo("Sucesso", "Produto cadastrado com sucesso!")

    @seguro
    def atualizar(self):
        id_produto = self._id_selecionado()
        campos = self._ler_formulario()
        if not ps.atualizar(id_produto, campos):
            raise ValueError("Produto não encontrado.")
        self.app.registrar(f"Produto {id_produto} atualizado no Supabase; cache do Redis invalidado.")
        self.carregar()
        messagebox.showinfo("Sucesso", "Produto atualizado com sucesso!")

    @seguro
    def excluir(self):
        id_produto = self._id_selecionado()
        nome = self.dados[id_produto]["nome"]
        if not messagebox.askyesno("Confirmar exclusão", f"Excluir o produto '{nome}'?"):
            return
        try:
            ps.excluir(id_produto)
        except Exception as erro:
            if "foreign key" in str(erro).lower() or "violates" in str(erro).lower():
                raise ValueError("Esse produto já aparece em pedidos e não pode ser excluído.")
            raise
        self.app.registrar(f"Produto {id_produto} excluído do Supabase; cache do Redis invalidado.")
        self.limpar()
        self.carregar()


# ----------------------------- aba Loja / Carrinho -----------------------------
class AbaLoja(AbaBase):
    def __init__(self, master, app):
        super().__init__(master, app)
        self.clientes = {}
        self.ttl = 0

        topo = ttk.Frame(self)
        topo.pack(fill="x")
        ttk.Label(topo, text="Cliente:").pack(side="left")
        self.cb_cliente = ttk.Combobox(topo, state="readonly", width=34)
        self.cb_cliente.pack(side="left", padx=6)
        self.cb_cliente.bind("<<ComboboxSelected>>", lambda _e: self.atualizar_carrinho())
        ttk.Button(topo, text="Recarregar clientes", command=self.carregar_clientes).pack(side="left", padx=4)

        corpo = ttk.Frame(self)
        corpo.pack(fill="both", expand=True, pady=(10, 0))
        corpo.columnconfigure(0, weight=1)
        corpo.columnconfigure(1, weight=1)
        corpo.rowconfigure(0, weight=1)

        esquerda = ttk.LabelFrame(corpo, text="Produtos disponíveis", padding=8)
        esquerda.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        quadro, self.tab_produtos = criar_tabela(esquerda, [
            ("id", "ID", 45, "center"), ("nome", "Produto", 190, "w"),
            ("preco", "Preço", 85, "e"), ("estoque", "Estoque", 60, "center")], altura=12)
        quadro.pack(fill="both", expand=True)
        linha = ttk.Frame(esquerda)
        linha.pack(fill="x", pady=(8, 0))
        ttk.Label(linha, text="Quantidade:").pack(side="left")
        self.sp_qtd = ttk.Spinbox(linha, from_=1, to=999, width=5)
        self.sp_qtd.set(1)
        self.sp_qtd.pack(side="left", padx=6)
        ttk.Button(linha, text="Adicionar ao carrinho", style="Primario.TButton",
                   command=self.adicionar).pack(side="left", padx=4)

        direita = ttk.LabelFrame(corpo, text="Carrinho (armazenado no Redis)", padding=8)
        direita.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        quadro, self.tab_carrinho = criar_tabela(direita, [
            ("id", "ID", 45, "center"), ("nome", "Produto", 170, "w"),
            ("qtd", "Qtd", 45, "center"), ("subtotal", "Subtotal", 95, "e")], altura=9)
        quadro.pack(fill="both", expand=True)
        self.lbl_total = ttk.Label(direita, text="Total: R$ 0,00", style="Total.TLabel")
        self.lbl_total.pack(anchor="e", pady=(8, 0))
        self.lbl_expira = ttk.Label(direita, text="", style="Sub.TLabel")
        self.lbl_expira.pack(anchor="e")
        acoes = ttk.Frame(direita)
        acoes.pack(fill="x", pady=(8, 0))
        ttk.Button(acoes, text="Remover item", command=self.remover).pack(side="left", padx=2)
        ttk.Button(acoes, text="Esvaziar", command=self.esvaziar).pack(side="left", padx=2)
        fim = ttk.Frame(direita)
        fim.pack(fill="x", pady=(8, 0))
        ttk.Label(fim, text="Pagamento:").pack(side="left")
        self.cb_pagamento = ttk.Combobox(fim, state="readonly", values=["PIX", "CARTAO"], width=9)
        self.cb_pagamento.set("PIX")
        self.cb_pagamento.pack(side="left", padx=6)
        ttk.Button(fim, text="Finalizar pedido (grava no Supabase)", style="Primario.TButton",
                   command=self.finalizar).pack(side="left", padx=4)

        self.after(1000, self._tick)

    def ao_exibir(self):
        if not self.clientes:
            self.carregar_clientes()
        self.atualizar_produtos()
        self.atualizar_carrinho()

    def _id_cliente(self):
        escolhido = self.cb_cliente.get()
        if not escolhido:
            raise ValueError("Selecione um cliente.")
        return self.clientes[escolhido]

    def _tick(self):
        """Contagem regressiva local do tempo de vida do carrinho (TTL do Redis)."""
        if self.ttl and self.ttl > 0:
            self.ttl -= 1
            self._mostrar_ttl()
            if self.ttl == 0:
                try:
                    self.atualizar_carrinho()
                except Exception:
                    pass
        self.after(1000, self._tick)

    def _mostrar_ttl(self):
        if self.ttl and self.ttl > 0:
            minutos, segundos = divmod(self.ttl, 60)
            self.lbl_expira.config(text=f"Expira em {minutos:02d}:{segundos:02d} sem novas alterações (TTL do Redis)")
        else:
            self.lbl_expira.config(text="")

    @seguro
    def carregar_clientes(self):
        lista = cs.listar_clientes()
        self.clientes = {f"{c['id_cliente']} - {c['nome']}": c["id_cliente"] for c in lista}
        self.cb_cliente["values"] = list(self.clientes)
        if self.clientes and not self.cb_cliente.get():
            self.cb_cliente.current(0)
        self.app.registrar(f"{len(lista)} cliente(s) carregado(s) do Supabase.")

    @seguro
    def atualizar_produtos(self):
        (produtos, origem), ms = medir(ps.listar)
        self.tab_produtos.delete(*self.tab_produtos.get_children())
        for p in produtos:
            self.tab_produtos.insert("", "end", iid=str(p["id_produto"]),
                                     values=(p["id_produto"], p["nome"], moeda(p["preco"]), p["estoque"]))
        self.app.mostrar("Produtos disponíveis atualizados", origem, ms)

    @seguro
    def atualizar_carrinho(self):
        self.tab_carrinho.delete(*self.tab_carrinho.get_children())
        if not self.cb_cliente.get():
            self.lbl_total.config(text="Total: R$ 0,00")
            self.ttl = 0
            self._mostrar_ttl()
            return
        (itens, total, ttl), ms = medir(cs.ver, self._id_cliente())
        for i in itens:
            self.tab_carrinho.insert("", "end", iid=str(i["id_produto"]),
                                     values=(i["id_produto"], i["nome"], i["quantidade"], moeda(i["subtotal"])))
        self.lbl_total.config(text=f"Total: {moeda(total)}")
        self.ttl = ttl if ttl and ttl > 0 else 0
        self._mostrar_ttl()
        self.app.mostrar(f"Carrinho lido do Redis: {len(itens)} item(ns)", "Redis (carrinho)", ms)

    @seguro
    def adicionar(self):
        id_cliente = self._id_cliente()
        selecao = self.tab_produtos.selection()
        if not selecao:
            raise ValueError("Selecione um produto na lista da esquerda.")
        try:
            quantidade = int(self.sp_qtd.get())
        except ValueError:
            raise ValueError("A quantidade deve ser um número inteiro.")
        (ok, mensagem), ms = medir(cs.adicionar, id_cliente, int(selecao[0]), quantidade)
        if not ok:
            raise ValueError(mensagem)
        self.app.mostrar(mensagem, "Redis (carrinho)", ms)
        self.atualizar_carrinho()

    @seguro
    def remover(self):
        id_cliente = self._id_cliente()
        selecao = self.tab_carrinho.selection()
        if not selecao:
            raise ValueError("Selecione um item no carrinho.")
        cs.remover_item(id_cliente, int(selecao[0]))
        self.atualizar_carrinho()

    @seguro
    def esvaziar(self):
        cs.limpar(self._id_cliente())
        self.atualizar_carrinho()

    @seguro
    def finalizar(self):
        id_cliente = self._id_cliente()
        (id_pedido, total), ms = medir(cs.finalizar, id_cliente, self.cb_pagamento.get())
        self.app.mostrar(f"Pedido {id_pedido} gravado no Supabase", "Supabase", ms)
        self.app.registrar("Carrinho removido do Redis; cache de produtos e vendas invalidado.")
        self.atualizar_produtos()
        self.atualizar_carrinho()
        messagebox.showinfo("Pedido finalizado", f"Pedido {id_pedido} finalizado!\nTotal: {moeda(total)}")


# ----------------------------- aba Vendas -----------------------------
class AbaVendas(AbaBase):
    def __init__(self, master, app):
        super().__init__(master, app)
        topo = ttk.Frame(self)
        topo.pack(fill="x")
        ttk.Button(topo, text="Atualizar relatório", style="Primario.TButton", command=self.carregar).pack(side="left")
        self.lbl_fat = ttk.Label(topo, text="Faturamento total: R$ 0,00", style="Total.TLabel")
        self.lbl_fat.pack(side="right")
        quadro, self.tabela = criar_tabela(self, [
            ("id", "Pedido", 70, "center"), ("data", "Data", 130, "center"), ("cliente", "Cliente", 150, "w"),
            ("itens", "Itens", 300, "w"), ("pagamento", "Pagamento", 90, "center"), ("total", "Total", 110, "e")],
            altura=16)
        quadro.pack(fill="both", expand=True, pady=(10, 0))

    def ao_exibir(self):
        self.carregar()

    @seguro
    def carregar(self):
        (vendas, faturamento, origem), ms = medir(vs.relatorio)
        self.tabela.delete(*self.tabela.get_children())
        for v in vendas:
            self.tabela.insert("", "end", values=(v["id_pedido"], v["data"], v["cliente"], v["itens"],
                                                  v["pagamento"], moeda(v["total"])))
        self.lbl_fat.config(text=f"Faturamento total: {moeda(faturamento)}")
        self.app.mostrar(f"Relatório com {len(vendas)} venda(s)", origem, ms)


# ----------------------------- aba Painel Redis -----------------------------
class AbaPainel(AbaBase):
    def __init__(self, master, app):
        super().__init__(master, app)

        topo = ttk.Frame(self)
        topo.pack(fill="x")
        self.lbl_conexao = tk.Label(topo, text="Redis: verificando...", fg="white", bg="#666666", padx=8, pady=2)
        self.lbl_conexao.pack(side="left")
        ttk.Button(topo, text="Atualizar", command=self.atualizar).pack(side="left", padx=(12, 4))
        ttk.Button(topo, text="Limpar cache (produtos e vendas)", command=self.limpar_cache).pack(side="left", padx=4)
        ttk.Button(topo, text="Testar desempenho: Supabase x Redis", style="Primario.TButton",
                   command=self.testar).pack(side="left", padx=4)

        ttk.Label(self, justify="left", style="Sub.TLabel", wraplength=960, text=(
            "Usos do Redis: (1) cache da lista de produtos e de cada produto; (2) carrinho de compras de cada "
            "cliente, com expiração automática; (3) cache do relatório de vendas.")).pack(anchor="w", pady=(8, 2))
        self.lbl_resultado = ttk.Label(self, text="", style="Total.TLabel")
        self.lbl_resultado.pack(anchor="w", pady=(2, 6))

        meio = ttk.Frame(self)
        meio.pack(fill="both", expand=True)
        meio.columnconfigure(0, weight=3)
        meio.columnconfigure(1, weight=2)
        meio.rowconfigure(0, weight=1)

        esquerda = ttk.LabelFrame(meio, text="Chaves existentes no Redis", padding=6)
        esquerda.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        quadro, self.tab_chaves = criar_tabela(esquerda, [
            ("chave", "Chave", 200, "w"), ("tipo", "Tipo", 70, "center"), ("ttl", "Expira em", 110, "center")], altura=7)
        quadro.pack(fill="both", expand=True)
        self.tab_chaves.bind("<<TreeviewSelect>>", self._selecionar)

        direita = ttk.LabelFrame(meio, text="Conteúdo da chave selecionada", padding=6)
        direita.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self.txt_valor = tk.Text(direita, height=8, width=36, wrap="none", state="disabled", font=("Consolas", 9))
        self.txt_valor.pack(fill="both", expand=True)

        log = ttk.LabelFrame(self, text="Registro de operações (origem dos dados)", padding=6)
        log.pack(fill="both", expand=True, pady=(8, 0))
        self.txt_log = tk.Text(log, height=7, wrap="word", state="disabled", font=("Consolas", 9))
        barra = ttk.Scrollbar(log, orient="vertical", command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=barra.set)
        self.txt_log.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")

    def ao_exibir(self):
        self.atualizar()

    def adicionar_log(self, linha):
        self.txt_log.config(state="normal")
        self.txt_log.insert("end", linha + "\n")
        self.txt_log.see("end")
        self.txt_log.config(state="disabled")

    def _definir_valor(self, texto):
        self.txt_valor.config(state="normal")
        self.txt_valor.delete("1.0", "end")
        self.txt_valor.insert("1.0", texto)
        self.txt_valor.config(state="disabled")

    def atualizar(self):
        try:
            conectado = rp.ping()
        except Exception as erro:
            self.lbl_conexao.config(text="Redis: sem conexão", bg=COR_REDIS)
            self.app.registrar(f"ERRO ao conectar no Redis: {erro}")
            return
        self.lbl_conexao.config(text=f"Redis: conectado (PING = {conectado})", bg=COR_SUPABASE)
        self.tab_chaves.delete(*self.tab_chaves.get_children())
        for chave, tipo, ttl in rp.chaves():
            texto_ttl = "sem expiração" if ttl == -1 else f"{ttl} s"
            self.tab_chaves.insert("", "end", iid=chave, values=(chave, tipo, texto_ttl))
        self._definir_valor("")

    def _selecionar(self, _evento=None):
        selecao = self.tab_chaves.selection()
        if selecao:
            self._definir_valor(rp.valor_formatado(selecao[0]))

    @seguro
    def limpar_cache(self):
        removidas = ps.invalidar_cache()
        self.app.registrar(f"Cache limpo manualmente: {removidas} chave(s) removida(s). Carrinhos preservados.")
        self.atualizar()

    @seguro
    def testar(self):
        ms_supabase, origem1, ms_redis, origem2 = rp.teste_desempenho()
        if ms_redis > 0:
            texto = (f"Supabase: {ms_supabase:.0f} ms  |  Redis (cache): {ms_redis:.0f} ms  |  "
                     f"o cache foi {ms_supabase / ms_redis:.1f}x mais rápido")
        else:
            texto = f"Supabase: {ms_supabase:.0f} ms  |  Redis (cache): {ms_redis:.0f} ms"
        self.lbl_resultado.config(text=texto)
        self.app.registrar(f"Teste de desempenho -> 1ª consulta: {origem1}, {ms_supabase:.0f} ms | "
                           f"2ª consulta: {origem2}, {ms_redis:.0f} ms")
        self.atualizar()


# ----------------------------- janela principal -----------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Loja de Suplementos - Supabase + Redis")
        self.geometry("1040x700")
        self.minsize(960, 620)
        self._estilo()

        cabecalho = ttk.Frame(self, padding=(12, 10))
        cabecalho.pack(fill="x")
        ttk.Label(cabecalho, text="Loja de Suplementos", style="Titulo.TLabel").pack(side="left")
        ttk.Label(cabecalho, text="Supabase (banco de dados)  +  Redis (cache e carrinho)",
                  style="Sub.TLabel").pack(side="left", padx=14)

        rodape = ttk.Frame(self, padding=(12, 6))
        rodape.pack(side="bottom", fill="x")
        self.lbl_status = ttk.Label(rodape, text="Pronto.")
        self.lbl_status.pack(side="left")
        self.lbl_origem = tk.Label(rodape, text="", fg="white", padx=4, pady=2)
        self.lbl_origem.pack(side="right")
        ttk.Label(rodape, text="Origem dos dados:").pack(side="right", padx=6)

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        self.painel = AbaPainel(self.nb, self)  # criado primeiro para receber o registro de operações
        self.abas = [
            ("Produtos", AbaProdutos(self.nb, self)),
            ("Loja / Carrinho", AbaLoja(self.nb, self)),
            ("Vendas", AbaVendas(self.nb, self)),
            ("Painel Redis", self.painel),
        ]
        for nome, aba in self.abas:
            self.nb.add(aba, text=nome)
        self.nb.bind("<<NotebookTabChanged>>", self._aba_mudou)
        self.after(150, lambda: self.abas[0][1].ao_exibir())

    def _estilo(self):
        estilo = ttk.Style(self)
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass
        estilo.configure("Titulo.TLabel", font=("Segoe UI", 17, "bold"), foreground=COR_TITULO)
        estilo.configure("Sub.TLabel", foreground="#555555")
        estilo.configure("Total.TLabel", font=("Segoe UI", 11, "bold"), foreground=COR_TITULO)
        estilo.configure("Treeview", rowheight=26)
        estilo.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        estilo.configure("Primario.TButton", background=COR_TITULO, foreground="white", padding=(10, 4))
        estilo.map("Primario.TButton", background=[("active", "#2c5282")])

    def _aba_mudou(self, _evento=None):
        indice = self.nb.index(self.nb.select())
        self.abas[indice][1].ao_exibir()

    def registrar(self, mensagem):
        self.painel.adicionar_log(f"[{datetime.now():%H:%M:%S}] {mensagem}")

    def mostrar(self, texto, origem=None, ms=None):
        sufixo = f"  ({ms:.0f} ms)" if ms is not None else ""
        self.lbl_status.config(text=texto + sufixo)
        if origem:
            self.lbl_origem.config(text=f" {origem} ", bg=cor_origem(origem))
            self.registrar(f"{texto} | origem: {origem}{sufixo}")


def iniciar():
    App().mainloop()
