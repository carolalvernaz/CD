# Programa Principal do Nó Distribuído (no.py)

## O que é este arquivo

`no.py` é o programa principal de cada nó do sistema distribuído de ACO. Ele é o integrador: importa todos os módulos (`rede.py`, `aco.py`, `coordenacao.py`, `data/instancia.py`) e os conecta em um único loop de execução contínua.

Cada nó é um processo Python independente:

```bash
python no.py 5   # Nó 5 — porta 5005
python no.py 4   # Nó 4 — porta 5004
...
python no.py 1   # Nó 1 — porta 5001
```

Opcionalmente, `--benchmark` faz o nó parar após 100 iterações (usado nos experimentos comparativos):

```bash
python no.py 1 --benchmark
```

---

## Visão geral do design

A versão final do sistema tem três características que vale destacar logo de início, porque mudaram em relação a versões anteriores do projeto:

1. **Cinco nós.** O dicionário `NOS` define 5 nós (IDs 1 a 5, portas 5001–5005).
2. **Loop único, sem thread de heartbeat dedicada.** Todo o trabalho do nó (processar mensagens, detectar falha do líder, executar ACO, sincronizar) acontece no **loop principal**. A única thread paralela é o servidor TCP interno de `rede.py`. Não há mais `loop_heartbeat` nem `_eleicao_inicial`.
3. **Detecção de falha passiva (sem mensagem de HEARTBEAT).** A vivacidade do líder é inferida do tráfego normal: sempre que chega uma mensagem do líder atual (tipicamente as `SOLICITACAO`/`FEROMONIO` das sincronizações periódicas), o nó atualiza o relógio `ultimo_contato_lider`. Se passar tempo demais sem nenhum contato, o líder é considerado morto.
4. **Grupo dinâmico.** Os participantes ativos são rastreados por `MembrosGrupo`. Nós entram por um protocolo de JOIN/REGISTER e são removidos quando não respondem.

---

## Dependências

| Módulo | Origem | Uso |
|---|---|---|
| `rede.py` | interno | Comunicação TCP entre nós |
| `aco.py` | interno | Algoritmo de otimização local |
| `coordenacao.py` | interno | Relógio de Lamport, eleição Bully e `MembrosGrupo` |
| `data/instancia.py` | interno | Matriz de distâncias do TSP e formatação de rota |
| `sys` | padrão Python | Leitura dos argumentos de linha de comando |
| `time` | padrão Python | Timeouts, medição de duração e pausas |

---

## Configuração

```python
NOS = {
    1: ("localhost", 5001),
    2: ("localhost", 5002),
    3: ("localhost", 5003),
    4: ("localhost", 5004),
    5: ("localhost", 5005),
}
```

Para rodar em máquinas diferentes, basta substituir `"localhost"` pelos IPs reais.

### Constantes principais

| Constante | Valor | Descrição |
|---|---:|---|
| `TIMEOUT_LIDER_MORTO` | `8` | Segundos sem contato do líder antes de iniciar nova eleição |
| `INTERVALO_SYNC` | `100` | A cada quantas iterações o líder sincroniza o feromônio |
| `JANELA_RESPOSTA_JOIN` | `0.3` | Tempo de espera por resposta ao procurar um grupo existente |
| `TEMPO_MINIMO_ANTES_PARAR` | `30` | Tempo mínimo de execução antes de qualquer parada (modo normal) |
| `MIN_ITERACOES` | `1000000` | Iterações mínimas antes de a estabilização poder parar a busca |
| `MAX_SYNCS_SEM_MELHORA` | `25` | Sincronizações seguidas sem melhora que caracterizam estabilização |
| `MAX_ITERACOES` | `2000000` | Limite máximo de iterações (modo normal) |
| `NUM_FORMIGAS` | `5` | Formigas por iteração |
| `TIMEOUT_SYNC` | `3` | Janela máxima (s) de espera por respostas de feromônio/recuperação |
| `ITERACOES_BENCHMARK` | `100` | Iterações no modo `--benchmark` |

---

## Instâncias dos módulos

```python
rede    = Rede(MEU_ID, NOS[MEU_ID][1], NOS)
aco     = ACO(DISTANCIAS)
relogio = RelogioLamport()
eleicao = EleicaoLider(MEU_ID, list(NOS.keys()))
membros = MembrosGrupo(MEU_ID)
```

