import socket
import threading
import json
import queue
import time


DELIMITADOR = b"\n"

TIMEOUT_CONEXAO = 3

BUFFER_SIZE = 4096

# Timeout de leitura de uma conexao recebida. Cada conexao envia uma rajada
# curta de bytes e fecha; o timeout so existe para que uma conexao travada
# (queda abrupta sem fechar o socket) nao segure a thread indefinidamente.
TIMEOUT_RECV = 5


class Rede:


    def __init__(self, meu_id: int, minha_porta: int, nos_conhecidos: dict):
        self.meu_id = meu_id
        self.minha_porta = minha_porta
        self.nos_conhecidos = nos_conhecidos

        # Fila thread-safe onde chegam as mensagens recebidas.
        self._fila: queue.Queue = queue.Queue()

        # Flag para sinalizar que o servidor deve parar (usado em testes).
        self._rodando = False

        # Referência ao socket servidor (guardamos para poder fechar depois).
        self._socket_servidor: socket.socket | None = None

    # API pública

    def iniciar_servidor(self) -> None:
        """
        Sobe o servidor TCP em background (thread daemon).
        Retorna imediatamente — o servidor roda em paralelo.
        """
        self._rodando = True
        t = threading.Thread(target=self._loop_servidor, daemon=True)
        t.start()
        # Pequena pausa para o socket ficar pronto antes de qualquer envio.
        time.sleep(0.1)
        print(f"[Rede] Nó {self.meu_id} escutando na porta {self.minha_porta}")

    def enviar_mensagem(self, destino_id: int, mensagem: dict) -> bool:
        
        if destino_id not in self.nos_conhecidos:
            return False

        host, porta = self.nos_conhecidos[destino_id]

        try:
            # Criamos um socket novo a cada envio (simples e robusto).
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(TIMEOUT_CONEXAO)
                s.connect((host, porta))

                # Serializa o dict como JSON + delimitador.
                dados = json.dumps(mensagem, ensure_ascii=False).encode("utf-8")
                dados += DELIMITADOR
                s.sendall(dados)

            return True

        except (ConnectionRefusedError, TimeoutError, OSError):
            # Nó offline ou rede com problema — esperado durante quedas de
            # líder e eleições. A camada acima (no.py) trata o retorno False.
            return False

    def broadcast(self, mensagem: dict) -> None:

        for destino_id in self.nos_conhecidos:
            if destino_id != self.meu_id:
                self.enviar_mensagem(destino_id, mensagem)

    def receber_proxima(self) -> dict | None:

        try:
            return self._fila.get_nowait()
        except queue.Empty:
            return None

    def parar(self) -> None:

        self._rodando = False
        if self._socket_servidor:
            try:
                self._socket_servidor.close()
            except OSError:
                pass

    # Internos (não usar de fora desta classe) 

    def _loop_servidor(self) -> None:
        """
        Loop principal do servidor TCP. Roda em thread daemon.
        Aceita conexões e delega cada uma para _tratar_conexao().
        """
        self._socket_servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # SO_REUSEADDR evita erro "Address already in use" ao reiniciar rápido.
        self._socket_servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket_servidor.bind(("0.0.0.0", self.minha_porta))
        self._socket_servidor.listen(10)
        self._socket_servidor.settimeout(1.0)  # timeout para checar _rodando

        while self._rodando:
            try:
                conn, endereco = self._socket_servidor.accept()
                # Cada conexão recebida é tratada em thread separada,
                # assim o servidor não trava enquanto lê dados.
                t = threading.Thread(
                    target=self._tratar_conexao,
                    args=(conn, endereco),
                    daemon=True
                )
                t.start()
            except socket.timeout:
                # Timeout normal do accept() — apenas verifica _rodando.
                continue
            except OSError:
                # Socket foi fechado pelo parar() — sai do loop.
                break

    def _tratar_conexao(self, conn: socket.socket, endereco: tuple) -> None:

        buffer = b""
        try:
            with conn:
                # Timeout de leitura: se o outro lado caiu de forma abrupta
                # (queda durante eleição/sync/recuperação) sem fechar a conexão,
                # o recv não fica preso para sempre segurando a thread.
                conn.settimeout(TIMEOUT_RECV)
                while True:
                    try:
                        chunk = conn.recv(BUFFER_SIZE)
                    except socket.timeout:
                        # Conexão ociosa/travada — paramos de ler e processamos
                        # o que já chegou (mensagens completas no buffer).
                        break
                    if not chunk:
                        break
                    buffer += chunk

            # Uma conexão pode conter múltiplas mensagens separadas por \n.
            for parte in buffer.split(DELIMITADOR):
                parte = parte.strip()
                if not parte:
                    continue
                try:
                    mensagem = json.loads(parte.decode("utf-8"))
                    self._fila.put(mensagem)
                except json.JSONDecodeError:
                    # Mensagem malformada — ignora e segue para a próxima.
                    continue

        except (ConnectionResetError, BrokenPipeError, OSError):
            # Queda abrupta da conexão — não deve derrubar o nó.
            pass

    def tentar_enviar_mensagem(self, destino_id: int, mensagem: dict) -> bool:
        if destino_id not in self.nos_conhecidos:
            return False

        host, porta = self.nos_conhecidos[destino_id]

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(TIMEOUT_CONEXAO)
                s.connect((host, porta))

                dados = json.dumps(mensagem, ensure_ascii=False).encode("utf-8")
                dados += DELIMITADOR
                s.sendall(dados)

            return True

        except (ConnectionRefusedError, TimeoutError, OSError):
            return False