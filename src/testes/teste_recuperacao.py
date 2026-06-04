import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aco import ACO
from coordenacao import RelogioLamport
from data.instancia import obter_matriz_distancias
from rede import Rede


NOS = {
    1: ("localhost", 5601),
    2: ("localhost", 5602),
}


def montar_mensagem(tipo, remetente_id, relogio, conteudo=None):
    if conteudo is None:
        conteudo = {}

    return {
        "tipo": tipo,
        "remetente_id": remetente_id,
        "timestamp_lamport": relogio.antes_de_enviar(),
        "conteudo": conteudo,
    }


def aguardar_mensagem(rede, tipo_esperado, timeout=3.0):
    prazo = time.time() + timeout

    while time.time() < prazo:
        msg = rede.receber_proxima()

        if msg and msg["tipo"] == tipo_esperado:
            return msg

        time.sleep(0.05)

    raise AssertionError(f"Mensagem {tipo_esperado} nao recebida no prazo.")


def matrizes_iguais(matriz_a, matriz_b, tolerancia=1e-9):
    for i in range(len(matriz_a)):
        for j in range(len(matriz_a)):
            if abs(matriz_a[i][j] - matriz_b[i][j]) > tolerancia:
                return False

    return True


def executar_aco_com_seed(seed):
    random.seed(seed)

    aco = ACO(obter_matriz_distancias())

    for _ in range(20):
        aco.executar_iteracao(num_formigas=5)

    return aco


def testar_recuperacao_de_estado():
    print("\n=== TESTE RECUPERACAO DE ESTADO ===\n")

    lider_rede = Rede(2, NOS[2][1], NOS)
    worker_rede = Rede(1, NOS[1][1], NOS)

    lider_relogio = RelogioLamport()
    worker_relogio = RelogioLamport()

    lider_aco = executar_aco_com_seed(2)
    worker_aco = executar_aco_com_seed(1)

    lider_rede.iniciar_servidor()
    worker_rede.iniciar_servidor()

    try:
        matriz_lider_antes = lider_aco.obter_feromonio()
        matriz_worker = worker_aco.obter_feromonio()
        matriz_esperada = ACO.consolidar_matrizes([
            matriz_lider_antes,
            matriz_worker,
        ])

        solicitacao = montar_mensagem(
            "RECUPERACAO_SOLICITACAO",
            2,
            lider_relogio,
        )

        assert lider_rede.enviar_mensagem(1, solicitacao), (
            "Lider deveria conseguir solicitar estado ao worker."
        )

        msg_solicitacao = aguardar_mensagem(worker_rede, "RECUPERACAO_SOLICITACAO")
        worker_relogio.ao_receber(msg_solicitacao["timestamp_lamport"])

        resposta = montar_mensagem(
            "RECUPERACAO_ESTADO",
            1,
            worker_relogio,
            worker_aco.exportar_estado(),
        )

        assert worker_rede.enviar_mensagem(2, resposta), (
            "Worker deveria conseguir responder com seu estado local."
        )

        msg_resposta = aguardar_mensagem(lider_rede, "RECUPERACAO_ESTADO")
        lider_relogio.ao_receber(msg_resposta["timestamp_lamport"])

        matriz_recebida = msg_resposta["conteudo"]["matriz"]
        matriz_recuperada = ACO.consolidar_matrizes([
            lider_aco.obter_feromonio(),
            matriz_recebida,
        ])

        lider_aco.substituir_feromonio(matriz_recuperada)

        assert matrizes_iguais(lider_aco.obter_feromonio(), matriz_esperada), (
            "A matriz do novo lider deve ser exatamente a media consolidada."
        )

        print("Recuperacao validada: solicitacao, resposta, media e substituicao OK.")

    finally:
        lider_rede.parar()
        worker_rede.parar()


if __name__ == "__main__":
    testar_recuperacao_de_estado()
