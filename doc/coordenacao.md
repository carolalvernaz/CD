# Relógio de Lamport e Eleição de Líder (coordenacao.py)

## O que é este módulo

`coordenacao.py` implementa os dois requisitos técnicos obrigatórios do sistema distribuído de ACO. Ele contém duas classes independentes que trabalham juntas: `RelogioLamport` carimba cada mensagem com um timestamp lógico, e `EleicaoLider` decide qual nó coordena a sincronização de feromônio. Ambas são usadas diretamente por `no.py` — nenhum outro módulo precisa conhecer os detalhes internos.

## Dependências

Apenas biblioteca padrão do Python - nenhuma instalação necessária.

| Módulo | Uso |
|---|---|
| `threading` | Proteção de estado compartilhado entre threads com `Lock` |
| `time` | Medição de timeouts para a eleição |

## Constantes de configuração

| Constante | Valor | Descrição |
|---|---|---|
| `TIMEOUT_OK` | `2.0s` | Tempo máximo aguardando resposta OK de um nó maior antes de se declarar líder |
| `TIMEOUT_LIDER` | `5.0s` | Tempo máximo aguardando anúncio LIDER após receber OK — cobre o caso em que o nó maior que respondeu também cai |

---

## Classe `RelogioLamport`

### O que resolve

Em sistemas distribuídos, não existe um relógio global. Duas máquinas podem processar eventos no mesmo instante de tempo real mas em ordens lógicas diferentes. O Relógio de Lamport resolve isso: em vez de usar o horário do sistema, cada nó mantém um contador inteiro que só cresce. As regras de atualização garantem que, se o evento A causou o evento B, então o timestamp de A é sempre menor que o de B — estabelecendo uma ordem parcial consistente entre todos os nós.

No contexto do ACO, isso garante que atualizações de feromônio mais recentes não sejam sobrescritas por mensagens atrasadas na rede.

### Construtor

```python
RelogioLamport()
```

Inicializa o contador em `0`. Cada nó cria sua própria instância.

### Métodos públicos

#### `antes_de_enviar() → int`

Incrementa o relógio e retorna o timestamp a ser colocado no campo `timestamp_lamport` da mensagem. Deve ser chamado imediatamente antes de qualquer `enviar_mensagem()`.

```python
ts = relogio.antes_de_enviar()
msg["timestamp_lamport"] = ts
rede.enviar_mensagem(destino_id, msg)
```

#### `ao_receber(timestamp_recebido: int) → None`

Atualiza o relógio ao receber uma mensagem. Deve ser chamado antes de processar o conteúdo da mensagem.

A regra é: `tempo = max(tempo_local, timestamp_recebido) + 1`. Isso garante que o evento de recebimento seja sempre posterior ao evento de envio, em qualquer nó.

```python
msg = rede.receber_proxima()
if msg:
    relogio.ao_receber(msg["timestamp_lamport"])
    processar_mensagem(msg)
```

#### `evento_interno() → int`

Incrementa o relógio para eventos locais que não envolvem envio nem recebimento de mensagens. Uso opcional nesta entrega.

```python
ts = relogio.evento_interno()
```

#### `obter() → int`

Retorna o valor atual do relógio sem modificá-lo. Útil para logs e diagnóstico.

```python
print(f"Timestamp atual: {relogio.obter()}")
```

### Regras de uso (obrigatórias)

| Situação | O que chamar |
|---|---|
| Antes de qualquer envio | `antes_de_enviar()` → colocar resultado em `timestamp_lamport` |
| Ao receber qualquer mensagem | `ao_receber(msg["timestamp_lamport"])` antes de processar |
| Eventos locais sem comunicação | `evento_interno()` (opcional) |

> **Detalhe de implementação:** todos os métodos são protegidos por `threading.Lock`. O relógio pode ser acessado simultaneamente pela thread do loop principal e pela thread de heartbeat sem risco de corrida.

---

## Classe `EleicaoLider`

### O que resolve

No ACO distribuído, um nó precisa coordenar a sincronização da matriz de feromônio — consolidando os resultados de todos os workers e redistribuindo o feromônio combinado. Esse coordenador é o líder. O algoritmo Bully garante que, se o líder atual cair, o nó com maior ID entre os sobreviventes assume automaticamente, sem intervenção manual.

A classe gerencia todo o estado interno da eleição e expõe apenas mensagens prontas para envio — `no.py` não precisa conhecer o protocolo, apenas transmitir o que `EleicaoLider` retornar.

### Construtor

