# Camada de Comunicação entre Nós (rede.py)

## O que é este módulo

`rede.py` é a camada de comunicação do sistema distribuído de ACO (Algoritmo de Colônia de Formigas). Ele isola toda a complexidade de sockets TCP, threads e serialização JSON em uma única classe - `Rede` - cujas funções públicas são chamadas pelos demais módulos (`aco.py`, `coordenacao.py`, `no.py`) sem que eles precisem saber nada sobre rede.

## Dependências

Apenas biblioteca padrão do Python - nenhuma instalação necessária.

| Módulo | Uso |
|---|---|
| `socket` | Comunicação TCP entre nós |
| `threading` | Servidor roda em thread daemon paralela |
| `json` | Serialização/deserialização das mensagens |
| `queue` | Fila thread-safe para mensagens recebidas |
| `time` | Pausa de inicialização do servidor |

## Constantes de configuração

| Constante | Valor | Descrição |
|---|---:|---|
| `TIMEOUT_CONEXAO` | `3` | Timeout (s) ao abrir conexão para enviar |
| `TIMEOUT_RECV` | `5` | Timeout (s) de leitura de uma conexão recebida — evita que uma conexão travada por queda abrupta segure uma thread para sempre |
| `BUFFER_SIZE` | `4096` | Tamanho do bloco lido por `recv()` |

As falhas de envio (nó offline) e de leitura (conexão caída, JSON inválido) são tratadas silenciosamente — retornam `False` ou são ignoradas, sem poluir o terminal. A camada acima (`no.py`) decide o que fazer com base no retorno.


## Formato padrão de mensagem

Toda mensagem trocada entre nós segue este formato JSON:

```json
{
  "tipo": "TESTE | ELEICAO | OK | LIDER | SOLICITACAO | FEROMONIO",
  "remetente_id": 2,
  "timestamp_lamport": 7,
  "conteudo": { }
}
```

| Campo | Tipo | Descrição |
|---|---|---|
| `tipo` | `str` | Identifica o propósito da mensagem |
| `remetente_id` | `int` | ID do nó que enviou |
| `timestamp_lamport` | `int` | Carimbo do relógio lógico (preenchido pelo módulo `coordenacao.py`) |
| `conteudo` | `dict` | Dados específicos de cada tipo de mensagem |

### Tipos de mensagem e seus `conteudo`

| `tipo` | Quem envia | O que vai em `conteudo` |
|---|---|---|
| `ELEICAO` | Qualquer nó | `{"iniciador_id": 2}` |
| `OK` | Nó com ID maior | `{}` |
| `LIDER` | Novo líder eleito | `{"lider_id": 3}` |
| `SOLICITACAO` | Líder | `{}` |
| `FEROMONIO` | Worker ou Líder | `{"matriz": [[...], ...], "num_iteracoes": 10}` |


## Classe `Rede`

### Construtor

```python
Rede(meu_id: int, minha_porta: int, nos_conhecidos: dict)
```

| Parâmetro | Tipo | Exemplo | Descrição |
|---|---|---|---|
| `meu_id` | `int` | `1` | ID único deste nó |
| `minha_porta` | `int` | `5001` | Porta TCP onde este nó vai escutar |
| `nos_conhecidos` | `dict` | `{1: ('localhost', 5001), 2: ('localhost', 5002)}` | Mapa de todos os nós do sistema |


### Métodos públicos

#### `iniciar_servidor() → None`

Sobe o servidor TCP em uma thread daemon em background. Retorna imediatamente - o servidor roda em paralelo com o restante do programa.

Deve ser chamado uma única vez, logo após instanciar a classe.

```python
rede.iniciar_servidor()
# A partir daqui o nó já aceita conexões de outros nós.
```

> **Detalhe de implementação:** o servidor usa `SO_REUSEADDR` para evitar o erro `Address already in use` ao reiniciar o processo rapidamente. O `accept()` tem timeout de 1 segundo para verificar periodicamente se o servidor deve parar.


#### `enviar_mensagem(destino_id: int, mensagem: dict) → bool`

Envia uma mensagem JSON para o nó de destino via TCP.

- Retorna `True` se o envio foi bem-sucedido.
- Retorna `False` se o nó estiver offline ou ocorrer qualquer erro de rede - sem lançar exceção.
- Timeout de conexão: 3 segundos.

