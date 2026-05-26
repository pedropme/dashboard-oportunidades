import subprocess
import tkinter as tk
from tkinter import scrolledtext, ttk
import threading
import os
import sys
import shutil
from datetime import datetime

# Localiza a pasta raiz do projeto (onde o .exe está)
if getattr(sys, "frozen", False):
    PROJECT_DIR = os.path.dirname(sys.executable)
else:
    PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

VENDAS_SCRIPT = os.path.join(PROJECT_DIR, "scripts", "baixar_vendas.py")


def _python_exe():
    """Retorna o caminho do interpretador Python para subprocessos."""
    if getattr(sys, "frozen", False):
        # Modo exe: usa o Python do sistema
        py = shutil.which("python") or shutil.which("python3")
        return py or "python"
    return sys.executable


def log(msg, color="default"):
    output.config(state="normal")
    output.insert(tk.END, msg + "\n")
    if color != "default":
        start = f"end-{len(msg)+2}c"
        output.tag_add(color, start, "end-1c")
    output.tag_config("green",  foreground="#4CAF50")
    output.tag_config("red",    foreground="#EF5350")
    output.tag_config("orange", foreground="#FFA726")
    output.tag_config("gray",   foreground="#9E9E9E")
    output.see(tk.END)
    root.update()


def run_update():
    btn.config(state="disabled", text="Atualizando...")
    progress.start(12)
    output.config(state="normal")
    output.delete(1.0, tk.END)

    def execute():
        ok_geral = True
        try:
            agora = datetime.now().strftime("%d/%m/%Y %H:%M")
            log(f"Iniciando atualização — {agora}\n", "gray")

            # ── 1. Download de vendas.xlsx ─────────────────────────────────
            vendas_ok = False
            if os.path.exists(VENDAS_SCRIPT):
                log("Baixando base de vendas do portal Analysis BI...")
                py = _python_exe()
                r = subprocess.run(
                    [py, VENDAS_SCRIPT, "--no-git"],
                    cwd=PROJECT_DIR,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=300,          # 5 min máx
                )
                # Mostra as linhas relevantes do log (evita ruído)
                for linha in r.stdout.splitlines():
                    if linha.strip():
                        if "ERRO" in linha or "TIMEOUT" in linha:
                            log(f"  {linha}", "red")
                        elif "Concluido" in linha or "salvo" in linha or "recebido" in linha:
                            log(f"  {linha}", "green")
                        else:
                            log(f"  {linha}", "gray")
                if r.returncode == 0:
                    log("✓ Vendas baixadas com sucesso", "green")
                    vendas_ok = True
                else:
                    log("✗ Falha ao baixar vendas — continuando com arquivos existentes", "orange")
                    if r.stderr:
                        log(f"  {r.stderr[:400]}", "red")
                    ok_geral = False
            else:
                log("  (script de vendas não encontrado — pulando)", "gray")

            # ── 2. git add dados/ ──────────────────────────────────────────
            log("\nPreparando arquivos para envio...")
            r = subprocess.run(
                ["git", "add", "dados/"],
                cwd=PROJECT_DIR,
                capture_output=True,
                text=True
            )
            if r.returncode == 0:
                log("✓ Arquivos da pasta dados/ preparados", "green")
            else:
                log(f"✗ Erro ao preparar arquivos:\n{r.stderr}", "red")
                ok_geral = False

            # ── 3. git commit ──────────────────────────────────────────────
            sufixo = " (+ vendas)" if vendas_ok else ""
            msg_commit = f"Atualização de base{sufixo} — {agora}"
            r = subprocess.run(
                ["git", "commit", "-m", msg_commit],
                cwd=PROJECT_DIR,
                capture_output=True,
                text=True
            )
            if r.returncode == 0:
                log("✓ Commit realizado", "green")
            else:
                log("  Sem alterações novas para commitar", "orange")

            # ── 4. git push ────────────────────────────────────────────────
            log("  Enviando ao GitHub...")
            r = subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=PROJECT_DIR,
                capture_output=True,
                text=True
            )
            if r.returncode == 0:
                log("✓ Enviado com sucesso!", "green")
                log("\nO dashboard será atualizado em instantes.", "green")
            else:
                log(f"✗ Erro ao enviar ao GitHub:\n{r.stderr}", "red")
                ok_geral = False

        except subprocess.TimeoutExpired:
            log("✗ Timeout: o download de vendas demorou mais de 5 minutos.", "red")
            ok_geral = False
        except FileNotFoundError:
            log("✗ Git não encontrado. Certifique-se de que o Git está instalado.", "red")
            ok_geral = False
        except Exception as e:
            log(f"✗ Erro inesperado: {e}", "red")
            ok_geral = False
        finally:
            progress.stop()
            btn.config(
                state="normal",
                text="Atualizar Dashboard" if ok_geral else "Atualizar Dashboard (com erros)"
            )
            output.config(state="disabled")

    threading.Thread(target=execute, daemon=True).start()


# ─── Interface ────────────────────────────────────────────
root = tk.Tk()
root.title("Atualizar Dashboard")
root.geometry("480x380")
root.resizable(False, False)
root.configure(bg="#1e1e2e")

# Título
tk.Label(
    root,
    text="PME Máquinas — Dashboard",
    font=("Segoe UI", 13, "bold"),
    bg="#1e1e2e",
    fg="#89b4fa"
).pack(pady=(18, 2))

tk.Label(
    root,
    text="Baixa a base de vendas do portal Analysis BI\ne envia todos os arquivos para o GitHub.",
    font=("Segoe UI", 9),
    bg="#1e1e2e",
    fg="#a6adc8",
    justify="center"
).pack()

btn = tk.Button(
    root,
    text="Atualizar Dashboard",
    command=run_update,
    bg="#89b4fa",
    fg="#1e1e2e",
    font=("Segoe UI", 11, "bold"),
    relief="flat",
    padx=24,
    pady=10,
    cursor="hand2",
    activebackground="#b4befe",
    activeforeground="#1e1e2e"
)
btn.pack(pady=16)

# Barra de progresso (indeterminate)
style = ttk.Style()
style.theme_use("clam")
style.configure("blue.Horizontal.TProgressbar",
                troughcolor="#313244", background="#89b4fa",
                thickness=4)
progress = ttk.Progressbar(
    root, orient="horizontal", mode="indeterminate",
    style="blue.Horizontal.TProgressbar", length=420
)
progress.pack(pady=(0, 8))

output = scrolledtext.ScrolledText(
    root,
    height=10,
    width=60,
    font=("Consolas", 9),
    bg="#11111b",
    fg="#cdd6f4",
    relief="flat",
    state="disabled"
)
output.pack(padx=14, pady=(0, 14))

root.mainloop()