```python
EleicaoLider(meu_id: int, todos_ids: list)
```

| Parâmetro | Tipo | Exemplo | Descrição |
|---|---|---|---|
| `meu_id` | `int` | `2` | ID único deste nó |
| `todos_ids` | `list` | `[1, 2, 3]` | Lista com os IDs de todos os nós do sistema |

### Métodos públicos

#### `iniciar_eleicao() → list[dict]`

Inicia uma eleição e retorna a lista de mensagens `ELEICAO` para enviar aos nós com ID maior. Retorna lista vazia se já houver uma eleição em andamento, ou se este for o nó com maior ID (nesse caso, aguarda o timeout para se declarar líder).

```python
mensagens = eleicao.iniciar_eleicao()
for m in mensagens:
    m["timestamp_lamport"] = relogio.antes_de_enviar()
    rede.enviar_mensagem(m["destino_id"], m)
```

#### `ao_receber_eleicao(remetente_id: int) → dict`

Processa uma mensagem `ELEICAO` recebida. Retorna um dicionário com duas chaves:

- `"ok"` — mensagem `OK` pronta para enviar ao remetente.
- `"eleicao"` — lista de mensagens `ELEICAO` para propagar aos nós maiores (vazia se este for o maior nó vivo).

```python
resultado = eleicao.ao_receber_eleicao(remetente)

ok = resultado["ok"]
ok["timestamp_lamport"] = relogio.antes_de_enviar()
rede.enviar_mensagem(ok["destino_id"], ok)

for m in resultado["eleicao"]:
    m["timestamp_lamport"] = relogio.antes_de_enviar()
    rede.enviar_mensagem(m["destino_id"], m)
```

#### `ao_receber_ok(remetente_id: int) → None`

Registra que um nó maior respondeu à eleição. Reinicia o timer interno: a partir deste momento, o nó aguarda `TIMEOUT_LIDER` segundos pelo anúncio de LIDER — não mais `TIMEOUT_OK`.

```python
eleicao.ao_receber_ok(remetente_id)
```

#### `ao_receber_lider(lider_id: int) → None`

Atualiza o líder atual e encerra o estado de eleição. Deve ser chamado ao receber mensagem `LIDER` ou para definir um líder inicial na inicialização do sistema.

```python
eleicao.ao_receber_lider(lider_id=3)
```

#### `verificar_timeout_ok() → list[dict]`

Deve ser chamado periodicamente no loop principal. Verifica se algum dos dois timeouts expirou e, se sim, declara este nó como líder e retorna a lista de mensagens `LIDER` para broadcast. Retorna lista vazia enquanto nenhum timeout tiver expirado.

```python
# No loop principal de no.py:
mensagens_lider = eleicao.verificar_timeout_ok()
for m in mensagens_lider:
    rede.enviar_mensagem(m["destino_id"], m)
```

#### `obter_lider() → int | None`

Retorna o ID do líder atual, ou `None` se ainda não há líder definido.

```python
lider = eleicao.obter_lider()
if lider is None:
    print("Sem líder — eleição necessária")
```

#### `eu_sou_lider() → bool`

Atalho para verificar se este nó é o líder atual.

```python
if eleicao.eu_sou_lider():
    solicitar_e_redistribuir_feromonio()
```

#### `em_eleicao() → bool`

Retorna `True` se uma eleição estiver em andamento. Usado pelo heartbeat para pausar verificações de falha durante a eleição.

```python
if eleicao.em_eleicao():
    continue  # não envia heartbeat durante eleição
```

#### `resetar_lider() → None`

Limpa o líder atual sem iniciar eleição. Deve ser chamado antes de `iniciar_eleicao()` quando o heartbeat detecta falha do líder. Não faz nada se já houver uma eleição em andamento.

```python
eleicao.resetar_lider()
eleicao.iniciar_eleicao()
```

### Fluxo completo do algoritmo Bully

```
Nó 1                    Nó 2                    Nó 3 (caiu)
  │                       │                         ✕
  │── HB falha ×2 ────────┤
  │   resetar_lider()     │── HB falha ×2
  │   iniciar_eleicao()   │   resetar_lider()
  │                       │   iniciar_eleicao()
  │── ELEICAO ───────────►│
  │◄─────────────── OK ───│
  │   ao_receber_ok()     │   (sem nós maiores)
  │   timer reiniciado    │   aguarda TIMEOUT_OK
  │   aguarda TIMEOUT_    │
  │   LIDER               │── LIDER (broadcast) ──►│ (nó 1)
  │◄──────────── LIDER ───│
  │   ao_receber_lider(2) │   lider_atual = 2
  │   lider_atual = 2     │
```