```python
mensagem = {
    "tipo": "ELEICAO",
    "remetente_id": 1,
    "timestamp_lamport": 4,
    "conteudo": {"iniciador_id": 1}
}

sucesso = rede.enviar_mensagem(destino_id=2, mensagem=mensagem)

if not sucesso:
    print("Nó 2 está offline — iniciar eleição?")
```

> **Detalhe de implementação:** abre e fecha uma conexão TCP a cada envio.


#### `tentar_enviar_mensagem(destino_id: int, mensagem: dict) → bool`

Variante de melhor-esforço (*best-effort*) de `enviar_mensagem`, com o mesmo comportamento: abre a conexão, envia JSON + delimitador e retorna `True`/`False`.

É usada por `no.py` nos pontos em que uma falha de envio é esperada e não é problema — por exemplo, ao **procurar um grupo** na inicialização (`JOIN` para nós que podem não estar no ar) ou ao **disparar uma eleição** (`ELEICAO` para nós maiores que podem ter caído). O nome deixa explícito, no chamador, que ali a falha é tolerada; o `False` já é tratado pela lógica de `no.py`.


#### `broadcast(mensagem: dict) → None`

Envia a mensagem para todos os nós conhecidos, exceto este próprio. Continua mesmo que alguns nós estejam offline.

```python
mensagem = {
    "tipo": "LIDER",
    "remetente_id": 3,
    "timestamp_lamport": 9,
    "conteudo": {"lider_id": 3}
}

rede.broadcast(mensagem)
```

#### `receber_proxima() → dict | None`

Retorna a próxima mensagem da fila interna (ordem FIFO), ou `None` se não houver mensagens. Não bloqueia - retorna imediatamente.

Deve ser chamada em loop no programa principal (`no.py`):

```python
while True:
    msg = rede.receber_proxima()
    if msg:
        # processa a mensagem
        print(f"Recebi: {msg['tipo']} de nó {msg['remetente_id']}")
    time.sleep(0.01)
```

#### `parar() → None`

Encerra o servidor TCP e libera a porta.

```python
rede.parar()
```

## Arquitetura interna

```

                    Classe Rede                       
                                                      
  Thread principal (no.py)                            
  ┌──────────────────────────────────────────────┐   
  │  enviar_mensagem() ──► socket TCP ──► nó B   │   
  │  broadcast()       ──► socket TCP ──► nós... │   
  │  receber_proxima() ◄── queue.Queue           │   
  └──────────────────────────────────────────────┘   
                          ▲                          
  Thread daemon (servidor)│                          
  ┌───────────────────────┴───────────────────────┐   
  │  _loop_servidor()                             │  
  │    └── accept() ──► _tratar_conexao() (thread)│  
  │                          └── json.loads()     │  
  │                          └── queue.put()      │  
  └───────────────────────────────────────────────┘   

```

### Fluxo de recebimento

1. `_loop_servidor()` roda em uma thread daemon e chama `accept()` em loop.
2. Para cada conexão aceita, dispara uma nova thread chamando `_tratar_conexao()`.
3. `_tratar_conexao()` lê todos os bytes da conexão, divide pelo `DELIMITADOR` (`\n`) e faz `json.loads()` em cada parte.
4. O dict resultante é colocado na `queue.Queue` interna.
5. O código em `no.py` consome a fila chamando `receber_proxima()` no loop principal.

### Fluxo de envio

1. `enviar_mensagem()` serializa o dict como JSON com `json.dumps()`, adiciona `\n` ao final.
2. Abre uma conexão TCP com `socket.connect()`, chama `sendall()` e fecha.
3. Todo esse bloco está dentro de `try/except` — falhas retornam `False` silenciosamente.

## Como testar

### Teste automático

```bash
python teste_rede.py auto
```

Executa 4 cenários e imprime OK em cada um:

| Teste | O que verifica |
|---|---|
| 1 - Envio direto | Nó 2 envia para Nó 1; Nó 1 recebe corretamente |
| 2 - Broadcast | Nó 1 faz broadcast; Nós 2 e 3 recebem; Nó 1 não recebe a si mesmo |
| 3 - Nó offline | `enviar_mensagem()` retorna `False` sem travar quando destino está fora |
| 4 - Múltiplas mensagens | 5 mensagens enviadas em sequência chegam todas |

### Teste com terminais reais

Abra dois terminais na pasta `src/`:

```bash
# Terminal 1
python teste_rede.py servidor 1

# Terminal 2
python teste_rede.py cliente 2 1
```
