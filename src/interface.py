"""
Interface grafica — ACO Distribuido
Uso: python src/interface.py
"""
import csv
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import scrolledtext, ttk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

BASE = Path(__file__).parent.parent


def ler_csv(p):
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def media(vals):
    return sum(vals) / len(vals) if vals else 0


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ACO Distribuido")
        self.geometry("1000x700")

        self.processos = {}
        self.log_queues = {}

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=5, pady=5)

        tab1 = ttk.Frame(nb)
        tab2 = ttk.Frame(nb)
        nb.add(tab1, text="Resultados")
        nb.add(tab2, text="Sistema ao Vivo")

        self._aba_resultados(tab1)
        self._aba_live(tab2)
        self._poll_logs()

    # ── Aba Resultados ─────────────────────────────────────────────────────────

    def _aba_resultados(self, parent):
        dados = ler_csv(BASE / "resultados.csv")
        tol   = ler_csv(BASE / "resultados_tolerancia.csv")

        C = [d for d in dados if d["versao"] == "centralizado"]
        D = [d for d in dados if d["versao"] == "distribuido"]

        tempo_c = [float(d["tempo_total"])      for d in C]
        tempo_d = [float(d["tempo_total"])      for d in D]
        dist_c  = [float(d["melhor_distancia"]) for d in C]
        dist_d  = [float(d["melhor_distancia"]) for d in D]

        # Resumo em texto simples
        info = tk.Frame(parent)
        info.pack(fill="x", padx=10, pady=8)

        resumo = (
            f"Execucoes: {len(C)} centralizado, {len(D)} distribuido     |     "
            f"Tempo medio: {media(tempo_c)*1000:.1f} ms (centr.)  x  {media(tempo_d):.2f} s (distr.)     |     "
            f"Distancia media: {media(dist_c):.1f} (centr.)  x  {media(dist_d):.1f} (distr.)"
        )
        tk.Label(info, text=resumo, font=("Arial", 9)).pack(anchor="w")

        # Graficos
        fig = Figure(figsize=(10, 6), dpi=90)
        fig.subplots_adjust(hspace=0.45, wspace=0.35)

        # Tempo
        ax1 = fig.add_subplot(2, 2, 1)
        ax1.bar(["Centralizado", "Distribuido"], [media(tempo_c), media(tempo_d)])
        ax1.set_title("Tempo de execucao medio (s)")
        ax1.set_ylabel("Segundos")

        # Distancia
        ax2 = fig.add_subplot(2, 2, 2)
        ax2.bar(["Centralizado", "Distribuido"], [media(dist_c), media(dist_d)])
        ax2.set_title("Distancia media encontrada")
        ax2.set_ylabel("Distancia")
        ax2.set_ylim(65, max(max(dist_c), max(dist_d)) + 3)

        # Tolerancia
        ax3 = fig.add_subplot(2, 1, 2)
        cenarios = ["inicio", "meio", "fim"]
        medias_tol = [
            media([float(d["tempo_recuperacao"]) for d in tol if d["cenario"] == c])
            for c in cenarios
        ]
        ax3.bar(["Inicio", "Meio", "Fim"], medias_tol)
        ax3.set_title("Tempo medio de recuperacao apos falha do lider (s)")
        ax3.set_ylabel("Segundos")

        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=5)

    # ── Aba ao Vivo ────────────────────────────────────────────────────────────

    def _aba_live(self, parent):
        # Botoes
        btn_frame = tk.Frame(parent)
        btn_frame.pack(fill="x", padx=10, pady=8)

        tk.Button(btn_frame, text="Iniciar todos (5 a 1)",
                  command=self._iniciar_todos).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Parar todos",
                  command=self._parar_todos).pack(side="left", padx=4)
        tk.Label(btn_frame,
                 text="Inicie em ordem decrescente — no 5 assume como lider.",
                 font=("Arial", 8), fg="gray").pack(side="left", padx=8)

        # Status dos nos
        status_frame = tk.LabelFrame(parent, text="Nos", padx=8, pady=6)
        status_frame.pack(fill="x", padx=10, pady=4)

        self.status_labels = {}
        for nid in [1, 2, 3, 4, 5]:
            col = tk.Frame(status_frame)
            col.pack(side="left", expand=True)
            tk.Label(col, text=f"No {nid}", font=("Arial", 9, "bold")).pack()
            lbl = tk.Label(col, text="parado", fg="gray", font=("Arial", 8))
            lbl.pack()
            self.status_labels[nid] = lbl
            tk.Button(col, text="Iniciar", width=7,
                      command=lambda n=nid: self._iniciar_no(n)).pack(pady=2)
            tk.Button(col, text="Parar", width=7,
                      command=lambda n=nid: self._parar_no(n)).pack()

        # Logs
        log_nb = ttk.Notebook(parent)
        log_nb.pack(fill="both", expand=True, padx=10, pady=(4, 8))

        self.log_texts = {}
        for nid in [1, 2, 3, 4, 5]:
            frame = ttk.Frame(log_nb)
            log_nb.add(frame, text=f"No {nid}")
            txt = scrolledtext.ScrolledText(
                frame, wrap="word", state="disabled",
                font=("Consolas", 9), bg="#f9f9f9",
            )
            txt.pack(fill="both", expand=True)
            self.log_texts[nid] = txt

    # ── Controle de processos ──────────────────────────────────────────────────

    def _iniciar_no(self, nid):
        proc = self.processos.get(nid)
        if proc and proc.poll() is None:
            return

        txt = self.log_texts[nid]
        txt.configure(state="normal")
        txt.delete("1.0", "end")
        txt.configure(state="disabled")

        q = queue.Queue(maxsize=500)
        self.log_queues[nid] = q

        env = {**os.environ, "PYTHONUTF8": "1"}
        proc = subprocess.Popen(
            [sys.executable, str(BASE / "src" / "no.py"), str(nid)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            env=env, cwd=str(BASE),
        )
        self.processos[nid] = proc
        self.status_labels[nid].config(text="rodando", fg="green")

        def _ler():
            for linha in proc.stdout:
                linha = linha.rstrip()
                if not linha:
                    continue
                if q.full():
                    try: q.get_nowait()
                    except queue.Empty: pass
                try: q.put_nowait(linha)
                except queue.Full: pass
            q.put_nowait("__FIM__")

        threading.Thread(target=_ler, daemon=True).start()

    def _parar_no(self, nid):
        proc = self.processos.pop(nid, None)
        if proc and proc.poll() is None:
            proc.terminate()
        self.status_labels[nid].config(text="parado", fg="gray")

    def _iniciar_todos(self):
        def _seq():
            import time
            for nid in [5, 4, 3, 2, 1]:
                self.after(0, self._iniciar_no, nid)
                time.sleep(2.2)
        threading.Thread(target=_seq, daemon=True).start()

    def _parar_todos(self):
        for nid in list(self.processos.keys()):
            self._parar_no(nid)

    # ── Poll de logs ───────────────────────────────────────────────────────────

    def _poll_logs(self):
        for nid, q in self.log_queues.items():
            try:
                while True:
                    linha = q.get_nowait()
                    txt = self.log_texts[nid]
                    txt.configure(state="normal")
                    if linha == "__FIM__":
                        txt.insert("end", "--- processo encerrado ---\n")
                        self.status_labels[nid].config(text="encerrado", fg="red")
                    else:
                        txt.insert("end", linha + "\n")
                    txt.see("end")
                    txt.configure(state="disabled")
            except queue.Empty:
                pass
        self.after(100, self._poll_logs)


if __name__ == "__main__":
    app = App()
    app.mainloop()
