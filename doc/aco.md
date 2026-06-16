# Núcleo Local do Algoritmo de Colônia de Formigas (aco)

## O que é este módulo

`aco.py` implementa o núcleo local do algoritmo ACO (Ant Colony Optimization / Otimização por Colônia de Formigas).

Esse módulo é responsável por executar o algoritmo de otimização usado para resolver o TSP (Travelling Salesman Problem / Problema do Caixeiro Viajante). Ele recebe uma matriz de distâncias entre cidades, constrói rotas com formigas artificiais, calcula o custo dessas rotas, atualiza a matriz de feromônio e mantém registrada a melhor rota encontrada até o momento.

O módulo foi feito para funcionar de forma isolada. Ele não conhece rede, sockets, eleição de líder, relógio lógico ou mensagens. A parte distribuída é feita posteriormente pelo `no.py`, que apenas chama os métodos públicos da classe `ACO`.

## Responsabilidade do módulo

O `aco.py` faz:

- recebe uma matriz de distâncias;
- cria uma matriz inicial de feromônio;
- executa uma iteração do algoritmo com N formigas;
- constrói uma rota completa para cada formiga;
- calcula a distância total de cada rota;
- identifica a melhor rota da iteração;
- atualiza a melhor rota global;
- evapora feromônio antigo;
- deposita feromônio nas rotas construídas;
- permite obter a matriz de feromônio atual;
- permite aplicar uma matriz de feromônio recebida de outro nó.

O `aco.py` não faz:

- não envia mensagens;
- não recebe mensagens;
- não escolhe líder;
- não usa relógio de Lamport;
- não cria sockets;
- não sabe qual nó está executando;
- não sabe se está rodando localmente ou distribuído.

## Dependências

Apenas biblioteca padrão do Python, sem instalação externa.

| Módulo | Uso |
|---|---|
| `random` | Sorteio da cidade inicial e escolha probabilística da próxima cidade |
| `math.inf` | Valor inicial para representar uma distância infinita antes de encontrar qualquer rota |

## Constante de configuração

| Constante | Valor | Descrição |
|---|---:|---|
| `FEROMONIO_INICIAL` | `0.1` | Valor inicial de feromônio entre cidades diferentes |

A diagonal principal da matriz de feromônio é sempre `0.0`, porque não há deslocamento de uma cidade para ela mesma.

## Classe `ACO`

### O que resolve

A classe `ACO` implementa a busca por boas rotas para o Problema do Caixeiro Viajante.

O problema consiste em encontrar uma rota que:

- comece em uma cidade;
- passe por todas as cidades uma única vez;
- retorne para a cidade inicial;
- tenha a menor distância total possível.

Como testar todas as rotas possíveis é inviável para instâncias maiores, o ACO usa uma abordagem heurística. Em vez de tentar todas as combinações, ele simula formigas artificiais construindo rotas. As rotas melhores reforçam os caminhos usados com mais feromônio. Com o passar das iterações, as próximas formigas tendem a escolher caminhos que historicamente apareceram em rotas melhores.

## Construtor

`ACO(matriz_distancias, alfa=1.0, beta=2.0, rho=0.5, q=100)`

### Parâmetros

| Parâmetro | Tipo | Valor padrão | Descrição |
|---|---|---:|---|
| `matriz_distancias` | `list[list[int ou float]]` | obrigatório | Matriz com as distâncias entre as cidades |
| `alfa` | `float` | `1.0` | Peso do feromônio na escolha da próxima cidade |
| `beta` | `float` | `2.0` | Peso da distância na escolha da próxima cidade |
| `rho` | `float` | `0.5` | Taxa de evaporação do feromônio |
| `q` | `float` | `100` | Fator de escala para depósito de feromônio |

### O que acontece no construtor

Quando um objeto `ACO` é criado, ele executa a seguinte sequência:

1. Recebe a matriz de distâncias.
2. Valida se a matriz é quadrada.
3. Valida se a matriz não está vazia.
4. Valida se os valores são numéricos.
5. Valida se não existem distâncias negativas.
6. Valida se a diagonal principal é zero.
7. Copia a matriz recebida para proteger o estado interno.
8. Calcula a quantidade de cidades.
9. Armazena os parâmetros `alfa`, `beta`, `rho` e `q`.
10. Cria a matriz inicial de feromônio.
11. Inicializa a melhor rota global como vazia.
12. Inicializa a melhor distância global como infinito.

O módulo não busca a matriz diretamente em `instancia.py`. Quem cria o objeto `ACO` é responsável por passar a matriz.

Exemplo de uso esperado:

`matriz = obter_matriz_distancias()`

`aco = ACO(matriz)`

## Parâmetros matemáticos

### `alfa`

Controla o peso do feromônio.

Quanto maior o `alfa`, mais a formiga confia nos caminhos que já foram reforçados anteriormente.

Se `alfa` for muito alto, o algoritmo tende a seguir cedo demais os caminhos que parecem bons. Isso pode acelerar a convergência, mas também pode prender o algoritmo em uma solução ruim.

No projeto, usamos `alfa = 1.0`, que dá peso normal ao feromônio.

### `beta`

Controla o peso da distância.

A distância entra no algoritmo por meio da visibilidade:

`visibilidade = 1 / distancia`

Quanto menor a distância, maior a visibilidade.

Se `beta` for alto, a formiga dá mais preferência para cidades próximas.

No projeto, usamos `beta = 2.0`, dando mais importância à distância do que ao feromônio no início da execução.

### `rho`

Controla a evaporação do feromônio.

A evaporação reduz o feromônio antigo usando a regra:

`novo_feromonio = feromonio_atual * (1 - rho)`

Com `rho = 0.5`, metade do feromônio evapora a cada atualização.

A evaporação evita que o algoritmo fique preso cedo demais em caminhos que foram reforçados por acaso nas primeiras iterações.

### `q`

Controla a quantidade de feromônio depositado por uma rota.

O depósito é calculado assim:

`deposito = q / distancia_da_rota`

Rotas menores depositam mais feromônio. Rotas maiores depositam menos.

Com `q = 100`, uma rota de distância `50` deposita `2.0`, enquanto uma rota de distância `200` deposita `0.5`.

## Estrutura interna

### `self.matriz_distancias`

Cópia da matriz de distâncias recebida no construtor.

Essa matriz representa o custo fixo entre as cidades.

Ela não muda durante a execução.

### `self.feromonio`

Matriz de feromônio usada pelo algoritmo.

Ela representa o quanto cada caminho entre duas cidades parece promissor.

Essa matriz muda ao final de cada iteração.

A posição:

`feromonio[i][j]`

representa o feromônio no caminho da cidade `i` para a cidade `j`.

### `self.melhor_rota_global`

Guarda a melhor rota encontrada desde a criação do objeto `ACO`.

### `self.melhor_distancia_global`

Guarda a distância da melhor rota global.

Antes de qualquer iteração, ela começa como infinito.

## Métodos públicos

## `executar_iteracao(num_formigas: int) -> tuple[list, float]`

Executa uma iteração completa do algoritmo.

Uma iteração é composta por várias formigas construindo rotas. Depois que todas as formigas terminam, o algoritmo atualiza o feromônio.

### Entrada

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `num_formigas` | `int` | Quantidade de formigas artificiais que serão executadas naquela iteração |

### Saída

Retorna uma tupla:

`(melhor_rota_iteracao, melhor_distancia_iteracao)`

Onde:

- `melhor_rota_iteracao` é a melhor rota encontrada somente naquela iteração;
- `melhor_distancia_iteracao` é a distância dessa rota.

### Fluxo interno

A função executa a seguinte sequência:

1. Valida se `num_formigas` é maior que zero.
2. Cria uma lista para guardar as rotas encontradas.
3. Inicializa a melhor distância da iteração como infinito.
4. Para cada formiga:
   - chama `_construir_rota()`;
   - recebe uma rota completa;
   - chama `_calcular_distancia_rota(rota)`;
   - recebe a distância total da rota;
   - salva a rota e a distância em `rotas_encontradas`;
   - verifica se essa é a melhor rota da iteração;
   - verifica se essa é a melhor rota global.
