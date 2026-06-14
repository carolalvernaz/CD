"""
Executa 20 experimentos centralizados e 20 distribuidos (modo --benchmark).
Salva os resultados em resultados.csv na raiz do projeto.

Uso (da raiz do projeto):
    python src/testes/executar_experimentos.py
"""

import csv
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aco_centralizado import executar_baseline_centralizado

NUM_EXECUCOES = 20
ITERACOES = 100
NUM_FORMIGAS = 5
TIMEOUT_NO = 40       # tempo maximo por run distribuido (todos os nos em paralelo)
PAUSA_ENTRE_RUNS = 4  # aguarda portas liberarem antes do proximo run

RAIZ = Path(__file__).parent.parent.parent
SRC_DIR = Path(__file__).parent.parent
CSV_RESULTADOS = RAIZ / "resultados.csv"

CAMPOS = [
    "versao", "execucao", "iteracoes",
    "num_formigas", "tempo_total", "melhor_distancia",
]


def _salvar(linha):
    novo = not CSV_RESULTADOS.exists()
    with open(CSV_RESULTADOS, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS, extrasaction="ignore")
        if novo:
            w.writeheader()
        w.writerow(linha)


def _rodar_centralizado(execucao):
    print(f"  [{execucao:02d}/{NUM_EXECUCOES}]", end="  ", flush=True)
    r = executar_baseline_centralizado(
        iteracoes=ITERACOES, num_formigas=NUM_FORMIGAS, seed=execucao
    )
    print(f"tempo={r['tempo_total']:.3f}s   dist={r['melhor_distancia']:.2f}")
    return {
        "versao": "centralizado",
        "execucao": execucao,
        "iteracoes": ITERACOES,
        "num_formigas": NUM_FORMIGAS,
        "tempo_total": r["tempo_total"],
        "melhor_distancia": r["melhor_distancia"],
    }


def _iniciar_nos():
    processos = []
    for nid in range(1, 6):
        p = subprocess.Popen(
            [sys.executable, "-u", "no.py", str(nid), "--benchmark"],
            cwd=str(SRC_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        processos.append((nid, p))
        time.sleep(0.4)
    return processos


def _parsear_saida(saida):
    m_t = re.search(r"Tempo total de execucao: ([\d.]+)s", saida)
    m_d = re.search(r"Melhor distancia global: ([\d.]+)", saida)
    if m_t and m_d:
        return float(m_t.group(1)), float(m_d.group(1))
    return None, None


def _coletar_em_paralelo(processos):
    """Espera todos os processos terminarem em paralelo. Mata quem nao terminar no prazo."""
    saidas = {}
    lock = threading.Lock()

    def collect(nid, p):
        try:
            stdout, _ = p.communicate(timeout=TIMEOUT_NO)
        except subprocess.TimeoutExpired:
            p.kill()
            stdout, _ = p.communicate()
        with lock:
            saidas[nid] = stdout

    threads = [threading.Thread(target=collect, args=(nid, p), daemon=True)
               for nid, p in processos]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=TIMEOUT_NO + 5)

    # Garante que nenhum processo orphao sobreviveu
    for _, p in processos:
        if p.poll() is None:
            p.kill()

    return saidas


def _rodar_distribuido(execucao):
    print(f"  [{execucao:02d}/{NUM_EXECUCOES}]", end="  ", flush=True)
    processos = _iniciar_nos()
    saidas = _coletar_em_paralelo(processos)

    tempo, dist = None, None
    for saida in saidas.values():
        t, d = _parsear_saida(saida)
        if t is not None:
            tempo, dist = t, d
            break

    if tempo is None:
        print("FALHOU (nenhum no concluiu o benchmark no prazo)")
        time.sleep(PAUSA_ENTRE_RUNS)
        return None

    print(f"tempo={tempo:.3f}s   dist={dist:.2f}")
    time.sleep(PAUSA_ENTRE_RUNS)

    return {
        "versao": "distribuido",
        "execucao": execucao,
        "iteracoes": ITERACOES,
        "num_formigas": NUM_FORMIGAS,
        "tempo_total": tempo,
        "melhor_distancia": dist,
    }


def main():
    if CSV_RESULTADOS.exists():
        CSV_RESULTADOS.unlink()

    print(f"Salvando em: {CSV_RESULTADOS}\n")

    print("=== VERSAO CENTRALIZADA (20 execucoes) ===")
    for i in range(1, NUM_EXECUCOES + 1):
        _salvar(_rodar_centralizado(i))

    print("\n=== VERSAO DISTRIBUIDA (20 execucoes, 5 nos por run) ===")
    print("(cada execucao inicia 5 processos em modo --benchmark)\n")
    for i in range(1, NUM_EXECUCOES + 1):
        r = _rodar_distribuido(i)
        if r:
            _salvar(r)

    print(f"\nConcluido. Resultados em: {CSV_RESULTADOS}")


if __name__ == "__main__":
    main()
