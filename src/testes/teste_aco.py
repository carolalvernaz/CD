import sys
import os
from math import inf

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aco import ACO
from data.instancia import (
    obter_matriz_distancias,
    obter_nomes_cidades,
    formatar_rota,
)


def log(msg):
    print(msg, flush=True)


def obter_valores_fora_diagonal(matriz):
    valores = []

    for i in range(len(matriz)):
        for j in range(len(matriz)):
            if i != j:
                valores.append(matriz[i][j])

    return valores


def calcular_resumo_feromonio(matriz):
    valores = obter_valores_fora_diagonal(matriz)

    return {
        "min": min(valores),
        "max": max(valores),
        "media": sum(valores) / len(valores),
        "soma": sum(valores),
    }


def formatar_resumo_feromonio(rotulo, resumo):
    return (
        f"{rotulo:<7} | "
        f"min={resumo['min']:.4f} "
        f"max={resumo['max']:.4f} "
        f"media={resumo['media']:.4f} "
        f"soma={resumo['soma']:.4f}"
    )


def obter_top_caminhos_reforcados(feromonio_antes, feromonio_depois, nomes, limite=5):
    diferencas = []

    tamanho = len(feromonio_antes)

    for i in range(tamanho):
        for j in range(i + 1, tamanho):
            diferenca = feromonio_depois[i][j] - feromonio_antes[i][j]

            diferencas.append({
                "origem": nomes[i],
                "destino": nomes[j],
                "antes": feromonio_antes[i][j],
                "depois": feromonio_depois[i][j],
                "diferenca": diferenca,
            })

    diferencas.sort(key=lambda item: item["diferenca"], reverse=True)

    return diferencas[:limite]


def imprimir_top_caminhos_reforcados(caminhos):
    log("Top caminhos reforçados:")

    for posicao, caminho in enumerate(caminhos, start=1):
        log(
            f"{posicao}. "
            f"{caminho['origem']} -> {caminho['destino']} | "
            f"antes={caminho['antes']:.4f} "
            f"depois={caminho['depois']:.4f} "
            f"delta={caminho['diferenca']:+.4f}"
        )


def criar_matriz_feromonio_externa(tamanho, valor=0.5):
    matriz = []

    for i in range(tamanho):
        linha = []

        for j in range(tamanho):
            if i == j:
                linha.append(0.0)
            else:
                linha.append(valor)

        matriz.append(linha)

    return matriz


def testar_execucao_aco():
    log("\n=== TESTE ACO ===\n")

    matriz_distancias = obter_matriz_distancias()
    nomes_cidades = obter_nomes_cidades()

    aco = ACO(matriz_distancias)

    log(f"Quantidade de cidades: {len(matriz_distancias)}")
    log("Executando 50 iterações com 10 formigas por iteração...\n")

    for iteracao in range(1, 51):
        feromonio_antes = aco.obter_feromonio()

        melhor_rota, melhor_distancia = aco.executar_iteracao(num_formigas=10)

        melhor_rota_global, melhor_distancia_global = aco.obter_melhor_global()

        feromonio_depois = aco.obter_feromonio()

        resumo_antes = calcular_resumo_feromonio(feromonio_antes)
        resumo_depois = calcular_resumo_feromonio(feromonio_depois)

        caminhos_reforcados = obter_top_caminhos_reforcados(
            feromonio_antes,
            feromonio_depois,
            nomes_cidades,
            limite=5,
        )

        log(f"Iteração {iteracao}")
        log(f"Melhor distância da iteração: {melhor_distancia}")
        log(f"Melhor distância global até agora: {melhor_distancia_global}")
        log(f"Melhor rota da iteração: {formatar_rota(melhor_rota)}")
        log(f"Melhor rota global até agora: {formatar_rota(melhor_rota_global)}")
        log("")
        log("Resumo do feromônio:")
        log(formatar_resumo_feromonio("Antes", resumo_antes))
        log(formatar_resumo_feromonio("Depois", resumo_depois))
        log("")
        imprimir_top_caminhos_reforcados(caminhos_reforcados)
        log("-" * 100)

    melhor_rota_global, melhor_distancia_global = aco.obter_melhor_global()

    log("\n=== RESULTADO FINAL ===\n")
    log(f"Melhor distância global: {melhor_distancia_global}")
    log(f"Melhor rota global: {formatar_rota(melhor_rota_global)}")

    assert melhor_rota_global != [], "A melhor rota global não deveria estar vazia."
    assert melhor_distancia_global != inf, "A melhor distância global não deveria ser infinita."
    assert len(melhor_rota_global) == len(matriz_distancias) + 1, (
        "A rota deve passar por todas as cidades e voltar para a cidade inicial."
    )
    assert melhor_rota_global[0] == melhor_rota_global[-1], (
        "A rota deve terminar na mesma cidade em que começou."
    )

    log("\nTeste de execução do ACO concluído com sucesso.")