5. Depois que todas as formigas terminam:
   - chama `_atualizar_feromonio(rotas_encontradas)`.
6. Retorna a melhor rota e a melhor distância da iteração.

### Observação importante

A melhor rota da iteração pode piorar de uma iteração para outra.

Exemplo:

- iteração 1: melhor distância `86`;
- iteração 2: melhor distância `74`;
- iteração 3: melhor distância `76`.

Isso é normal. A melhor rota global continua sendo `74`, porque o algoritmo guarda o melhor resultado encontrado até agora.

## `obter_feromonio() -> list[list[float]]`

Retorna uma cópia da matriz de feromônio atual.

Essa função será usada na parte distribuída quando o líder solicitar o feromônio de cada nó.

### Por que retorna uma cópia?

Para evitar que outro módulo altere diretamente a matriz interna do ACO.

Uso esperado:

`feromonio = aco.obter_feromonio()`

Na integração distribuída, essa matriz será enviada ao líder.

## `aplicar_feromonio_externo(matriz_externa: list[list[float]]) -> None`

Aplica uma matriz de feromônio recebida de fora.

Essa função é o principal ponto de integração com a parte distribuída.

Quando o líder consolidar o feromônio dos nós, ele enviará uma matriz consolidada para cada nó. Cada nó chamará esta função para misturar o feromônio recebido com o feromônio local.

### Regra usada

Para cada posição da matriz:

`feromonio_local[i][j] = (feromonio_local[i][j] + matriz_externa[i][j]) / 2`

A diagonal principal continua `0.0`.

### Por que fazer média?

A média permite misturar o aprendizado local do nó com o aprendizado recebido da rede.

Essa abordagem é simples e estável. Ela evita que um único nó domine imediatamente todo o sistema, mas também pode diluir descobertas locais muito boas.

Como melhoria futura, o líder poderia reforçar a melhor rota global recebida entre os nós antes de redistribuir a matriz consolidada.

> **Nota sobre a integração atual:** na versão final do projeto, a sincronização e a recuperação de estado **não** usam mais `aplicar_feromonio_externo`. O líder consolida as matrizes dos nós com o método estático `consolidar_matrizes()` (média elemento a elemento) e substitui a matriz local com `definir_feromonio()`. Os workers, ao receber a matriz consolidada, também usam `definir_feromonio()`. O método `aplicar_feromonio_externo` permanece disponível como estratégia alternativa de mistura local, mas não é chamado por `no.py`.

## `definir_feromonio(matriz_nova: list[list[float]]) -> None`

Substitui completamente a matriz de feromônio interna pela matriz recebida.

Diferente de `aplicar_feromonio_externo` (que faz a **média** entre a matriz local e a externa), `definir_feromonio` **descarta** a matriz local e adota a recebida na íntegra.

### Validações

- a matriz precisa ser quadrada e não vazia (`_validar_matriz_generica`);
- precisa ter o mesmo tamanho da instância (mesmo número de cidades);
- a diagonal principal é forçada para `0.0` após a substituição.

### Onde é usado

É o ponto de integração distribuída efetivamente usado por `no.py`:

- o **líder** aplica a média consolidada em si mesmo após a sincronização ou a recuperação de estado;
- cada **worker** aplica a matriz consolidada que o líder redistribui.

Uso esperado:

`aco.definir_feromonio(matriz_consolidada)`

## `exportar_estado() -> dict`

Retorna um dicionário com o estado relevante do nó para envio pela rede.

### Saída

```python
{
    "matriz": [[...], ...],        # cópia da matriz de feromônio atual
    "melhor_rota": [...],          # melhor rota global encontrada
    "melhor_distancia": float,     # distância dessa rota
}
```

É usado por `no.py` em dois momentos:

- resposta a uma `SOLICITACAO` de feromônio durante a sincronização periódica;
- resposta a uma `RECUPERACAO` quando um novo líder reconstrói o estado após uma falha.

Empacotar matriz + melhor rota + melhor distância em um único método garante que o líder receba, de uma só vez, tanto o conhecimento de feromônio quanto a melhor solução já encontrada por aquele nó.