### Decisões de design

**Por que dois timeouts (`TIMEOUT_OK` e `TIMEOUT_LIDER`)?**
O Bully clássico usa apenas um timeout. O problema é que, se o nó 1 recebe OK do nó 2 mas o nó 2 também cai antes de anunciar LIDER, o nó 1 fica bloqueado esperando para sempre. O segundo timeout (`TIMEOUT_LIDER = 5.0s`) cobre esse cenário: se ninguém anunciar LIDER dentro do prazo, o nó que estava aguardando assume a liderança mesmo assim.

**Por que o timer é reiniciado em `ao_receber_ok()`?**
Ao receber OK, o nó sabe que existe alguém maior vivo — e esse alguém precisa de tempo para concluir sua própria eleição antes de anunciar LIDER. Reiniciar o timer dá a esse nó uma janela limpa de `TIMEOUT_LIDER` segundos. Sem o reinício, o timer poderia expirar logo após o OK, fazendo dois nós se declararem líder simultaneamente.

**Por que retornar mensagens prontas em vez de enviar diretamente?**
`EleicaoLider` não conhece a classe `Rede` — recebe e devolve dicts, nada mais. Isso mantém o módulo testável em isolamento (sem sockets) e segue o mesmo contrato que os outros módulos expõem para `no.py`.

---

## Classe `MembrosGrupo`

### O que resolve

O sistema é dinâmico: nós entram pelo protocolo de JOIN/REGISTER e saem quando falham. Para que o líder saiba **para quem** enviar solicitações de feromônio, recuperação de estado e o sinal de parada, ele precisa manter uma lista atualizada dos participantes ativos. `MembrosGrupo` encapsula esse conjunto de IDs de forma thread-safe.

Cada nó mantém sua própria instância. O próprio ID nunca é removido do conjunto.

### Construtor

```python
MembrosGrupo(meu_id: int)
```

Inicializa o conjunto de participantes contendo apenas o próprio nó.

### Métodos públicos

#### `adicionar(no_id: int) -> None`

Adiciona um nó ao grupo. Chamado sempre que se recebe uma mensagem de um nó conhecido (eleição, registro, líder etc.).

#### `adicionar_varios(ids: list[int]) -> None`

Adiciona vários nós de uma vez. Usado ao receber a lista de `participantes` que acompanha mensagens `LIDER` e `REGISTER_ACK`. Garante que o próprio ID continue presente.

#### `remover(no_id: int) -> None`

Remove um nó do grupo. Chamado quando um worker não responde a um envio, a uma sincronização ou a uma recuperação. **Nunca remove o próprio nó.**

#### `listar() -> list[int]`

Retorna a lista ordenada de todos os participantes (incluindo o próprio nó). Usada em logs e enviada no campo `participantes` das mensagens `LIDER`/`REGISTER_ACK`.

#### `workers() -> list[int]`

Retorna a lista ordenada de participantes **exceto** o próprio nó. É a lista que o líder percorre para solicitar feromônio, pedir recuperação de estado e enviar o sinal de parada.

### Por que uma classe separada?

Mantém toda a lógica de pertinência ao grupo (e a proteção por `Lock`) isolada de `no.py`, no mesmo padrão das demais classes de `coordenacao.py`: estado interno protegido, API simples e testável. O líder e os workers usam exatamente os mesmos métodos — a diferença de comportamento fica em `no.py`.

---

## Como testar

### Teste do Relógio de Lamport

```bash
python teste_lamport.py
```

Simula 3 nós trocando mensagens em sequência e imprime o timestamp de cada um após cada evento. A saída deve mostrar o relógio nunca regredindo e mensagens recebidas sempre com timestamp maior que o do envio.

### Teste do Bully

```bash
python teste_bully.py
```

Inicia 3 nós com o Nó 3 como líder. Derruba o Nó 3 e aguarda o Nó 2 ser eleito. Derruba o Nó 2 e aguarda o Nó 1 ser eleito. O teste usa polling com timeout de 12 segundos por evento — não há `sleep` fixo, o assert só é verificado após confirmação do novo líder.

| Etapa | O que verifica |
|---|---|
| Inicialização | Todos os nós reconhecem Nó 3 como líder |
| Queda do Nó 3 | Nós 1 e 2 detectam falha via heartbeat e elegem Nó 2 |
| Queda do Nó 2 | Nó 1 detecta falha, inicia eleição, se declara líder por timeout |