def testar_obter_feromonio():
    log("\n=== TESTE OBTER FEROMÔNIO ===\n")

    matriz_distancias = obter_matriz_distancias()
    aco = ACO(matriz_distancias)

    feromonio = aco.obter_feromonio()

    assert len(feromonio) == len(matriz_distancias), (
        "A matriz de feromônio deve ter a mesma quantidade de linhas da matriz de distâncias."
    )

    assert len(feromonio[0]) == len(matriz_distancias), (
        "A matriz de feromônio deve ser quadrada."
    )

    assert feromonio[0][0] == 0.0, (
        "A diagonal principal da matriz de feromônio deve ser zero."
    )

    assert feromonio[0][1] > 0.0, (
        "Os caminhos entre cidades diferentes devem começar com feromônio positivo."
    )

    log("Teste de obtenção da matriz de feromônio concluído com sucesso.")


def testar_aplicar_feromonio_externo():
    log("\n=== TESTE APLICAR FEROMÔNIO EXTERNO ===\n")

    matriz_distancias = obter_matriz_distancias()
    aco = ACO(matriz_distancias)

    tamanho = len(matriz_distancias)

    feromonio_antes = aco.obter_feromonio()
    matriz_externa = criar_matriz_feromonio_externa(tamanho, valor=0.5)

    valor_local_antes = feromonio_antes[0][1]
    valor_externo = matriz_externa[0][1]

    aco.aplicar_feromonio_externo(matriz_externa)

    feromonio_depois = aco.obter_feromonio()

    valor_esperado = (valor_local_antes + valor_externo) / 2

    assert feromonio_depois[0][1] == valor_esperado, (
        "O feromônio local deveria ser a média entre o valor local e o externo."
    )

    assert feromonio_depois[1][0] == valor_esperado, (
        "A matriz de feromônio deve permanecer simétrica neste teste."
    )

    assert feromonio_depois[0][0] == 0.0, (
        "A diagonal principal deve continuar zero após aplicar feromônio externo."
    )

    log(f"Valor local antes: {valor_local_antes}")
    log(f"Valor externo: {valor_externo}")
    log(f"Valor esperado depois da média: {valor_esperado}")
    log(f"Valor obtido: {feromonio_depois[0][1]}")

    log("\nTeste de aplicação de feromônio externo concluído com sucesso.")


def testar_substituir_feromonio():
    log("\n=== TESTE SUBSTITUIR FEROMONIO ===\n")

    matriz_distancias = obter_matriz_distancias()
    aco = ACO(matriz_distancias)

    tamanho = len(matriz_distancias)
    matriz_nova = criar_matriz_feromonio_externa(tamanho, valor=0.75)

    aco.substituir_feromonio(matriz_nova)
    feromonio_depois = aco.obter_feromonio()

    assert feromonio_depois[0][1] == 0.75, (
        "O feromonio deve ser substituido diretamente pelo novo valor."
    )

    assert feromonio_depois[0][0] == 0.0, (
        "A diagonal principal deve continuar zero apos substituir feromonio."
    )

    matriz_nova[0][1] = 9.99

    assert feromonio_depois[0][1] == 0.75, (
        "A matriz interna nao deve compartilhar referencia com a matriz recebida."
    )

    log("Teste de substituicao completa do feromonio concluido com sucesso.")


def main():
    testar_execucao_aco()
    testar_obter_feromonio()
    testar_aplicar_feromonio_externo()
    testar_substituir_feromonio()

    log("\nTESTE ACO FINALIZADO COM SUCESSO\n")


if __name__ == "__main__":
    main()
