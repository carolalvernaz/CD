from rede import Rede
from aco import ACO
from coordenacao import RelogioLamport, EleicaoLider, MembrosGrupo
from data.instancia import DISTANCIAS, formatar_rota
import sys
import time


NOS = {
    1: ("localhost", 5001),
    2: ("localhost", 5002),
    3: ("localhost", 5003),
    4: ("localhost", 5004),
    5: ("localhost", 5005),
}

TIMEOUT_LIDER_MORTO = 8
INTERVALO_SYNC = 100
JANELA_RESPOSTA_JOIN = 0.3
TEMPO_MINIMO_ANTES_PARAR = 30
MIN_ITERACOES = 1000000
MAX_SYNCS_SEM_MELHORA = 25
MAX_ITERACOES = 2000000
NUM_FORMIGAS = 5
TIMEOUT_SYNC = 3
ITERACOES_BENCHMARK = 100


def validar_argumentos():
    argumentos = sys.argv[1:]

    if not 1 <= len(argumentos) <= 2:
        ids_validos = ", ".join(str(no_id) for no_id in NOS)
        print("Uso: python src\\no.py <id_do_no>")
        print("Opcional: acrescente --benchmark para executar 100 iteracoes.")
        print(f"IDs validos: {ids_validos}")
        sys.exit(1)

    try:
        meu_id = int(argumentos[0])
    except ValueError:
        print("O ID do no deve ser um numero inteiro.")
        sys.exit(1)

    if meu_id not in NOS:
        ids_validos = ", ".join(str(no_id) for no_id in NOS)
        print(f"ID invalido: {meu_id}. IDs validos: {ids_validos}")
        sys.exit(1)

    modo_benchmark = False

    if len(argumentos) == 2:
        if argumentos[1] != "--benchmark":
            print("Segundo argumento invalido. Use apenas --benchmark.")
            sys.exit(1)

        modo_benchmark = True

    return meu_id, modo_benchmark


MEU_ID, MODO_BENCHMARK = validar_argumentos()

rede = Rede(MEU_ID, NOS[MEU_ID][1], NOS)
aco = ACO(DISTANCIAS)
relogio = RelogioLamport()
eleicao = EleicaoLider(MEU_ID, list(NOS.keys()))
membros = MembrosGrupo(MEU_ID)

feromonios_recebidos = {}
melhores_recebidos = {}

rodando = True
inicio_execucao = time.perf_counter()
ultimo_contato_lider = time.time()

melhor_distancia_observada = float("inf")
melhor_rota_observada = []
syncs_sem_melhora = 0


def montar_mensagem(tipo, conteudo=None):
    if conteudo is None:
        conteudo = {}

    return {
        "tipo": tipo,
        "remetente_id": MEU_ID,
        "timestamp_lamport": relogio.antes_de_enviar(),
        "conteudo": conteudo,
    }


def enviar(destino_id, tipo, conteudo=None):
    mensagem = montar_mensagem(tipo, conteudo)
    return rede.enviar_mensagem(destino_id, mensagem)


def tentar_enviar(destino_id, tipo, conteudo=None):
    mensagem = montar_mensagem(tipo, conteudo)
    return rede.tentar_enviar_mensagem(destino_id, mensagem)


def lider_atual():
    return eleicao.obter_lider()


def eu_sou_lider():
    return eleicao.eu_sou_lider()


def registrar_contato_lider(rem):
    global ultimo_contato_lider

    if rem == lider_atual():
        ultimo_contato_lider = time.time()


def verificar_lider_morto():
    global ultimo_contato_lider

    lider = lider_atual()

    if lider is None:
        return

    if lider == MEU_ID:
        return

    if eleicao.em_eleicao():
        return

    tempo_sem_lider = time.time() - ultimo_contato_lider

    if tempo_sem_lider < TIMEOUT_LIDER_MORTO:
        return

    print(
        f"[ELEI] Lider {lider} nao respondeu por "
        f"{tempo_sem_lider:.1f}s. Iniciando nova eleicao."
    )

    membros.remover(lider)
    eleicao.resetar_lider()
    ultimo_contato_lider = time.time()

    iniciar_eleicao()


