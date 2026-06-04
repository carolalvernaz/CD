# Computacao Distribuida

Projeto em Python para simular um sistema distribuido com:

- comunicacao entre nos via sockets TCP;
- relogio logico de Lamport;
- eleicao de lider pelo algoritmo Bully;
- recuperacao de estado apos falha do lider;
- ACO (Ant Colony Optimization) distribuido para o problema do caixeiro viajante.

## Requisitos

- Python 3.11 ou superior.
- Nenhuma dependencia externa precisa ser instalada; o projeto usa apenas a biblioteca padrao do Python.

## Como rodar os testes

Entre na pasta do projeto:

## Testes
Para rodar os testes individualmente:

```powershell
$env:PYTHONUTF8='1'
python src\testes\teste_lamport.py
python src\testes\teste_rede.py
python src\testes\teste_bully.py
python src\testes\teste_aco.py
python src\testes\teste_recuperacao.py
```

O teste `teste_bully.py` abre portas locais e pode levar alguns segundos, porque simula queda de nos e aguarda a eleicao de novo lider.
O teste `teste_recuperacao.py` valida o protocolo de recuperacao: o novo lider solicita a matriz de feromonio de um worker, consolida a media e substitui sua matriz local pelo estado recuperado.

## Como rodar o sistema distribuido

Abra 3 terminais PowerShell na pasta do projeto. Em cada terminal, execute um no diferente.

Terminal 1:

```powershell
cd C:\Users\joao_\Desktop\computacaodist
$env:PYTHONUTF8='1'
python src\no.py 1
```

Terminal 2:

```powershell
cd C:\Users\joao_\Desktop\computacaodist
$env:PYTHONUTF8='1'
python src\no.py 2
```

Terminal 3:

```powershell
cd C:\Users\joao_\Desktop\computacaodist
$env:PYTHONUTF8='1'
python src\no.py 3
```

Por padrao, os nos usam `localhost` nas portas:

| No | Porta |
|---:|---:|
| 1 | 5001 |
| 2 | 5002 |
| 3 | 5003 |

O no 3 inicia como lider. Se ele for encerrado, os outros nos detectam a falha por heartbeat e iniciam a eleicao Bully.
Depois que o novo lider assume, ele solicita as matrizes de feromonio dos participantes sobreviventes, aguarda respostas por ate 3 segundos, calcula a media elemento a elemento e substitui sua matriz local pelo estado recuperado antes de continuar a execucao normal.

Para parar um no, use `Ctrl+C` no terminal correspondente.

## Estrutura do projeto

```text
src/
  aco.py                 Nucleo local do algoritmo ACO
  coordenacao.py         Relogio de Lamport e eleicao Bully
  rede.py                Comunicacao TCP entre nos
  no.py                  Processo principal de cada no distribuido
  data/instancia.py      Instancia do problema e dados das cidades
  testes/                Testes e simulacoes executaveis

doc/
  aco.md
  coordenacao.md
  recuperacao.md
  rede.md
  no.md
  instancia.md
```

## Documentacao

A explicacao detalhada de cada modulo esta na pasta `doc/`.

- `doc/aco.md`: funcionamento do ACO.
- `doc/rede.md`: camada de comunicacao TCP.
- `doc/coordenacao.md`: Lamport e Bully.
- `doc/recuperacao.md`: recuperacao de estado apos falha do lider.
- `doc/no.md`: integracao do no distribuido.
- `doc/instancia.md`: dados da instancia usada.