Cada nó cria suas próprias instâncias locais. Eles não compartilham estado — a distribuição acontece apenas pela troca de mensagens.

### Variáveis globais

```python
feromonios_recebidos = {}      # matrizes recebidas dos workers (sync/recuperação)
melhores_recebidos   = {}      # melhor rota/distância recebida de cada worker
rodando              = True    # controla o loop principal
inicio_execucao      = ...     # marca de tempo do início (perf_counter)
ultimo_contato_lider = ...     # marca de tempo do último contato com o líder
melhor_distancia_observada / melhor_rota_observada / syncs_sem_melhora
```

---

## Protocolo de mensagens

Toda mensagem tem `tipo`, `remetente_id`, `timestamp_lamport` e `conteudo` (ver `doc/rede.md`).

| Tipo | Quem envia | Significado |
|---|---|---|
| `JOIN` | Nó entrando | "Existe algum grupo? Quem é o líder?" |
| `JOIN_ACK` | Quem conhece o líder | Informa o `lider_id` ao recém-chegado |
| `REGISTER` | Nó entrando | Pede ao líder para entrar oficialmente no grupo |
| `REGISTER_ACK` | Líder | Confirma o registro e devolve a lista de `participantes` |
| `ELEICAO` | Qualquer nó | Inicia/propaga uma eleição Bully para os IDs maiores |
| `OK` | Nó de ID maior | "Recebi sua eleição; eu assumo a partir daqui" |
| `LIDER` | Novo líder | Anuncia liderança e envia a lista de `participantes` |
| `SOLICITACAO` | Líder | Pede a cada worker sua matriz de feromônio (sincronização) |
| `FEROMONIO` | Worker → líder / líder → workers | Worker envia sua matriz; líder redistribui a média consolidada |
| `RECUPERACAO` | Novo líder | Após assumir, pede o estado salvo de cada worker |
| `RECUPERACAO_RESPOSTA` | Worker | Envia seu estado (`exportar_estado`) ao líder em recuperação |
| `PARAR` | Líder | Sinaliza fim da busca e envia o resultado final |

O roteamento é feito em `processar_mensagem(msg)`, que primeiro chama `registrar_contato_lider(rem)` e depois despacha por `tipo`.

---

## Entrada no grupo (inicialização)

```python
rede.iniciar_servidor()
print(f"[INIT] No {MEU_ID} iniciado.")
tentar_entrar_em_grupo()
```

### `tentar_entrar_em_grupo()`

1. Envia `JOIN` para cada outro nó conhecido.
2. Após cada `JOIN`, processa as mensagens pendentes por `JANELA_RESPOSTA_JOIN` segundos.
3. Se descobrir um líder durante esse processo, para de procurar.
4. Se **nenhum** líder for encontrado após tentar todos, o nó **se declara líder** com `assumir_lider()`.

Esse mecanismo substitui a antiga regra de "o nó de maior ID começa como líder": agora a liderança inicial depende de quem já está no ar, e a eleição Bully corrige qualquer inconsistência (um nó de ID menor que assumiu por chegar primeiro será desafiado quando um ID maior aparecer).

### `processar_join`, `processar_join_ack`, `processar_register`, `processar_register_ack`

- `processar_join` — se eu sei quem é o líder, respondo `JOIN_ACK` com o `lider_id`.
- `processar_join_ack` — aprendo o líder, e se não sou eu, envio `REGISTER` ao líder.
- `processar_register` — o **líder** adiciona o remetente ao grupo e responde `REGISTER_ACK` com a lista de participantes.
- `processar_register_ack` — o nó registra todos os participantes; se descobre que tem ID maior que o líder, inicia eleição.

---

## Eleição de líder (Bully)

### `verificar_lider_morto()`

Chamada a cada ciclo do loop principal. Se o tempo desde `ultimo_contato_lider` ultrapassa `TIMEOUT_LIDER_MORTO` (8s) — e não estou em eleição nem sou o próprio líder — então:

1. removo o líder de `membros`;
2. chamo `eleicao.resetar_lider()`;
3. reinicio `ultimo_contato_lider`;
4. chamo `iniciar_eleicao()`.

### `iniciar_eleicao()`