def assumir_lider():
    ja_era_lider = eu_sou_lider()

    membros.adicionar(MEU_ID)
    eleicao.ao_receber_lider(MEU_ID)

    conteudo_lider = {
        "lider_id": MEU_ID,
        "participantes": membros.listar(),
    }

    for no_id in membros.workers():
        if not enviar(no_id, "LIDER", conteudo_lider):
            membros.remover(no_id)

    if not ja_era_lider:
        print(f"[ELEI] No {MEU_ID} assumiu como lider. Participantes: {membros.listar()}")

        recuperar_estado_pos_falha()


def aceitar_lider(lider_id):
    global ultimo_contato_lider

    lider_anterior = lider_atual()

    if lider_id not in NOS:
        return False

    membros.adicionar(lider_id)

    # Se eu sou líder e recebo líder menor, é mensagem antiga/errada.
    # Exemplo: eu sou 4 e recebo "líder 2".
    if eu_sou_lider() and lider_id < MEU_ID:
        print(f"[ELEI] Ignorando lider antigo {lider_id}; eu ja sou lider.")
        return False

    # Se eu sou líder e recebo líder maior, preciso aceitar.
    # Exemplo: eu sou 2 e recebo "líder 4".
    if eu_sou_lider() and lider_id > MEU_ID:
        eleicao.ao_receber_lider(lider_id)
        ultimo_contato_lider = time.time()
        print(f"[ELEI] Novo lider: No {lider_id}")
        return True

    # Mensagem duplicada do líder atual.
    if lider_anterior == lider_id:
        ultimo_contato_lider = time.time()
        return False

    # Se eu conheço um líder maior que o líder recebido, ignoro o antigo.
    if lider_anterior is not None and lider_anterior > lider_id:
        print(f"[ELEI] Ignorando lider antigo {lider_id}; lider atual: {lider_anterior}.")
        return False

    # Se o líder recebido é menor que eu, eu disputo.
    if MEU_ID > lider_id:
        print(f"[ELEI] Lider {lider_id} tem ID menor; iniciando eleicao.")
        iniciar_eleicao()
        return False

    eleicao.ao_receber_lider(lider_id)
    ultimo_contato_lider = time.time()

    if lider_anterior != lider_id:
        print(f"[ELEI] Novo lider: No {lider_id}")
        return True

    return False


def iniciar_eleicao():
    global eleicao

    if eu_sou_lider():
        return

    if eleicao.em_eleicao():
        return

    eleicao = EleicaoLider(MEU_ID, list(NOS.keys()))
    mensagens = eleicao.iniciar_eleicao()
    contatou_maior = False

    for mensagem in mensagens:
        destino = mensagem["destino_id"]

        if tentar_enviar(destino, "ELEICAO", mensagem["conteudo"]):
            contatou_maior = True

    if not contatou_maior:
        assumir_lider()


def verificar_eleicao():
    if eleicao.verificar_timeout_ok():
        assumir_lider()


def formatar_matriz(matriz):
    return "\n".join(
        " ".join(f"{valor:8.3f}" for valor in linha)
        for linha in matriz
    )


def imprimir_resultado_final(resultado):
    print("\n========== RESULTADO FINAL ==========")
    print(f"No: {MEU_ID}")
    print(f"Motivo da parada: {resultado['motivo']}")
    print(f"Iteracao final do lider: {resultado['iteracao']}")
    if "tempo_total" in resultado:
        print(f"Tempo total de execucao: {resultado['tempo_total']:.2f}s")
    print(f"Melhor distancia global: {resultado['melhor_distancia']:.2f}")
    print(f"Melhor rota global: {formatar_rota(resultado['melhor_rota'])}")
    print("\nMatriz final de feromonio:")
    print(formatar_matriz(resultado["matriz_feromonio"]))
    print("=====================================\n")


def processar_join(rem):
    if eu_sou_lider():
        enviar(rem, "JOIN_ACK", {
            "lider_id": MEU_ID,
        })
        return

    if lider_atual() is not None:
        enviar(rem, "JOIN_ACK", {
            "lider_id": lider_atual(),
        })