## `consolidar_matrizes(matrizes: list[list[list[float]]]) -> list[list[float]]` (estático)

Calcula a média elemento a elemento entre várias matrizes de feromônio.

É um **método estático** — não depende de uma instância de `ACO`. Recebe uma lista de matrizes (as recebidas dos workers mais a do próprio líder) e devolve uma única matriz consolidada.

### Regra

Para cada posição `[i][j]`:

`media[i][j] = (soma de matriz[i][j] de todas as matrizes) / quantidade_de_matrizes`

### Validações

- a lista não pode ser vazia;
- todas as matrizes devem ter o mesmo tamanho e ser quadradas.

### Onde é usado

É o coração da consolidação distribuída. Tanto a sincronização periódica quanto a recuperação de estado pós-falha chamam:

```python
matrizes = list(feromonios_recebidos.values()) + [aco.obter_feromonio()]
media = ACO.consolidar_matrizes(matrizes)
aco.definir_feromonio(media)
```

## `obter_melhor_global() -> tuple[list, float]`

Retorna a melhor rota encontrada pelo objeto `ACO` desde o início da execução.

### Saída

Retorna:

`(melhor_rota_global, melhor_distancia_global)`

Se nenhuma iteração foi executada ainda, retorna:

`([], infinito)`

Essa função pode ser usada para logs, testes, apresentação e relatório.

## Métodos internos

Os métodos internos começam com `_` e não devem ser chamados diretamente por outros módulos.

Eles existem para dividir a lógica do algoritmo em partes menores.

## `_criar_matriz_feromonio()`

Cria a matriz inicial de feromônio.

A matriz tem o mesmo tamanho da matriz de distâncias.

Para cidades diferentes, usa `FEROMONIO_INICIAL`.

Para a diagonal principal, usa `0.0`.

Exemplo conceitual com 4 cidades:

`[0.0, 0.1, 0.1, 0.1]`

`[0.1, 0.0, 0.1, 0.1]`

`[0.1, 0.1, 0.0, 0.1]`

`[0.1, 0.1, 0.1, 0.0]`

## `_construir_rota()`

Constrói uma rota completa para uma formiga.

### Fluxo

1. Sorteia uma cidade inicial.
2. Coloca essa cidade na rota.
3. Cria o conjunto de cidades ainda não visitadas.
4. Enquanto ainda houver cidade não visitada:
   - chama `_escolher_proxima_cidade(cidade_atual, cidades_nao_visitadas)`;
   - adiciona a cidade escolhida na rota;
   - remove a cidade escolhida das não visitadas;
   - atualiza a cidade atual.
5. Quando todas as cidades forem visitadas, adiciona a cidade inicial no final da rota.
6. Retorna a rota completa.

### Exemplo de rota retornada

`[0, 7, 3, 5, 2, 1, 0]`

Isso significa:

`Cidade 1 -> Cidade 8 -> Cidade 4 -> Cidade 6 -> Cidade 3 -> Cidade 2 -> Cidade 1`

## `_escolher_proxima_cidade(cidade_atual, cidades_candidatas)`

Escolhe a próxima cidade da formiga.

A escolha não é puramente gulosa. A formiga não escolhe sempre a cidade mais próxima. Ela escolhe com base em probabilidade.

A probabilidade usa dois fatores:

- feromônio do caminho;
- distância até a cidade candidata.

### Fórmula do peso

Para cada cidade candidata `j`, saindo da cidade atual `i`, o peso é:

`peso = feromonio[i][j]^alfa * (1 / distancia[i][j])^beta`

Depois o algoritmo faz um sorteio proporcional aos pesos.

### Exemplo conceitual

Se a formiga está na `Cidade 1`, e pode ir para:

- `Cidade 2`;
- `Cidade 3`;
- `Cidade 4`;

o algoritmo calcula um peso para cada opção.

Se `Cidade 4` tem maior peso, ela tem maior chance de ser escolhida, mas as outras ainda podem ser escolhidas.

Isso mantém diversidade na busca.

## `_calcular_distancia_rota(rota)`

