"""
Gera os tres graficos definitivos a partir dos CSVs de experimentos.
Requer: pip install matplotlib

Uso (da raiz do projeto):
    python src/testes/gerar_graficos.py
"""

import csv
import math
import statistics
import sys
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

RAIZ = Path(__file__).parent.parent.parent
CSV_RESULTADOS = RAIZ / "resultados.csv"
CSV_TOLERANCIA = RAIZ / "resultados_tolerancia.csv"
DOC_DIR = RAIZ / "doc"

AZUL = "#4C72B0"
LARANJA = "#DD8452"
VERDE = "#55A868"


def _ler_csv(caminho):
    if not caminho.exists():
        return []
    with open(caminho, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _separar(linhas, campo):
    cent = [float(l[campo]) for l in linhas if l["versao"] == "centralizado" and l.get(campo)]
    dist = [float(l[campo]) for l in linhas if l["versao"] == "distribuido" and l.get(campo)]
    return cent, dist


def _ci95(valores):
    n = len(valores)
    if n < 2:
        return 0.0
    t_tabela = {
        1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
        6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
        11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
        16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
        25: 2.060, 30: 2.042,
    }
    t = t_tabela.get(n - 1, 1.960)
    return t * statistics.stdev(valores) / math.sqrt(n)


def _estilo_boxplot(ax, dados, rotulos, cores, ylabel, titulo):
    bp = ax.boxplot(dados, patch_artist=True, widths=0.5)
    for patch, cor in zip(bp["boxes"], cores):
        patch.set_facecolor(cor)
        patch.set_alpha(0.75)
    for elemento in ["whiskers", "caps", "medians", "fliers"]:
        for item in bp[elemento]:
            item.set_color("#333333")
    ax.set_xticklabels(rotulos, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_title(titulo, fontsize=12, pad=10)
    ax.grid(axis="y", alpha=0.3, linestyle="--")


def grafico_1_tempo(linhas, destino):
    cent, dist = _separar(linhas, "tempo_total")
    if not cent and not dist:
        print("  Grafico 1: sem dados suficientes.")
        return

    dados, rotulos, cores = [], [], []
    if cent:
        dados.append(cent)
        rotulos.append(f"Centralizado\n(n={len(cent)})")
        cores.append(AZUL)
    if dist:
        dados.append(dist)
        rotulos.append(f"Distribuido\n(n={len(dist)})")
        cores.append(LARANJA)

    fig, ax = plt.subplots(figsize=(8, 5))
    _estilo_boxplot(ax, dados, rotulos, cores,
                    "Tempo total (s)",
                    "Comparacao de Tempo de Execucao — 100 iteracoes")

    if cent and dist:
        speedup = statistics.mean(cent) / statistics.mean(dist)
        ax.text(0.97, 0.97, f"Speedup medio: {speedup:.2f}x",
                transform=ax.transAxes, ha="right", va="top", fontsize=10,
                bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.6))

    plt.tight_layout()
    plt.savefig(destino, dpi=150)
    plt.close()
    print(f"  Grafico 1 salvo: {destino.name}")


def grafico_2_qualidade(linhas, destino):
    cent, dist = _separar(linhas, "melhor_distancia")
    if not cent and not dist:
        print("  Grafico 2: sem dados suficientes.")
        return

    dados, rotulos, cores = [], [], []
    if cent:
        dados.append(cent)
        rotulos.append(f"Centralizado\n(n={len(cent)})")
        cores.append(AZUL)
    if dist:
        dados.append(dist)
        rotulos.append(f"Distribuido\n(n={len(dist)})")
        cores.append(LARANJA)

    fig, ax = plt.subplots(figsize=(8, 5))
    _estilo_boxplot(ax, dados, rotulos, cores,
                    "Melhor distancia encontrada",
                    "Comparacao da Qualidade das Solucoes — 100 iteracoes")

    plt.tight_layout()
    plt.savefig(destino, dpi=150)
    plt.close()
    print(f"  Grafico 2 salvo: {destino.name}")


def grafico_3_tolerancia(linhas_tol, destino):
    cenarios_dados = {}
    for l in linhas_tol:
        t = l.get("tempo_recuperacao")
        if t and t not in ("None", ""):
            cenarios_dados.setdefault(l["cenario"], []).append(float(t))

    ordem = ["inicio", "meio", "fim"]
    rotulos_display = {
        "inicio": "Inicio\n(falha precoce)",
        "meio":   "Meio\n(falha intermediaria)",
        "fim":    "Fim\n(falha tardia)",
    }

    dados = [cenarios_dados[n] for n in ordem if cenarios_dados.get(n)]
    rotulos = [rotulos_display[n] for n in ordem if cenarios_dados.get(n)]

    if not dados:
        print("  Grafico 3: sem dados de tolerancia.")
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    _estilo_boxplot(ax, dados, rotulos, [VERDE] * len(dados),
                    "Tempo de recuperacao (s)",
                    "Comportamento durante Recuperacao de Falha do Lider")

    ax.axhline(y=8, color="red", linestyle="--", alpha=0.6,
               label="Timeout deteccao = 8s")
    ax.legend(fontsize=9, loc="upper right")

    plt.tight_layout()
    plt.savefig(destino, dpi=150)
    plt.close()
    print(f"  Grafico 3 salvo: {destino.name}")


def _resumo(linhas, linhas_tol):
    print("\n========== RESUMO ESTATISTICO ==========")

    for versao in ["centralizado", "distribuido"]:
        valores = [float(l["tempo_total"]) for l in linhas
                   if l["versao"] == versao and l.get("tempo_total")]
        if not valores:
            continue
        ci = _ci95(valores)
        print(f"\n{versao.capitalize()} — Tempo (s)  [n={len(valores)}]")
        print(f"  Media:          {statistics.mean(valores):.3f}")
        print(f"  Desvio padrao:  {statistics.stdev(valores):.3f}")
        print(f"  IC 95%:         {statistics.mean(valores):.3f} +/- {ci:.3f}")
        print(f"  Min / Max:      {min(valores):.3f} / {max(valores):.3f}")

    cent, dist = _separar(linhas, "tempo_total")
    if cent and dist:
        speedup = statistics.mean(cent) / statistics.mean(dist)
        eficiencia = speedup / 5
        print(f"\nSpeedup medio (S = T_c / T_d):   {speedup:.3f}")
        print(f"Eficiencia (E = S / 5 nos):      {eficiencia:.3f}")

    cenarios_dados = {}
    for l in linhas_tol:
        t = l.get("tempo_recuperacao")
        if t and t not in ("None", ""):
            cenarios_dados.setdefault(l["cenario"], []).append(float(t))

    if cenarios_dados:
        print("\nTolerancia a falhas — Tempo de recuperacao (s):")
        for nome in ["inicio", "meio", "fim"]:
            tempos = cenarios_dados.get(nome, [])
            if tempos:
                ci = _ci95(tempos)
                print(f"  {nome:8s}  media={statistics.mean(tempos):.2f}  "
                      f"desvio={statistics.stdev(tempos):.2f}  IC95={ci:.2f}  n={len(tempos)}")

    print("=========================================\n")


def main():
    if not HAS_MATPLOTLIB:
        print("Instale matplotlib: pip install matplotlib")
        sys.exit(1)

    DOC_DIR.mkdir(exist_ok=True)

    linhas = _ler_csv(CSV_RESULTADOS)
    linhas_tol = _ler_csv(CSV_TOLERANCIA)

    if not linhas:
        print(f"Aviso: {CSV_RESULTADOS.name} nao encontrado. Execute executar_experimentos.py primeiro.")
    if not linhas_tol:
        print(f"Aviso: {CSV_TOLERANCIA.name} nao encontrado. Execute executar_tolerancia.py primeiro.")

    print("Gerando graficos...\n")
    grafico_1_tempo(linhas, DOC_DIR / "grafico_tempo_execucao.png")
    grafico_2_qualidade(linhas, DOC_DIR / "grafico_qualidade_solucoes.png")
    grafico_3_tolerancia(linhas_tol, DOC_DIR / "grafico_tolerancia.png")

    if linhas or linhas_tol:
        _resumo(linhas, linhas_tol)

    print(f"Graficos salvos em: {DOC_DIR}")


if __name__ == "__main__":
    main()
