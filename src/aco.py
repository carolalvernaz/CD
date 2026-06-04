import random
from math import inf


FEROMONIO_INICIAL = 0.1


class ACO:
    def __init__(self, matriz_distancias, alfa=1.0, beta=2.0, rho=0.5, q=100):
        self._validar_matriz_distancias(matriz_distancias)

        self.matriz_distancias = [linha[:] for linha in matriz_distancias]
        self.quantidade_cidades = len(matriz_distancias)

        self.alfa = alfa
        self.beta = beta
        self.rho = rho
        self.q = q

        self.feromonio = self._criar_matriz_feromonio()

        self.melhor_rota_global = None
        self.melhor_distancia_global = inf

    def executar_iteracao(self, num_formigas: int) -> tuple[list, float]:
        if num_formigas <= 0:
            raise ValueError("num_formigas deve ser maior que zero.")

        rotas_encontradas = []

        melhor_rota_iteracao = None
        melhor_distancia_iteracao = inf

        for _ in range(num_formigas):
            rota = self._construir_rota()
            distancia = self._calcular_distancia_rota(rota)

            rotas_encontradas.append((rota, distancia))

            if distancia < melhor_distancia_iteracao:
                melhor_rota_iteracao = rota
                melhor_distancia_iteracao = distancia

            if distancia < self.melhor_distancia_global:
                self.melhor_rota_global = rota[:]
                self.melhor_distancia_global = distancia

        self._atualizar_feromonio(rotas_encontradas)

        return melhor_rota_iteracao, melhor_distancia_iteracao

    def obter_feromonio(self) -> list[list[float]]:
        return [linha[:] for linha in self.feromonio]

    def aplicar_feromonio_externo(self, matriz_externa: list[list[float]]) -> None:
        self._validar_matriz_generica(matriz_externa, "matriz_externa")

        for i in range(self.quantidade_cidades):
            for j in range(self.quantidade_cidades):
                if i == j:
                    self.feromonio[i][j] = 0.0
                else:
                    self.feromonio[i][j] = (
                        self.feromonio[i][j] + matriz_externa[i][j]
                    ) / 2

    def substituir_feromonio(self, matriz_nova: list[list[float]]) -> None:
        self._validar_matriz_generica(matriz_nova, "matriz_nova")

        if len(matriz_nova) != self.quantidade_cidades:
            raise ValueError("matriz_nova deve ter o mesmo tamanho da instancia.")

        nova_matriz = []

        for i in range(self.quantidade_cidades):
            linha = []

            for j in range(self.quantidade_cidades):
                valor = matriz_nova[i][j]

                if not isinstance(valor, (int, float)):
                    raise TypeError("matriz_nova deve conter apenas numeros.")

                if valor < 0:
                    raise ValueError("matriz_nova nao pode conter valores negativos.")

                if i == j:
                    linha.append(0.0)
                else:
                    linha.append(float(valor))

            nova_matriz.append(linha)

        self.feromonio = nova_matriz

    def obter_melhor_global(self) -> tuple[list, float]:
        if self.melhor_rota_global is None:
            return [], inf

        return self.melhor_rota_global[:], self.melhor_distancia_global

    def _criar_matriz_feromonio(self):
        matriz = []

        for i in range(self.quantidade_cidades):
            linha = []

            for j in range(self.quantidade_cidades):
                if i == j:
                    linha.append(0.0)
                else:
                    linha.append(FEROMONIO_INICIAL)

            matriz.append(linha)

        return matriz

    def _construir_rota(self):
        cidade_inicial = random.randrange(self.quantidade_cidades)

        rota = [cidade_inicial]
        cidades_nao_visitadas = set(range(self.quantidade_cidades))
        cidades_nao_visitadas.remove(cidade_inicial)

        cidade_atual = cidade_inicial

        while cidades_nao_visitadas:
            proxima_cidade = self._escolher_proxima_cidade(
                cidade_atual,
                cidades_nao_visitadas
            )

            rota.append(proxima_cidade)
            cidades_nao_visitadas.remove(proxima_cidade)
            cidade_atual = proxima_cidade

        rota.append(cidade_inicial)

        return rota

    def _escolher_proxima_cidade(self, cidade_atual, cidades_candidatas):
        pesos = []

        for cidade in cidades_candidatas:
            distancia = self.matriz_distancias[cidade_atual][cidade]

            if distancia <= 0:
                peso = 0
            else:
                nivel_feromonio = self.feromonio[cidade_atual][cidade]
                visibilidade = 1 / distancia

                peso = (nivel_feromonio ** self.alfa) * (visibilidade ** self.beta)

            pesos.append((cidade, peso))

        soma_pesos = sum(peso for _, peso in pesos)

        if soma_pesos == 0:
            return random.choice(list(cidades_candidatas))

        sorteio = random.uniform(0, soma_pesos)
        acumulado = 0

        for cidade, peso in pesos:
            acumulado += peso

            if acumulado >= sorteio:
                return cidade

        return pesos[-1][0]

    def _calcular_distancia_rota(self, rota):
        distancia_total = 0

        for i in range(len(rota) - 1):
            origem = rota[i]
            destino = rota[i + 1]

            distancia_total += self.matriz_distancias[origem][destino]

        return distancia_total

    def _atualizar_feromonio(self, rotas_encontradas):
        self._evaporar_feromonio()
        self._depositar_feromonio(rotas_encontradas)

    def _evaporar_feromonio(self):
        fator_evaporacao = 1 - self.rho

        for i in range(self.quantidade_cidades):
            for j in range(self.quantidade_cidades):
                if i != j:
                    self.feromonio[i][j] *= fator_evaporacao

    def _depositar_feromonio(self, rotas_encontradas):
        for rota, distancia in rotas_encontradas:
            if distancia <= 0:
                continue

            deposito = self.q / distancia

            for i in range(len(rota) - 1):
                origem = rota[i]
                destino = rota[i + 1]

                self.feromonio[origem][destino] += deposito
                self.feromonio[destino][origem] += deposito

    def _validar_matriz_distancias(self, matriz):
        self._validar_matriz_generica(matriz, "matriz_distancias")

        for i in range(len(matriz)):
            for j in range(len(matriz)):
                valor = matriz[i][j]

                if not isinstance(valor, (int, float)):
                    raise TypeError("A matriz de distâncias deve conter apenas números.")

                if valor < 0:
                    raise ValueError("A matriz de distâncias não pode conter valores negativos.")

                if i == j and valor != 0:
                    raise ValueError("A diagonal principal da matriz de distâncias deve ser zero.")

    def _validar_matriz_generica(self, matriz, nome):
        if not matriz:
            raise ValueError(f"{nome} não pode ser vazia.")

        if not isinstance(matriz, list):
            raise TypeError(f"{nome} deve ser uma lista de listas.")

        quantidade_linhas = len(matriz)

        for linha in matriz:
            if not isinstance(linha, list):
                raise TypeError(f"{nome} deve ser uma lista de listas.")

            if len(linha) != quantidade_linhas:
                raise ValueError(f"{nome} deve ser uma matriz quadrada.")

        if quantidade_linhas < 2:
            raise ValueError(f"{nome} deve possuir pelo menos duas cidades.")

    def exportar_estado(self) -> dict:
        rota, distancia = self.obter_melhor_global()

        return {
            "matriz": self.obter_feromonio(),
            "melhor_rota": rota,
            "melhor_distancia": distancia,
        }

    @staticmethod
    def consolidar_matrizes(matrizes: list[list[list[float]]]) -> list[list[float]]:
        if not matrizes:
            raise ValueError("A lista de matrizes não pode ser vazia.")

        tamanho = len(matrizes[0])

        for matriz in matrizes:
            if len(matriz) != tamanho:
                raise ValueError("Todas as matrizes devem ter o mesmo tamanho.")

            for linha in matriz:
                if len(linha) != tamanho:
                    raise ValueError("Todas as matrizes devem ser quadradas e ter o mesmo tamanho.")

        return [
            [
                sum(matriz[i][j] for matriz in matrizes) / len(matrizes)
                for j in range(tamanho)
            ]
            for i in range(tamanho)
        ]