def processar_join_ack(rem, conteudo):
    global ultimo_contato_lider

    lider_id = conteudo.get("lider_id")

    if lider_id is None:
        return

    membros.adicionar(rem)

    lider_anterior = lider_atual()

    if lider_anterior != lider_id:
        eleicao.ao_receber_lider(lider_id)
        ultimo_contato_lider = time.time()
        print(f"[ELEI] Novo lider: No {lider_id}")

    if lider_id != MEU_ID:
        enviar(lider_id, "REGISTER", {})


def processar_recuperacao(rem, conteudo):
    lider_solicitante = conteudo.get("lider_id")

    if lider_solicitante != rem:
        return

    enviar(rem, "RECUPERACAO_RESPOSTA", aco.exportar_estado())


def processar_recuperacao_resposta(rem, conteudo):
    if not eu_sou_lider():
        return

    matriz = conteudo.get("matriz")

    if matriz is None:
        return

    feromonios_recebidos[rem] = matriz
    melhores_recebidos[rem] = {
        "rota": conteudo.get("melhor_rota", []),
        "distancia": conteudo.get("melhor_distancia", float("inf")),
    }


def aguardar_recuperacao(workers_contatados):
    prazo = time.time() + TIMEOUT_SYNC

    while time.time() < prazo and rodando:
        msg = rede.receber_proxima()

        if msg:
            relogio.ao_receber(msg["timestamp_lamport"])
            processar_mensagem(msg)
            continue

        if all(worker in feromonios_recebidos for worker in workers_contatados):
            break

        time.sleep(0.1)


def recuperar_estado_pos_falha():
    if not eu_sou_lider():
        return

    workers = membros.workers()

    if not workers:
        return

    print(f"[REC] Lider {MEU_ID} solicitando estados para recuperacao.")

    feromonios_recebidos.clear()
    melhores_recebidos.clear()

    workers_contatados = []

    for worker in workers:
        if enviar(worker, "RECUPERACAO", {"lider_id": MEU_ID}):
            workers_contatados.append(worker)
        else:
            membros.remover(worker)
            print(f"[MEMB] No {worker} removido do grupo: falha ao solicitar recuperacao.")

    aguardar_recuperacao(workers_contatados)

    for worker in workers_contatados:
        if worker not in feromonios_recebidos:
            membros.remover(worker)
            print(f"[MEMB] No {worker} removido do grupo: nao respondeu a recuperacao.")

    workers_ativos = [
        worker
        for worker in workers_contatados
        if worker in feromonios_recebidos
    ]

    matrizes = list(feromonios_recebidos.values()) + [aco.obter_feromonio()]
    media = ACO.consolidar_matrizes(matrizes)

    aco.definir_feromonio(media)
    atualizar_criterio_parada()

    for worker in workers_ativos:
        enviar(worker, "FEROMONIO", {
            "matriz": media,
        })

    print(
        f"[REC] Estado consolidado com {len(workers_ativos)} worker(s). "
        f"Participantes: {membros.listar()}"
    )


def processar_register(rem):
    if eu_sou_lider():
        membros.adicionar(rem)

        print(
            f"[MEMB] No {rem} entrou no grupo do lider {MEU_ID}. "
            f"Participantes: {membros.listar()}"
        )

        enviar(rem, "REGISTER_ACK", {
            "lider_id": MEU_ID,
            "participantes": membros.listar(),
        })
        return

    if lider_atual() is not None:
        enviar(rem, "JOIN_ACK", {
            "lider_id": lider_atual(),
        })


def processar_register_ack(rem, conteudo):
    lider_id = conteudo.get("lider_id")

    if lider_id is None:
        return

    membros.adicionar(rem)
    membros.adicionar_varios(conteudo.get("participantes", []))

    if MEU_ID > lider_id:
        print(f"[ELEI] Lider {lider_id} tem ID menor; iniciando eleicao.")
        iniciar_eleicao()
        return

    aceitar_lider(lider_id)


def processar_eleicao(rem):
    membros.adicionar(rem)

    if MEU_ID <= rem:
        return

    if eu_sou_lider():
        enviar(rem, "LIDER", {
            "lider_id": MEU_ID,
            "participantes": membros.listar(),
        })
        return

    enviar(rem, "OK", {})
    iniciar_eleicao()


