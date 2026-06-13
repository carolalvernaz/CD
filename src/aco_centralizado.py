from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path
from time import perf_counter

from aco import ACO
from data.instancia import DISTANCIAS, formatar_rota


ITERACOES_PADRAO = 100
FORMIGAS_PADRAO = 5


def calcular_speedup(tempo_referencia: float, tempo_otimizado: float) -> float:
    if tempo_otimizado <= 0:
        return float("inf")

    return tempo_referencia / tempo_otimizado


def calcular_eficiencia(speedup: float, quantidade_processos: int) -> float:
    if quantidade_processos <= 0:
        return 0.0

    return speedup / quantidade_processos


def executar_baseline_centralizado(
    iteracoes: int = ITERACOES_PADRAO,
    num_formigas: int = FORMIGAS_PADRAO,
    seed: int | None = None,
) -> dict:
    if iteracoes <= 0:
        raise ValueError("iteracoes deve ser maior que zero.")

    if num_formigas <= 0:
        raise ValueError("num_formigas deve ser maior que zero.")

    if seed is not None:
        random.seed(seed)

    aco = ACO(DISTANCIAS)
    inicio = perf_counter()

    for _ in range(iteracoes):
        aco.executar_iteracao(num_formigas=num_formigas)

    tempo_total = perf_counter() - inicio
    melhor_rota, melhor_distancia = aco.obter_melhor_global()

    return {
        "modo": "centralizado",
        "iteracoes": iteracoes,
        "num_formigas": num_formigas,
        "tempo_total": tempo_total,
        "melhor_rota": melhor_rota,
        "melhor_distancia": melhor_distancia,
        "taxa_iteracoes_por_segundo": iteracoes / tempo_total if tempo_total > 0 else float("inf"),
    }


def salvar_resultado_csv(caminho: Path, resultado: dict, extras: dict | None = None) -> None:
    campos = [
        "modo",
        "iteracoes",
        "num_formigas",
        "tempo_total",
        "melhor_distancia",
        "melhor_rota",
        "taxa_iteracoes_por_segundo",
        "speedup",
        "eficiencia",
        "tempo_referencia",
        "tempo_comparado",
        "quantidade_processos",
    ]

    linha = {campo: "" for campo in campos}
    resultado_csv = dict(resultado)
    resultado_csv["melhor_rota"] = formatar_rota(resultado["melhor_rota"])
    linha.update(resultado_csv)

    if extras:
        linha.update(extras)

    novo_arquivo = not caminho.exists()
    caminho.parent.mkdir(parents=True, exist_ok=True)

    with caminho.open("a", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos)

        if novo_arquivo:
            escritor.writeheader()

        escritor.writerow(linha)


def criar_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Executa o baseline centralizado do ACO com telemetria."
    )
    parser.add_argument("--iteracoes", type=int, default=ITERACOES_PADRAO)
    parser.add_argument("--formigas", type=int, default=FORMIGAS_PADRAO)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--tempo-distribuido",
        type=float,
        default=None,
        help="Tempo total medido na versao distribuida para calcular speedup.",
    )
    parser.add_argument(
        "--nos-distribuidos",
        type=int,
        default=5,
        help="Quantidade de processos/nos usados no calculo de eficiencia.",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Caminho opcional para salvar uma linha com as metricas.",
    )
    return parser.parse_args()


def imprimir_resultado(resultado: dict, tempo_distribuido: float | None, quantidade_nos: int) -> None:
    print("\n========== BASELINE CENTRALIZADO ==========")
    print(f"Iteracoes: {resultado['iteracoes']}")
    print(f"Formigas por iteracao: {resultado['num_formigas']}")
    print(f"Tempo total: {resultado['tempo_total']:.2f}s")
    print(f"Iteracoes por segundo: {resultado['taxa_iteracoes_por_segundo']:.2f}")
    print(f"Melhor distancia global: {resultado['melhor_distancia']:.2f}")
    print(f"Melhor rota global: {formatar_rota(resultado['melhor_rota'])}")

    if tempo_distribuido is not None:
        speedup = calcular_speedup(tempo_distribuido, resultado["tempo_total"])
        eficiencia = calcular_eficiencia(speedup, quantidade_nos)
        print(f"Tempo distribuido de referencia: {tempo_distribuido:.2f}s")
        print(f"Speedup: {speedup:.2f}")
        print(f"Eficiencia: {eficiencia:.2f}")
    else:
        print("Speedup e eficiencia ficam disponiveis quando o tempo distribuido for informado.")

    print("===========================================\n")


def main() -> None:
    args = criar_argumentos()
    resultado = executar_baseline_centralizado(
        iteracoes=args.iteracoes,
        num_formigas=args.formigas,
        seed=args.seed,
    )

    tempo_distribuido = args.tempo_distribuido
    quantidade_nos = args.nos_distribuidos

    extras = {
        "speedup": "",
        "eficiencia": "",
        "tempo_referencia": "",
        "tempo_comparado": "",
        "quantidade_processos": quantidade_nos,
    }

    if tempo_distribuido is not None:
        speedup = calcular_speedup(tempo_distribuido, resultado["tempo_total"])
        eficiencia = calcular_eficiencia(speedup, quantidade_nos)
        extras.update(
            {
                "speedup": speedup,
                "eficiencia": eficiencia,
                "tempo_referencia": tempo_distribuido,
                "tempo_comparado": resultado["tempo_total"],
            }
        )

    imprimir_resultado(resultado, tempo_distribuido, quantidade_nos)

    if args.csv is not None:
        salvar_resultado_csv(args.csv, resultado, extras)
        print(f"[CSV] Resultados salvos em {args.csv}")


if __name__ == "__main__":
    main()
