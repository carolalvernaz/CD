# Recuperacao de Estado Apos Falha do Lider

## O que e este mecanismo

A recuperacao de estado apos falha do lider e o protocolo usado para evitar que o sistema distribuido perca o conhecimento acumulado nas matrizes de feromonio quando o lider atual cai.

Antes desta etapa, os nos ja conseguiam detectar a queda do lider e iniciar uma nova eleicao pelo algoritmo Bully. O problema era que o novo lider continuava a execucao usando apenas sua propria matriz local de feromonio. Isso podia descartar parte importante do aprendizado distribuido feito pelos outros nos antes da falha.

Com a recuperacao implementada, quando um novo lider assume oficialmente, ele solicita as matrizes de feromonio dos participantes sobreviventes, consolida essas matrizes com a sua propria matriz local e substitui seu estado interno pela matriz recuperada.

## Arquivos envolvidos

| Arquivo | Papel |
|---|---|
| `src/no.py` | Implementa o protocolo distribuido de recuperacao |
| `src/aco.py` | Permite substituir completamente a matriz de feromonio |
| `src/rede.py` | Transporta as mensagens TCP/JSON usadas pelo protocolo |
| `src/coordenacao.py` | Mantem Lamport, Bully e estado de lideranca |
| `src/testes/teste_recuperacao.py` | Valida o fluxo de solicitacao, resposta, media e substituicao |

## Objetivo

O objetivo do protocolo e garantir que, apos a falha do lider:

- os nos sobreviventes continuem executando sem reinicializacao;
- a eleicao Bully escolha um novo lider;
- o novo lider recupere o conhecimento mantido pelos demais nos;
- a matriz recuperada substitua a matriz local do novo lider;
- o ciclo normal de ACO e sincronizacao periodica continue depois disso.

## Mensagens usadas

O protocolo adiciona dois tipos de mensagem ao sistema.

| Tipo | Quem envia | Quem recebe | Conteudo |
|---|---|---|---|
| `RECUPERACAO_SOLICITACAO` | Novo lider | Workers sobreviventes | `{}` |
| `RECUPERACAO_ESTADO` | Worker | Novo lider | Estado exportado pelo ACO |

O conteudo de `RECUPERACAO_ESTADO` segue o formato retornado por `aco.exportar_estado()`:

```python
{
    "matriz": [[...], ...],
    "melhor_rota": [...],
    "melhor_distancia": 73
}
```

Nesta fase, a recuperacao usa a chave `"matriz"` para reconstruir o feromonio global. As informacoes de melhor rota e melhor distancia continuam sendo enviadas porque ja fazem parte do estado exportado pelo ACO e podem ser aproveitadas em melhorias futuras.

## Constante de configuracao

| Constante | Valor | Descricao |
|---|---:|---|
| `TIMEOUT_RECUPERACAO` | `3` | Janela maxima, em segundos, para aguardar respostas dos workers |

Se algum worker nao responder dentro da janela de 3 segundos, ele e removido da lista de participantes ativos do lider.

## Fluxo completo

1. O lider atual deixa de responder.
2. Os workers detectam a falha pelo tempo sem contato com o lider.
3. A eleicao Bully e iniciada.
4. O no vencedor assume a lideranca.
5. O novo lider envia `RECUPERACAO_SOLICITACAO` para os participantes conhecidos.
6. Cada worker que reconhece esse lider responde com `RECUPERACAO_ESTADO`.
7. O lider aguarda respostas por ate `TIMEOUT_RECUPERACAO`.
8. O lider calcula a media elemento por elemento entre:
   - sua propria matriz local;
   - todas as matrizes recebidas dos workers.
9. O lider chama `aco.substituir_feromonio(matriz_recuperada)`.
10. A execucao normal continua.

## Regra de consolidacao

A consolidacao usa a media aritmetica elemento por elemento:

```text
matriz_recuperada[i][j] =
    soma(matriz_k[i][j] para cada matriz k) / quantidade_de_matrizes
```

Exemplo com duas matrizes:

```text
lider[0][1]  = 0.40
worker[0][1] = 0.80

recuperada[0][1] = (0.40 + 0.80) / 2
recuperada[0][1] = 0.60
```

A diagonal principal permanece `0.0`, porque nao existe caminho de uma cidade para ela mesma.