def processar_ok(rem):
    membros.adicionar(rem)
    eleicao.ao_receber_ok(rem)


def processar_lider(rem, conteudo):
    lider_id = conteudo.get("lider_id")

    if lider_id is None:
        return

    membros.adicionar(rem)
    membros.adicionar_varios(conteudo.get("participantes", []))

    aceitar_lider(lider_id)


def processar_solicitacao(rem):
    if rem != lider_atual():
        print(f"[SYNC] Ignorando solicitacao de no {rem}; lider atual: {lider_atual()}.")
        return

    enviar(rem, "FEROMONIO", aco.exportar_estado())


def processar_feromonio(rem, conteudo):
    matriz = conteudo.get("matriz")

    if matriz is None:
        return

    if eu_sou_lider():
        feromonios_recebidos[rem] = matriz
        melhores_recebidos[rem] = {
            "rota": conteudo.get("melhor_rota", []),
            "distancia": conteudo.get("melhor_distancia", float("inf")),
        }
        return

    if rem == lider_atual():
        aco.definir_feromonio(matriz)
        print(f"[SYNC] Feromonio consolidado recebido do lider {rem} e aplicado.")
        return

    print(f"[SYNC] Ignorando feromonio de no {rem}; lider atual: {lider_atual()}.")


def processar_parar(rem, conteudo):
    global rodando

    if rem != lider_atual():
        print(f"[SYNC] Ignorando PARAR de no {rem}; lider atual: {lider_atual()}.")
        return

    aco.definir_feromonio(conteudo["matriz_feromonio"])
    imprimir_resultado_final(conteudo)
    rodando = False


def processar_mensagem(msg):
    tipo = msg["tipo"]
    rem = msg["remetente_id"]
    conteudo = msg.get("conteudo", {})

    registrar_contato_lider(rem)

    if tipo == "JOIN":
        processar_join(rem)

    elif tipo == "JOIN_ACK":
        processar_join_ack(rem, conteudo)

    elif tipo == "REGISTER":
        processar_register(rem)

    elif tipo == "REGISTER_ACK":
        processar_register_ack(rem, conteudo)

    elif tipo == "ELEICAO":
        processar_eleicao(rem)

    elif tipo == "OK":
        processar_ok(rem)

    elif tipo == "LIDER":
        processar_lider(rem, conteudo)

    elif tipo == "SOLICITACAO":
        processar_solicitacao(rem)

    elif tipo == "RECUPERACAO":
        processar_recuperacao(rem, conteudo)

    elif tipo == "RECUPERACAO_RESPOSTA":
        processar_recuperacao_resposta(rem, conteudo)

    elif tipo == "FEROMONIO":
        processar_feromonio(rem, conteudo)

    elif tipo == "PARAR":
        processar_parar(rem, conteudo)


def processar_mensagens_pendentes(ate_quando):
    while time.time() < ate_quando:
        msg = rede.receber_proxima()

        if msg:
            relogio.ao_receber(msg["timestamp_lamport"])
            processar_mensagem(msg)
        else:
            time.sleep(0.05)


def tentar_entrar_em_grupo():
    print(f"[JOIN] No {MEU_ID} procurando grupo existente.")

    for destino_id in NOS:
        if destino_id == MEU_ID:
            continue

        tentar_enviar(destino_id, "JOIN", {})
        processar_mensagens_pendentes(time.time() + JANELA_RESPOSTA_JOIN)

        if lider_atual() is not None:
            break

    if lider_atual() is None:
        assumir_lider()


def escolher_melhor_global():
    rota_local, dist_local = aco.obter_melhor_global()

    candidatos = [
        {
            "no_id": MEU_ID,
            "rota": rota_local,
            "distancia": dist_local,
        }
    ]

    for no_id, melhor in melhores_recebidos.items():
        candidatos.append({
            "no_id": no_id,
            "rota": melhor["rota"],
            "distancia": melhor["distancia"],
        })

    return min(candidatos, key=lambda item: item["distancia"])


