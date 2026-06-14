# Computacao Distribuida

Projeto em Python que simula um sistema distribuido com:

- comunicacao entre nos via sockets TCP;
- relogio logico de Lamport para ordenacao causal de eventos;
- eleicao de lider pelo algoritmo Bully (maior ID vence);
- ACO (Ant Colony Optimization) distribuido para o problema do caixeiro viajante (TSP, 16 cidades).

## Requisitos

- Python 3.11 ou superior.
- Para gerar os graficos de analise: `pip install matplotlib`
- As demais dependencias usam apenas a biblioteca padrao do Python.

## Estrutura do projeto

```text
src/
  aco.py                  Nucleo local do algoritmo ACO
  aco_centralizado.py     Versao centralizada do ACO (baseline)
  coordenacao.py          Relogio de Lamport e eleicao Bully
  rede.py                 Comunicacao TCP entre nos
  no.py                   Processo principal de cada no distribuido
  data/instancia.py       Instancia do problema e dados das 16 cidades
  testes/
    teste_lamport.py      Testes unitarios do relogio de Lamport
    teste_rede.py         Testes de comunicacao TCP
    teste_bully.py        Testes do algoritmo de eleicao
    teste_aco.py          Testes do nucleo ACO
    executar_experimentos.py   Executa 20 runs centralizado + 20 distribuido
    executar_tolerancia.py     Testes de tolerancia a falhas (3 cenarios x 5 reps)
    gerar_graficos.py          Gera os 3 graficos a partir dos CSVs

doc/
  aco.md
  coordenacao.md
  rede.md
  no.md
  instancia.md

resultados.csv              Tempos e distancias das 40 execucoes de benchmark
resultados_tolerancia.csv   Tempos de recuperacao dos 15 testes de tolerancia
doc/grafico_tempo_execucao.png
doc/grafico_qualidade_solucoes.png
doc/grafico_tolerancia.png
```

## Como rodar os testes unitarios

```powershell
$env:PYTHONUTF8='1'
python src\testes\teste_lamport.py
python src\testes\teste_rede.py
python src\testes\teste_bully.py
python src\testes\teste_aco.py
```

O teste `teste_bully.py` simula queda de nos e pode levar alguns segundos.

## Como rodar o sistema distribuido (modo normal)

O sistema usa 5 nos. Abra 5 terminais na pasta do projeto e execute um no por terminal.
**Recomendado: iniciar em ordem decrescente (5 primeiro)**, pois o no de maior ID vence a eleicao Bully e os nos menores encontram o lider mais facilmente.

Terminal 1 (iniciar primeiro):
```powershell
$env:PYTHONUTF8='1'
python src\no.py 5
```

Terminal 2:
```powershell
$env:PYTHONUTF8='1'
python src\no.py 4
```

...e assim por diante ate o no 1.

Portas usadas (localhost):

| No | Porta |
|---:|------:|
| 1  | 5001  |
| 2  | 5002  |
| 3  | 5003  |
| 4  | 5004  |
| 5  | 5005  |

O no 5 assume como lider apos a eleicao inicial. Se ele for encerrado, os nos restantes detectam a falha (timeout de 8s) e elegem o proximo lider pelo Bully.

Para encerrar um no, use `Ctrl+C` no terminal correspondente.

## Modo benchmark

Para parar apos 100 iteracoes (usado nos experimentos comparativos):

```powershell
$env:PYTHONUTF8='1'
python src\no.py 1 --benchmark
```

## Experimentos comparativos (Fase 3)

### 1. Rodar os 40 experimentos (20 centralizado + 20 distribuido)

```powershell
$env:PYTHONUTF8='1'
python src\testes\executar_experimentos.py
```

Gera `resultados.csv` com tempo de execucao e melhor distancia de cada run.

### 2. Rodar os testes de tolerancia a falhas

```powershell
$env:PYTHONUTF8='1'
python src\testes\executar_tolerancia.py
```

Executa 3 cenarios de falha do lider (inicio, meio e fim da execucao), 5 repeticoes cada.
Gera `resultados_tolerancia.csv` com o tempo de recuperacao de cada run.

> **Nota:** os nos iniciam em ordem 5->4->3->2->1 com 2s de intervalo para garantir
> que todos se registrem com o lider antes dos testes. O script aguarda ate detectar
> sincronizacao estavel (lider com 4 workers) antes de injetar a falha.

### 3. Gerar os graficos

```powershell
$env:PYTHONUTF8='1'
python src\testes\gerar_graficos.py
```

Gera 3 graficos em `doc/`:
- `grafico_tempo_execucao.png`: comparacao de tempo centralizado vs distribuido
- `grafico_qualidade_solucoes.png`: comparacao da melhor distancia encontrada
- `grafico_tolerancia.png`: tempo de recuperacao por cenario de falha

## Versao centralizada (baseline)

```powershell
$env:PYTHONUTF8='1'
python src\aco_centralizado.py --iteracoes 100 --formigas 5
```

## Documentacao

A explicacao detalhada de cada modulo esta na pasta `doc/`.

- `doc/aco.md`: funcionamento do ACO local.
- `doc/rede.md`: camada de comunicacao TCP.
- `doc/coordenacao.md`: Lamport e Bully.
- `doc/no.md`: integracao do no distribuido.
- `doc/instancia.md`: dados da instancia usada.
