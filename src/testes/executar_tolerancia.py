"""
Testes de tolerancia a falhas: encerra o lider em momentos distintos
e mede o tempo de recuperacao do sistema.

Salva resultados em resultados_tolerancia.csv na raiz do projeto.

Uso (da raiz do projeto):
    python src/testes/executar_tolerancia.py
"""

import csv
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent.parent
SRC_DIR = Path(__file__).parent.parent
CSV_TOLERANCIA = RAIZ / "resultados_tolerancia.csv"

LIDER_ID = 5
TIMEOUT_ESTABILIZACAO = 90  # maximo para aguardar sync com 4 workers
TIMEOUT_RECUPERACAO = 60    # maximo para detectar nova eleicao + sync
PAUSA_ENTRE_RUNS = 15       # aguarda liberacao de portas entre runs
STAGGER = 2.0               # segundos entre inicio de cada no

CENARIOS = [
    ("inicio", 5),
    ("meio",   20),
    ("fim",    45),
]
REPETICOES = 5

CAMPOS = [
    "cenario", "execucao", "lider_morto", "momento_falha",
    "tempo_recuperacao", "eleicao_correta", "busca_continuou",
]


def _salvar(linha):
    novo = not CSV_TOLERANCIA.exists()
    with open(CSV_TOLERANCIA, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS, extrasaction="ignore")
        if novo:
            w.writeheader()
        w.writerow(linha)


def _executar_cenario(nome, momento_falha, execucao):
    processos = {}
    saidas = {nid: [] for nid in range(1, 6)}
    lock = threading.Lock()

    def ler_saida(nid, p):
        try:
            while True:
                linha = p.stdout.readline()
                if not linha:
                    break
                with lock:
                    saidas[nid].append(linha)
        except (ValueError, OSError):
            pass

    def output_de(nid):
        with lock:
            return "".join(saidas[nid])

    def linhas_de(nid):
        with lock:
            return list(saidas[nid])

    # Inicia nos em ordem INVERSA: 5 primeiro, depois 4,3,2,1.
    # Assim os nos menores encontram o 5 ja no ar e aceitam-no como lider.
    for nid in [5, 4, 3, 2, 1]:
        p = subprocess.Popen(
            [sys.executable, "-u", "no.py", str(nid)],
            cwd=str(SRC_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            text=True,
        )
        processos[nid] = p
        t = threading.Thread(target=ler_saida, args=(nid, p), daemon=True)
        t.start()
        time.sleep(STAGGER)

    # Aguarda ate o lider sincronizar com todos os 4 workers.
    # "[SYNC] Feromonio sincronizado com 4 worker(s)" confirma que o sistema
    # esta genuinamente estavel (todos os nos activos como workers do lider 5).
    ESTAB = r"Feromonio sincronizado com 4 worker"
    prazo = time.time() + TIMEOUT_ESTABILIZACAO
    estabilizado = False
    while time.time() < prazo:
        if re.search(ESTAB, output_de(LIDER_ID)):
            estabilizado = True
            break
        time.sleep(0.5)

    if not estabilizado:
        print(f"  AVISO: sistema nao estabilizou em {TIMEOUT_ESTABILIZACAO}s")
        for nid in range(1, 6):
            linhas = [l.rstrip() for l in output_de(nid).split("\n") if l.strip()]
            total = len(linhas)
            primeiras = " | ".join(linhas[:3]) if linhas else "(sem saida)"
            ultima = linhas[-1] if linhas else "(sem saida)"
            print(f"    no={nid} ({total} linhas)  inicio: {primeiras[:100]}")
            print(f"         ultima: {ultima[:120]}")

    # Aguarda momento de falha apos estabilizacao
    time.sleep(momento_falha)

    # Snapshot do numero de linhas por no ANTES do kill para filtragem posterior
    with lock:
        snapshot = {nid: len(saidas[nid]) for nid in range(1, 6) if nid != LIDER_ID}

    t_kill = time.time()
    try:
        processos[LIDER_ID].kill()
    except Exception:
        pass

    # Deteccao de recuperacao:
    #  - eleicao_correta : algum no sobrevivente imprimiu "assumiu como lider"
    #  - t_recuperado    : primeiro "[SYNC] Feromonio sincronizado com N worker(s)"
    #                      (N >= 1) aparece em qualquer no sobrevivente
    #                      APOS o kill (usando snapshot de linhas)
    t_recuperado = None
    eleicao_correta = False
    busca_continuou = False
    prazo = t_kill + TIMEOUT_RECUPERACAO

    PAD_SYNC = r"Feromonio sincronizado com (\d+) worker"
    PAD_ELEI = r"assumiu como lider"

    while time.time() < prazo:
        for nid in range(1, 6):
            if nid == LIDER_ID:
                continue
            with lock:
                novas_linhas = "".join(saidas[nid][snapshot[nid]:])

            if re.search(PAD_ELEI, novas_linhas):
                eleicao_correta = True

            m = re.search(PAD_SYNC, novas_linhas)
            if m and int(m.group(1)) >= 1:
                t_recuperado = time.time()
                eleicao_correta = True
                busca_continuou = True
                break

        if t_recuperado:
            break
        time.sleep(0.3)

    # Encerra todos os processos
    for nid, p in processos.items():
        try:
            p.kill()
            p.wait(timeout=5)
        except Exception:
            pass

    time.sleep(PAUSA_ENTRE_RUNS)

    return {
        "cenario": nome,
        "execucao": execucao,
        "lider_morto": LIDER_ID,
        "momento_falha": momento_falha,
        "tempo_recuperacao": round(t_recuperado - t_kill, 2) if t_recuperado else None,
        "eleicao_correta": eleicao_correta,
        "busca_continuou": busca_continuou,
    }


def main():
    if CSV_TOLERANCIA.exists():
        CSV_TOLERANCIA.unlink()

    print(f"Salvando em: {CSV_TOLERANCIA}\n")
    print("Os nos iniciam em ordem inversa (5->4->3->2->1).")
    print("Estabilizacao: aguarda '[SYNC] com 4 worker(s)' no lider.")
    print("Recuperacao:   aguarda primeiro SYNC do novo lider apos o kill.\n")

    for nome, momento in CENARIOS:
        print(f"=== Cenario '{nome}': falha {momento}s apos estabilizacao ({REPETICOES} repeticoes) ===")
        for rep in range(1, REPETICOES + 1):
            print(f"  [{rep}/{REPETICOES}]", end="  ", flush=True)
            r = _executar_cenario(nome, momento, rep)
            t = r["tempo_recuperacao"]
            if t is not None:
                print(f"recuperacao em {t:.2f}s  eleicao_ok={r['eleicao_correta']}")
            else:
                print(f"recuperacao NAO detectada ({TIMEOUT_RECUPERACAO}s)  eleicao={r['eleicao_correta']}")
            _salvar(r)
        print()

    print(f"Concluido. Resultados em: {CSV_TOLERANCIA}")


if __name__ == "__main__":
    main()
