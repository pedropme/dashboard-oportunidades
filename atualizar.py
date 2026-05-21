import subprocess
import tkinter as tk
from tkinter import scrolledtext
import threading
import os
import sys
from datetime import datetime

# Localiza a pasta raiz do projeto (onde o .exe está)
if getattr(sys, "frozen", False):
    PROJECT_DIR = os.path.dirname(sys.executable)
else:
    PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def log(msg, color="black"):
    output.config(state="normal")
    output.insert(tk.END, msg + "\n")
    output.tag_add(color, f"end-{len(msg)+2}c", "end-1c")
    output.tag_config("green",  foreground="#2E7D32")
    output.tag_config("red",    foreground="#C62828")
    output.tag_config("orange", foreground="#E65100")
    output.see(tk.END)
    root.update()


def run_update():
    btn.config(state="disabled", text="Atualizando...")
    output.config(state="normal")
    output.delete(1.0, tk.END)

    def execute():
        try:
            agora = datetime.now().strftime("%d/%m/%Y %H:%M")
            log(f"Iniciando atualização — {agora}\n")

            # git add dados/
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
                return

            # git commit
            msg_commit = f"Atualização de base — {agora}"
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

            # git push
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

        except FileNotFoundError:
            log("✗ Git não encontrado. Certifique-se de que o Git está instalado.", "red")
        except Exception as e:
            log(f"✗ Erro inesperado: {e}", "red")
        finally:
            btn.config(state="normal", text="Atualizar Dashboard")
            output.config(state="disabled")

    threading.Thread(target=execute, daemon=True).start()


# ─── Interface ────────────────────────────────────────────
root = tk.Tk()
root.title("Atualizar Dashboard")
root.geometry("420x300")
root.resizable(False, False)
root.configure(bg="#f5f5f5")

tk.Label(
    root,
    text="PME Máquinas — Dashboard",
    font=("Segoe UI", 13, "bold"),
    bg="#f5f5f5",
    fg="#1565C0"
).pack(pady=(18, 2))

tk.Label(
    root,
    text="Envia as bases da pasta dados/ para o GitHub\ne atualiza o dashboard automaticamente.",
    font=("Segoe UI", 9),
    bg="#f5f5f5",
    fg="#555",
    justify="center"
).pack()

btn = tk.Button(
    root,
    text="Atualizar Dashboard",
    command=run_update,
    bg="#1565C0",
    fg="white",
    font=("Segoe UI", 11, "bold"),
    relief="flat",
    padx=24,
    pady=10,
    cursor="hand2",
    activebackground="#0D47A1",
    activeforeground="white"
)
btn.pack(pady=16)

output = scrolledtext.ScrolledText(
    root,
    height=7,
    width=52,
    font=("Consolas", 9),
    bg="#1e1e1e",
    fg="#d4d4d4",
    relief="flat",
    state="disabled"
)
output.pack(padx=12, pady=(0, 12))

root.mainloop()