## Por que substituir a matriz em vez de aplicar media incremental

O metodo antigo `aplicar_feromonio_externo()` mistura a matriz recebida com a matriz local:

```text
feromonio_local = (feromonio_local + matriz_externa) / 2
```

Isso e adequado para sincronizacao periodica, porque o no mistura o aprendizado externo com o seu estado local.

Na recuperacao, o comportamento esperado e diferente: o novo lider deve reconstruir o estado global e passar a usar exatamente a matriz consolidada. Por isso foi criado o metodo:

```python
substituir_feromonio(matriz_nova)
```

Esse metodo valida a matriz recebida, copia seus valores e troca completamente `self.feromonio`.

## Tratamento de eleicoes concorrentes

Durante uma falha, mais de um no pode iniciar eleicao quase ao mesmo tempo. Isso e esperado em sistemas distribuidos.

Exemplo:

```text
[RECUP] Lider 1 iniciando recuperacao de estado com 1 participante(s).
[ELEI] Novo lider: No 2
```

Nesse caso, o no 1 iniciou a recuperacao, mas depois reconheceu que o no 2 e o lider correto pelo Bully, pois possui ID maior.

Para evitar substituicao indevida, o codigo verifica se o no ainda e lider antes de concluir a recuperacao:

```text
[RECUP] Recuperacao cancelada: no deixou de ser lider.
```

Assim, somente o lider valido deve aplicar a matriz recuperada.

## Logs esperados

Quando a recuperacao acontece corretamente, o terminal do novo lider deve mostrar:

```text
[ELEI] No 2 assumiu como lider. Participantes: [1, 2]
[RECUP] Lider 2 iniciando recuperacao de estado com 1 participante(s).
[RECUP] Estado recuperado com 1 resposta(s). Matriz local do lider substituida.
```

Essas mensagens indicam que:

- o no 2 assumiu a lideranca;
- havia 1 participante sobrevivente para consultar;
- o lider recebeu 1 matriz;
- a matriz consolidada substituiu a matriz local do lider.

## Como testar automaticamente

Na pasta do projeto, execute:

```powershell
$env:PYTHONUTF8='1'
python src\testes\teste_recuperacao.py
```

O teste valida:

- envio de `RECUPERACAO_SOLICITACAO`;
- resposta com `RECUPERACAO_ESTADO`;
- consolidacao pela media;
- substituicao completa da matriz do lider.

Saida esperada:

```text
=== TESTE RECUPERACAO DE ESTADO ===

Recuperacao validada: solicitacao, resposta, media e substituicao OK.
```

## Como testar manualmente

Abra tres terminais PowerShell na pasta do projeto.

Terminal 1:

```powershell
$env:PYTHONUTF8='1'
python src\no.py 1
```

Terminal 2:

```powershell
$env:PYTHONUTF8='1'
python src\no.py 2
```

Terminal 3:

```powershell
$env:PYTHONUTF8='1'
python src\no.py 3
```

Depois que os nos estiverem executando, encerre o terminal do lider atual, normalmente o no de maior ID ativo.

Nos logs do novo lider, procure:

```text
[RECUP] Lider X iniciando recuperacao de estado...
[RECUP] Estado recuperado com ... resposta(s). Matriz local do lider substituida.
```

Se essas mensagens aparecerem, a fase de recuperacao foi executada corretamente.

## Relacao com a sincronizacao normal

A recuperacao nao substitui a sincronizacao periodica de feromonio.

Existem dois fluxos diferentes:

| Fluxo | Quando acontece | Mensagens |
|---|---|---|
| Sincronizacao normal | A cada `INTERVALO_SYNC` iteracoes | `SOLICITACAO` e `FEROMONIO` |
| Recuperacao pos-falha | Logo apos um novo lider assumir | `RECUPERACAO_SOLICITACAO` e `RECUPERACAO_ESTADO` |

A separacao das mensagens evita confundir respostas de sincronizacao normal com respostas de recuperacao.

## Resultado esperado

Ao final da fase 1, o sistema deve ser capaz de:

- sobreviver a queda do lider;
- eleger automaticamente um novo lider;
- recuperar a matriz de feromonio usando os nos sobreviventes;
- evitar perda critica de conhecimento acumulado;
- continuar a execucao sem reinicializar o sistema.
