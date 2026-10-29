"""Ponto de entrada: abre a interface gráfica da Loja de Suplementos (Supabase + Redis)."""

import sys


def _mostrar_erro(titulo, mensagem):
    print(f"\n[ERRO] {titulo}\n{mensagem}\n", file=sys.stderr)
    try:
        import tkinter as tk
        from tkinter import messagebox

        raiz = tk.Tk()
        raiz.withdraw()
        messagebox.showerror(titulo, mensagem)
        raiz.destroy()
    except Exception:
        pass


def main():
    try:
        import gui  # importa os serviços, que carregam o .env e criam as conexões
    except Exception as erro:
        _mostrar_erro("Não foi possível iniciar a aplicação", f"{erro}")
        return 1
    gui.iniciar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