Calcula a distância total de uma rota.

A rota já precisa estar completa.

Exemplo:

`[0, 2, 3, 1, 0]`

A função soma:

- distância de `0` para `2`;
- distância de `2` para `3`;
- distância de `3` para `1`;
- distância de `1` para `0`.

O retorno é a distância total da rota.

## `_atualizar_feromonio(rotas_encontradas)`

Atualiza a matriz de feromônio depois que todas as formigas terminaram suas rotas.

Ela chama duas funções:

1. `_evaporar_feromonio()`;
2. `_depositar_feromonio(rotas_encontradas)`.

A ordem é importante.

Primeiro o feromônio antigo evapora. Depois as rotas encontradas depositam novo feromônio.

## `_evaporar_feromonio()`

Reduz o feromônio de todos os caminhos.

A regra é:

`novo_feromonio = feromonio_atual * (1 - rho)`

Com `rho = 0.5`, todo caminho perde metade do feromônio.

A diagonal principal não é alterada.

## `_depositar_feromonio(rotas_encontradas)`

Deposita feromônio nos caminhos usados pelas formigas.

Para cada rota encontrada, calcula:

`deposito = q / distancia_da_rota`

Rotas menores geram depósitos maiores.

Depois, para cada trecho da rota, soma esse depósito na matriz de feromônio.

Exemplo:

Rota:

`Cidade 1 -> Cidade 4 -> Cidade 2 -> Cidade 1`

Recebe depósito nos caminhos:

- `Cidade 1 -> Cidade 4`;
- `Cidade 4 -> Cidade 2`;
- `Cidade 2 -> Cidade 1`.

Como a instância é simétrica, o código também reforça o caminho inverso:

- `Cidade 4 -> Cidade 1`;
- `Cidade 2 -> Cidade 4`;
- `Cidade 1 -> Cidade 2`.

## `_validar_matriz_distancias(matriz)`

Valida a matriz de distâncias recebida no construtor.

Verifica:

- se a matriz não está vazia;
- se é uma lista de listas;
- se é quadrada;
- se tem pelo menos duas cidades;
- se todos os valores são numéricos;
- se não existem valores negativos;
- se a diagonal principal é zero.

Se alguma regra for violada, lança erro.

## `_validar_matriz_generica(matriz, nome)`

Valida uma matriz genérica.

É usada tanto para a matriz de distâncias quanto para a matriz externa de feromônio.

Verifica:

- se a matriz existe;
- se é uma lista;
- se cada linha é uma lista;
- se é quadrada;
- se possui pelo menos duas cidades.

## Fluxo completo de uma iteração

Uma iteração do ACO acontece assim:

1. `executar_iteracao(num_formigas)` é chamada.
2. Para cada formiga, o algoritmo chama `_construir_rota()`.
3. `_construir_rota()` sorteia uma cidade inicial.
4. Enquanto ainda faltarem cidades, `_construir_rota()` chama `_escolher_proxima_cidade()`.
5. `_escolher_proxima_cidade()` calcula o peso de cada caminho possível e sorteia a próxima cidade.
6. Quando a rota está completa, `_construir_rota()` retorna a rota.
7. `executar_iteracao()` chama `_calcular_distancia_rota(rota)`.
8. `_calcular_distancia_rota()` soma todos os trechos da rota e retorna a distância total.
9. `executar_iteracao()` guarda a rota e compara com a melhor rota da iteração.
10. `executar_iteracao()` também compara com a melhor rota global.
11. Depois que todas as formigas terminam, `executar_iteracao()` chama `_atualizar_feromonio()`.
12. `_atualizar_feromonio()` chama `_evaporar_feromonio()`.
13. `_atualizar_feromonio()` chama `_depositar_feromonio(rotas_encontradas)`.
14. `executar_iteracao()` retorna a melhor rota e a melhor distância daquela iteração.

Resumo:

`executar_iteracao() -> _construir_rota() -> _escolher_proxima_cidade() -> _calcular_distancia_rota() -> _atualizar_feromonio() -> _evaporar_feromonio() -> _depositar_feromonio()`