1. Não faz nada se eu já sou líder ou se já estou em eleição.
2. Recria a instância de `EleicaoLider` (estado limpo) e obtém as mensagens `ELEICAO` para os IDs maiores.
3. Tenta enviar a cada ID maior (`tentar_enviar`, silencioso).
4. Se **nenhum** ID maior pôde ser contatado, chamo `assumir_lider()` imediatamente.

### `processar_eleicao(rem)`

- adiciono `rem` ao grupo;
- se meu ID é menor ou igual ao remetente, ignoro (ele cuida);
- se sou líder, respondo `LIDER`;
- senão, respondo `OK` e inicio minha própria eleição.

### `processar_ok` e `verificar_eleicao()`

- `processar_ok` registra que um nó maior respondeu (`eleicao.ao_receber_ok`).
- `verificar_eleicao()` (no loop) chama `eleicao.verificar_timeout_ok()`; se algum timeout expirou, eu venço e chamo `assumir_lider()`.

### `assumir_lider()`

1. me adiciono ao grupo e marco `ao_receber_lider(MEU_ID)`;
2. envio `LIDER` (com a lista de participantes) a todos os workers, removendo os que falharem;
3. se eu **ainda não era** líder, disparo a **recuperação de estado pós-falha**.

### `aceitar_lider(lider_id)`

Trata todos os casos de receber um anúncio de líder, garantindo coerência do Bully:

- ignoro um líder de ID menor que o atual ou menor que eu (mensagem antiga/errada);
- aceito um líder de ID maior;
- se o líder anunciado é menor que eu, **disputo** iniciando eleição;
- atualizo `ultimo_contato_lider` ao aceitar.

---

## Recuperação de estado pós-falha

Quando um nó assume a liderança pela primeira vez (após a queda do líder anterior), ele reconstrói o estado global a partir do que os sobreviventes conhecem. Este é o **requisito obrigatório** da segunda entrega.

### `recuperar_estado_pos_falha()`

1. envia `RECUPERACAO` a cada worker conhecido (removendo do grupo os que não puderem ser contatados);
2. aguarda respostas por até `TIMEOUT_SYNC` (3s) em `aguardar_recuperacao`;
3. remove do grupo os workers que não responderam;
4. consolida as matrizes recebidas + a própria com `ACO.consolidar_matrizes` (média elemento a elemento);
5. aplica a média localmente com `aco.definir_feromonio`;
6. atualiza o critério de parada;
7. redistribui a matriz consolidada via `FEROMONIO` aos workers ativos.

### `processar_recuperacao` / `processar_recuperacao_resposta`

- um worker, ao receber `RECUPERACAO` do líder legítimo, responde com `RECUPERACAO_RESPOSTA` contendo `aco.exportar_estado()` (matriz + melhor rota + melhor distância);
- o líder coleta cada resposta em `feromonios_recebidos` e `melhores_recebidos`.

Assim, o conhecimento acumulado antes da falha (feromônio **e** melhor rota) não é perdido: o novo líder parte do estado médio dos sobreviventes em vez de recomeçar do zero.

---

## Sincronização periódica

A cada `INTERVALO_SYNC` iterações, **se for líder**, o nó executa `sincronizar(iteracao)`:

1. `solicitar_feromonios(workers)` — envia `SOLICITACAO` a cada worker; remove do grupo quem falha no envio.
2. `aguardar_feromonios(...)` — coleta as respostas `FEROMONIO` por até `TIMEOUT_SYNC`.
3. `remover_workers_sem_resposta(...)` — limpa do grupo quem não respondeu.
4. consolida (`ACO.consolidar_matrizes`) a média das matrizes recebidas + a própria.
5. aplica localmente (`definir_feromonio`) e redistribui `FEROMONIO` aos workers ativos.
6. atualiza o critério de parada e, se ele for atingido, envia `PARAR` e encerra.

> **Detalhe importante:** como as `SOLICITACAO` chegam aos workers a cada ciclo de sync, são elas que renovam o `ultimo_contato_lider` de cada worker. É assim que a vivacidade do líder é detectada sem uma mensagem de heartbeat dedicada.

### `processar_solicitacao` / `processar_feromonio`

- `processar_solicitacao` — só atende se vier do líder atual; responde com `exportar_estado`.
- `processar_feromonio` — se sou líder, **coleto** a matriz do worker; se sou worker e veio do líder, **aplico** a matriz consolidada (`definir_feromonio`).