def atualizar_criterio_parada():
    global melhor_distancia_observada
    global melhor_rota_observada
    global syncs_sem_melhora

    melhor = escolher_melhor_global()

    if melhor["distancia"] < melhor_distancia_observada:
        melhor_distancia_observada = melhor["distancia"]
        melhor_rota_observada = melhor["rota"]
        syncs_sem_melhora = 0
    else:
        syncs_sem_melhora += 1

    return melhor


def verificar_parada(iteracao):
    if MODO_BENCHMARK:
        if iteracao >= ITERACOES_BENCHMARK:
            return True, f"benchmark de {ITERACOES_BENCHMARK} iteracoes concluido"

        return False, ""

    if time.perf_counter() - inicio_execucao < TEMPO_MINIMO_ANTES_PARAR:
        return False, ""

    if iteracao >= MAX_ITERACOES:
        return True, "limite maximo de iteracoes atingido"

    if iteracao >= MIN_ITERACOES and syncs_sem_melhora >= MAX_SYNCS_SEM_MELHORA:
        return True, "melhor rota estabilizou"

    return False, ""


def solicitar_feromonios(workers):
    workers_contatados = []

    for worker in workers:
        if enviar(worker, "SOLICITACAO", {}):
            workers_contatados.append(worker)
        else:
            membros.remover(worker)
            print(f"[MEMB] No {worker} removido do grupo: falha no envio.")

    return workers_contatados


def aguardar_feromonios(workers_contatados):
    prazo = time.time() + TIMEOUT_SYNC

    while time.time() < prazo and rodando:
        msg = rede.receber_proxima()

        if msg:
            relogio.ao_receber(msg["timestamp_lamport"])
            processar_mensagem(msg)
            continue

        if all(worker in feromonios_recebidos for worker in workers_contatados):
            break

        time.sleep(0.1)


def remover_workers_sem_resposta(workers_contatados):
    for worker in workers_contatados:
        if worker not in feromonios_recebidos:
            membros.remover(worker)
            print(f"[MEMB] No {worker} removido do grupo: nao respondeu ao sync.")


def sincronizar(iteracao):
    global rodando

    workers = membros.workers()

    if not workers:
        return

    feromonios_recebidos.clear()
    melhores_recebidos.clear()

    workers_contatados = solicitar_feromonios(workers)
    aguardar_feromonios(workers_contatados)
    remover_workers_sem_resposta(workers_contatados)

    workers_ativos = [
        worker
        for worker in workers_contatados
        if worker in membros.workers()
    ]

    matrizes = list(feromonios_recebidos.values()) + [aco.obter_feromonio()]
    media = ACO.consolidar_matrizes(matrizes)

    aco.definir_feromonio(media)

    for worker in workers_ativos:
        enviar(worker, "FEROMONIO", {
            "matriz": media,
        })

    melhor = atualizar_criterio_parada()

    print(
        f"[SYNC] Feromonio sincronizado com {len(workers_ativos)} worker(s). "
        f"melhor={melhor['distancia']:.2f} no={melhor['no_id']} "
        f"sem_melhora={syncs_sem_melhora}/{MAX_SYNCS_SEM_MELHORA}"
    )

    parar, motivo = verificar_parada(iteracao)

    if parar:
        tempo_total = time.perf_counter() - inicio_execucao

        resultado = {
            "motivo": motivo,
            "iteracao": iteracao,
            "melhor_rota": melhor_rota_observada,
            "melhor_distancia": melhor_distancia_observada,
            "matriz_feromonio": media,
            "tempo_total": tempo_total,
            "modo": "benchmark" if MODO_BENCHMARK else "distribuido",
        }

        for worker in workers_ativos:
            enviar(worker, "PARAR", resultado)

        imprimir_resultado_final(resultado)
        rodando = False


rede.iniciar_servidor()
print(f"[INIT] No {MEU_ID} iniciado.")
tentar_entrar_em_grupo()

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

        print(
            f"[ACO] iter {iteracao} | dist {dist:.2f} | "
            f"lider: {lider_atual()} | participantes: {membros.listar() if eu_sou_lider() else '-'}"
        )

        if eu_sou_lider():
            sincronizar(iteracao)

    time.sleep(0.01)

rede.parar()