---

## Critério de parada

### `escolher_melhor_global()` / `atualizar_criterio_parada()`

Reúne a melhor rota local e as melhores recebidas dos workers, escolhe a de menor distância e atualiza `melhor_distancia_observada`/`melhor_rota_observada`. Se não houve melhora, incrementa `syncs_sem_melhora`.

### `verificar_parada(iteracao)`

- **Modo benchmark:** para ao atingir `ITERACOES_BENCHMARK` (100).
- **Modo normal:** nunca para antes de `TEMPO_MINIMO_ANTES_PARAR`; para ao atingir `MAX_ITERACOES`, ou por estabilização (após `MIN_ITERACOES`, quando `syncs_sem_melhora >= MAX_SYNCS_SEM_MELHORA`).

Ao parar, o líder envia `PARAR` (com o resultado consolidado) aos workers e todos imprimem o resultado final via `imprimir_resultado_final`.

---

## Loop principal

```python
iteracao = 0
while rodando:
    msg = rede.receber_proxima()
    if msg:
        relogio.ao_receber(msg["timestamp_lamport"])
        processar_mensagem(msg)

    verificar_lider_morto()
    verificar_eleicao()

    aco.executar_iteracao(num_formigas=NUM_FORMIGAS)
    iteracao += 1

    if iteracao % INTERVALO_SYNC == 0:
        _, dist = aco.obter_melhor_global()
        print(f"[ACO] iter {iteracao} | dist {dist:.2f} | lider: {lider_atual()} | ...")
        if eu_sou_lider():
            sincronizar(iteracao)

    time.sleep(0.01)

rede.parar()
```

| Passo | O que faz |
|---|---|
| 1 | Consome uma mensagem da fila; atualiza o Lamport **antes** de processar |
| 2 | Verifica se o líder está morto (detecção passiva por timeout) |
| 3 | Verifica se algum timeout de eleição expirou |
| 4 | Executa uma iteração local do ACO |
| 5 | A cada `INTERVALO_SYNC` iterações, imprime estado e (se líder) sincroniza |

O `time.sleep(0.01)` evita uso de 100% de CPU; mensagens não se perdem porque ficam enfileiradas na `queue.Queue` interna de `rede.py`.

---

## Threads em execução

| Thread | Função | Intervalo |
|---|---|---|
| Loop principal | Processa mensagens, detecta falha, executa ACO, sincroniza | Contínuo (≈10ms) |
| Servidor TCP (`rede.py`) | Aceita conexões e enfileira mensagens | Contínuo |

Diferente de versões anteriores, **não há thread de heartbeat nem thread de eleição inicial** — tudo é resolvido no loop principal.

---

## Fluxo de uma execução típica com falha

```
Nós sobem em ordem 5→4→3→2→1
  → cada nó faz JOIN, encontra o grupo e REGISTER no líder 5
  → líder 5 sincroniza feromônio a cada 100 iterações

Nó 5 (líder) cai:
  → workers param de receber SOLICITACAO
  → após 8s sem contato, verificar_lider_morto() dispara
  → Nó 4 (maior ID vivo) vence a eleição Bully e assume
  → Nó 4 executa recuperar_estado_pos_falha():
       pede RECUPERACAO aos sobreviventes, consolida a média,
       redistribui o feromônio
  → busca continua normalmente com Nó 4 como líder
```

---

## Saída esperada no terminal

```
[Rede] No 4 escutando na porta 5004
[INIT] No 4 iniciado.
[JOIN] No 4 procurando grupo existente.
[ELEI] Novo lider: No 5
[MEMB] No 4 entrou no grupo do lider 5. ...
[ACO] iter 100 | dist 78.00 | lider: 5 | participantes: -
...
[ELEI] Lider 5 nao respondeu por 8.1s. Iniciando nova eleicao.
[ELEI] No 4 assumiu como lider. Participantes: [1, 2, 3, 4]
[REC] Lider 4 solicitando estados para recuperacao.
[REC] Estado consolidado com 3 worker(s). Participantes: [1, 2, 3, 4]
[SYNC] Feromonio sincronizado com 3 worker(s). melhor=72.00 no=3 ...
```
