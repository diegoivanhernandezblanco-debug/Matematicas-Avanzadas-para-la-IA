import random
import time
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import os

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

# =========================
# CONFIGURACIÓN
# =========================
USAR_APRENDIZAJE_PREVIO = True
NOMBRE_ARCHIVO_FIJO = "q_table_aprendizaje_acumulado.xlsx"
NOMBRE_IMAGEN_TRAFICO = "simulacion_trafico_red.png"
NOMBRE_ARCHIVO_ANALISIS_MATEMATICO = "analisis_matematico_red.xlsx"
# En Windows abre automáticamente el reporte al terminar el análisis.
ABRIR_EXCEL_ANALISIS = True
UMBRAL_ANOMALIA_TRAFICO = 65
USAR_ALERTAS_VOZ = True
TASA_APRENDIZAJE = 0.03
NUM_NODOS = 20
NUM_PASOS_SIMULACION = 10
FORMA_Q = (NUM_NODOS + 1, NUM_NODOS)
COLORES_FASE = {
    "propagacion": "#fde68a",
    "aislamiento": "#c7d2fe",
    "recuperacion": "#bbf7d0",
}

# =========================
# SEMILLA
# =========================
seed = random.randint(1, 10000)
random.seed(seed)
np.random.seed(seed)
print(f"Semilla: {seed}")

# Estados
SANO = "SANO"
INFECTADO = "INFECTADO"
AISLADO = "AISLADO"
RECUPERANDOSE = "RECUPERANDOSE"
RECUPERADO = "RECUPERADO"

NODOS_BASE = {
    0: {"nombre": "Centro de Datos Nacional", "criticidad": 10},
    1: {"nombre": "Red Troncal de Gobierno", "criticidad": 9},
    2: {"nombre": "Sistema de Salud", "criticidad": 10},
    3: {"nombre": "Comunicaciones de Emergencia", "criticidad": 10},
    4: {"nombre": "Plataforma de Energia", "criticidad": 9},
    5: {"nombre": "Base de Identidad Ciudadana", "criticidad": 9},
    6: {"nombre": "Sistema de Recaudacion", "criticidad": 7},
    7: {"nombre": "Portal de Tramites", "criticidad": 6},
    8: {"nombre": "Sistema Financiero Publico", "criticidad": 8},
    9: {"nombre": "Respaldo y Monitoreo", "criticidad": 7},
}


def construir_catalogo_nodos(num_nodos):
    catalogo = dict(NODOS_BASE)
    extras = [
        "Centro Regional Norte",
        "Centro Regional Sur",
        "Nodo de Telemetria",
        "Servidor de Respaldos",
        "Hub de Comunicaciones",
        "Motor de Autenticacion",
        "Consola SOC",
        "Repositorio Forense",
        "Pasarela Segura",
        "Sistema Satelite",
    ]

    for nodo in range(len(NODOS_BASE), num_nodos):
        catalogo[nodo] = {
            "nombre": extras[(nodo - len(NODOS_BASE)) % len(extras)],
            "criticidad": max(5, 10 - ((nodo - len(NODOS_BASE)) % 5)),
        }

    return catalogo


def construir_conexiones_red(num_nodos):
    conexiones = set()

    for nodo in range(num_nodos - 1):
        conexiones.add((nodo, nodo + 1))

    for nodo in range(num_nodos - 4):
        conexiones.add((nodo, nodo + 4))

    for nodo in range(0, num_nodos - 2, 3):
        conexiones.add((nodo, nodo + 2))

    return sorted(conexiones)


CATALOGO_NODOS = construir_catalogo_nodos(NUM_NODOS)


class GestorVoz:
    def __init__(self, habilitado=True):
        self.habilitado = habilitado and pyttsx3 is not None
        self.motor = None
        self.disponible = False

        if not self.habilitado:
            if habilitado and pyttsx3 is None:
                print("Alertas de voz deshabilitadas: instala 'pyttsx3' para activar el audio.")
            return

        try:
            self.motor = pyttsx3.init()
            self.motor.setProperty("rate", 165)
            self.motor.setProperty("volume", 1.0)
            self.disponible = True
        except Exception as error:
            print(f"No fue posible inicializar la voz del sistema: {error}")

    def hablar(self, mensaje):
        if not self.disponible:
            return

        try:
            self.motor.say(mensaje)
            self.motor.runAndWait()
        except Exception as error:
            print(f"Fallo al reproducir alerta de voz: {error}")


voz = GestorVoz(USAR_ALERTAS_VOZ)

# =========================
# CLASE RED
# =========================
class Red:
    def __init__(self, num_nodos):
        self.num_nodos = num_nodos
        self.nodos = {i: SANO for i in range(num_nodos)}
        self.conexiones = {i: [] for i in range(num_nodos)}
        self.grafo = nx.Graph()
        self.grafo.add_nodes_from(range(num_nodos))
        self.pos = None
        self.paciente_cero = None
        self.en_recuperacion = False
        self.catalogo_nodos = CATALOGO_NODOS
        self.alertas_emitidas = set()
        self.fases_anunciadas = set()

    def conectar(self, a, b):
        self.conexiones[a].append(b)
        self.conexiones[b].append(a)
        self.grafo.add_edge(a, b)

    def infectar_nodo(self, nodo):
        if self.paciente_cero is None:
            self.paciente_cero = nodo
        self.nodos[nodo] = INFECTADO
        self.anunciar_amenaza(nodo)

    def aislar_nodo(self, nodo):
        if self.nodos[nodo] != AISLADO:
            self.nodos[nodo] = AISLADO
            print(f"Nodo {nodo} AISLADO")
            self.anunciar_aislamiento(nodo)

    def anunciar_amenaza(self, nodo):
        if nodo in self.alertas_emitidas:
            return

        nombre_nodo = self.obtener_nombre_nodo(nodo)
        mensaje = f"Amenaza detectada en {nombre_nodo}"
        print(f"ALERTA DE VOZ: {mensaje}")
        voz.hablar(mensaje)
        self.alertas_emitidas.add(nodo)

    def anunciar_aislamiento(self, nodo):
        nombre_nodo = self.obtener_nombre_nodo(nodo)
        mensaje = f"Nodo aislado para contencion: {nombre_nodo}"
        print(f"ALERTA DE VOZ: {mensaje}")
        voz.hablar(mensaje)

    def anunciar_inicio_recuperacion(self):
        if "recuperacion" in self.fases_anunciadas:
            return

        mensaje = "Iniciando fase de recuperacion de servicios criticos"
        print(f"ALERTA DE VOZ: {mensaje}")
        voz.hablar(mensaje)
        self.fases_anunciadas.add("recuperacion")

    def anunciar_recuperacion_completada(self, nodo):
        nombre_nodo = self.obtener_nombre_nodo(nodo)
        mensaje = f"Servicio recuperado exitosamente: {nombre_nodo}"
        print(f"ALERTA DE VOZ: {mensaje}")
        voz.hablar(mensaje)

    def iniciar_recuperacion(self):
        """Inicia la fase de recuperación de nodos infectados y aislados"""
        infectados = [nodo for nodo, estado in self.nodos.items() if estado == INFECTADO]
        aislados = [nodo for nodo, estado in self.nodos.items() if estado == AISLADO]
        
        if infectados or aislados:
            self.en_recuperacion = True
            print(f"\n{'='*50}")
            print(f"INICIANDO FASE DE RECUPERACIÓN")
            if infectados:
                print(f"Nodos infectados a recuperar: {infectados}")
            if aislados:
                print(f"Nodos aislados a recuperar: {aislados}")
            print(f"{'='*50}")
            self.anunciar_inicio_recuperacion()
            return True
        return False

    def obtener_nombre_nodo(self, nodo):
        return self.catalogo_nodos.get(nodo, {}).get("nombre", f"Nodo {nodo}")

    def obtener_criticidad_nodo(self, nodo):
        return self.catalogo_nodos.get(nodo, {}).get("criticidad", 1)

    def calcular_prioridad_recuperacion(self, nodo):
        """Calcula la prioridad de recuperación según riesgo e impacto"""
        estado = self.nodos[nodo]
        vecinos = self.conexiones[nodo]
        vecinos_sanos = sum(1 for vecino in vecinos if self.nodos[vecino] == SANO)
        vecinos_infectados = sum(1 for vecino in vecinos if self.nodos[vecino] == INFECTADO)
        grado = len(vecinos)
        criticidad = self.obtener_criticidad_nodo(nodo)
        nombre = self.obtener_nombre_nodo(nodo)

        # Prioridad base:
        # 1. Infectados primero porque siguen siendo amenaza activa.
        # 2. Luego aislados, priorizando los que conectan más con la red.
        prioridad_base = 100 if estado == INFECTADO else 50

        # La decisión mezcla importancia operativa del activo con riesgo técnico.
        puntaje = (
            prioridad_base
            + criticidad * 12
            + vecinos_sanos * 10
            + vecinos_infectados * 4
            + grado * 3
        )

        return {
            "nodo": nodo,
            "nombre": nombre,
            "estado": estado,
            "criticidad": criticidad,
            "vecinos_sanos": vecinos_sanos,
            "vecinos_infectados": vecinos_infectados,
            "grado": grado,
            "puntaje": puntaje,
        }

    def obtener_plan_recuperacion(self):
        """Genera un orden inteligente de recuperación"""
        candidatos = [
            self.calcular_prioridad_recuperacion(nodo)
            for nodo, estado in self.nodos.items()
            if estado in (INFECTADO, AISLADO)
        ]

        candidatos.sort(
            key=lambda info: (
                info["puntaje"],
                info["criticidad"],
                info["vecinos_sanos"],
                info["grado"]
            ),
            reverse=True
        )
        return candidatos

    def recuperar_siguiente_nodo(self, nodo):
        """Convierte un nodo infectado o aislado en recuperándose"""
        if self.nodos[nodo] in (INFECTADO, AISLADO):
            self.nodos[nodo] = RECUPERANDOSE
            print(f"Nodo {nodo} en proceso de recuperación")
            return nodo
        return None
    
    def finalizar_recuperacion_nodo(self, nodo):
        """Convierte un nodo en recuperación a recuperado"""
        if self.nodos[nodo] == RECUPERANDOSE:
            self.nodos[nodo] = RECUPERADO
            print(f"Nodo {nodo} completamente recuperado")
            self.anunciar_recuperacion_completada(nodo)
            return nodo
        return None

    def contar_infectados(self):
        return sum(1 for e in self.nodos.values() if e == INFECTADO)
    
    def contar_aislados(self):
        return sum(1 for e in self.nodos.values() if e == AISLADO)
    
    def contar_recuperandose(self):
        return sum(1 for e in self.nodos.values() if e == RECUPERANDOSE)
    
    def contar_recuperados(self):
        return sum(1 for e in self.nodos.values() if e == RECUPERADO)
    
    def obtener_infectados(self):
        return [nodo for nodo, estado in self.nodos.items() if estado == INFECTADO]
    
    def obtener_aislados(self):
        return [nodo for nodo, estado in self.nodos.items() if estado == AISLADO]
    
    def obtener_recuperados(self):
        return [nodo for nodo, estado in self.nodos.items() if estado == RECUPERADO]

    def propagar(self, probabilidad=0.3):
        nuevos = []
        for nodo, estado in self.nodos.items():
            if estado == INFECTADO:
                for vecino in self.conexiones[nodo]:
                    if self.nodos[vecino] == SANO:
                        if random.random() < probabilidad:
                            nuevos.append(vecino)
        for n in nuevos:
            self.nodos[n] = INFECTADO
            self.anunciar_amenaza(n)

    def visualizar(self, paso, fase="propagacion", historial_trafico=None):
        plt.clf()
        figura = plt.gcf()
        figura.set_size_inches(18, 8)
        ax_red = figura.add_subplot(1, 2, 1)
        ax_trafico = figura.add_subplot(1, 2, 2)
        colores = []
        node_size = 1100 if self.num_nodos <= 10 else 700
        font_size = 8 if self.num_nodos <= 10 else 6

        for nodo in self.grafo.nodes():
            if self.nodos[nodo] == SANO:
                colores.append("green")
            elif self.nodos[nodo] == INFECTADO:
                colores.append("red")
            elif self.nodos[nodo] == AISLADO:
                colores.append("gray")
            elif self.nodos[nodo] == RECUPERANDOSE:
                colores.append("orange")  # Naranja para recuperándose
            else:  # RECUPERADO
                colores.append("blue")    # Azul para recuperados

        labels = {}
        for n in self.grafo.nodes():
            marca_paciente_cero = "\nPACIENTE CERO" if n == self.paciente_cero else ""
            if self.num_nodos <= 10:
                labels[n] = (
                    f"{n}\n{self.obtener_nombre_nodo(n)}\n{self.nodos[n]}"
                    f"{marca_paciente_cero}"
                )
            else:
                labels[n] = f"{n}\n{self.nodos[n]}{marca_paciente_cero}"
        
        # Título según la fase
        if fase == "propagacion":
            titulo = f"FASE DE PROPAGACIÓN - Paso {paso}"
        elif fase == "aislamiento":
            titulo = f"FASE DE AISLAMIENTO - Paso {paso}"
        elif fase == "recuperacion":
            titulo = f"FASE DE RECUPERACIÓN - Paso {paso}"
        else:
            titulo = f"Simulación - Paso {paso}"
        
        figura.suptitle(
            f"{titulo} | Semilla {seed}\n"
            f"Paciente cero: Nodo {self.paciente_cero} - {self.obtener_nombre_nodo(self.paciente_cero)}\n"
            f"Infectados: {self.contar_infectados()} | Aislados: {self.contar_aislados()} | "
            f"Recuperándose: {self.contar_recuperandose()} | Recuperados: {self.contar_recuperados()}",
            fontsize=16
        )

        nx.draw(
            self.grafo,
            self.pos,
            labels=labels,
            node_color=colores,
            node_size=node_size,
            font_size=font_size,
            ax=ax_red
        )
        ax_red.set_title(f"{titulo}\nPaciente cero: Nodo {self.paciente_cero}", fontsize=14)

        if historial_trafico:
            pasos = [p["paso"] for p in historial_trafico]
            trafico_legitimo = [p["trafico_legitimo"] for p in historial_trafico]
            trafico_malicioso = [p["trafico_malicioso"] for p in historial_trafico]
            capacidad = [p["capacidad"] for p in historial_trafico]
            umbral_anomalia = [p["umbral_anomalia"] for p in historial_trafico]
            pasos_anomalos = [p["paso"] for p in historial_trafico if p["anomalia_detectada"]]
            trafico_anomalo = [p["trafico_malicioso"] for p in historial_trafico if p["anomalia_detectada"]]
            linea_atipicos = [
                p["trafico_malicioso"] if p["anomalia_detectada"] else np.nan
                for p in historial_trafico
            ]
            transiciones_fase = []

            for indice, punto in enumerate(historial_trafico):
                if indice == 0 or punto["fase"] != historial_trafico[indice - 1]["fase"]:
                    transiciones_fase.append((punto["paso"], punto["fase"]))

            ax_trafico.plot(
                pasos, trafico_legitimo,
                color="tab:blue", linewidth=2, marker="o",
                label="Trafico legitimo"
            )
            ax_trafico.plot(
                pasos, trafico_malicioso,
                color="tab:red", linewidth=3, marker="x",
                label="Trafico malicioso"
            )
            ax_trafico.plot(
                pasos, capacidad,
                color="tab:green", linewidth=2, linestyle="--",
                label="Capacidad disponible"
            )
            ax_trafico.plot(
                pasos, umbral_anomalia,
                color="darkorange", linewidth=2, linestyle=":",
                label="Umbral de anomalia"
            )

            ax_trafico.fill_between(pasos, trafico_malicioso, color="tab:red", alpha=0.12)
            ax_trafico.fill_between(pasos, trafico_legitimo, color="tab:blue", alpha=0.08)
            ax_trafico.fill_between(
                pasos,
                trafico_malicioso,
                umbral_anomalia,
                where=np.array(trafico_malicioso) > np.array(umbral_anomalia),
                color="crimson",
                alpha=0.22,
                interpolate=True,
                label="Fuera de rango"
            )
            ax_trafico.plot(
                pasos,
                linea_atipicos,
                color="crimson",
                linewidth=2.5,
                linestyle="-.",
                marker="o",
                markersize=6,
                zorder=4,
                label="Linea de valores atipicos"
            )

            for indice, (inicio, fase_actual) in enumerate(transiciones_fase):
                fin = pasos[-1]
                if indice + 1 < len(transiciones_fase):
                    fin = transiciones_fase[indice + 1][0]

                ax_trafico.axvspan(
                    inicio,
                    fin,
                    color=COLORES_FASE.get(fase_actual, "#e5e7eb"),
                    alpha=0.12
                )
                ax_trafico.text(
                    inicio + (fin - inicio) / 2 if fin > inicio else inicio,
                    max(capacidad) + 6,
                    fase_actual.upper(),
                    ha="center",
                    va="bottom",
                    fontsize=9,
                    color="#374151",
                    fontweight="bold"
                )

            if pasos_anomalos:
                ax_trafico.scatter(
                    pasos_anomalos,
                    trafico_anomalo,
                    color="crimson",
                    s=90,
                    zorder=5,
                    label="Picos anomalos"
                )
                for paso_anomalo, valor_anomalo in zip(pasos_anomalos, trafico_anomalo):
                    ax_trafico.annotate(
                        "Anomalia",
                        xy=(paso_anomalo, valor_anomalo),
                        xytext=(paso_anomalo + 0.15, valor_anomalo + 8),
                        fontsize=9,
                        color="crimson",
                        arrowprops=dict(arrowstyle="->", color="crimson", lw=1.5)
                    )

            ultimo = historial_trafico[-1]
            resumen_trafico = (
                f"Actual\n"
                f"Legitimo: {ultimo['trafico_legitimo']:.0f} Mbps\n"
                f"Malicioso: {ultimo['trafico_malicioso']:.0f} Mbps\n"
                f"Capacidad: {ultimo['capacidad']:.0f} Mbps\n"
                f"Anomalias: {sum(1 for p in historial_trafico if p['anomalia_detectada'])}"
            )
            ax_trafico.text(
                0.02,
                0.98,
                resumen_trafico,
                transform=ax_trafico.transAxes,
                va="top",
                ha="left",
                fontsize=10,
                bbox=dict(boxstyle="round,pad=0.4", facecolor="white", alpha=0.9, edgecolor="#9ca3af")
            )

            ax_trafico.set_title("Trafico de Red", fontsize=14)
            ax_trafico.set_xlabel("Paso de simulacion")
            ax_trafico.set_ylabel("Mbps simulados")
            ax_trafico.grid(True, alpha=0.3)
            ax_trafico.legend(loc="upper right")
            ax_trafico.set_xlim(left=0)
            ax_trafico.set_ylim(bottom=0, top=max(max(capacidad), max(trafico_malicioso), max(trafico_legitimo)) + 18)

        figura.tight_layout(rect=[0, 0, 1, 0.9])
        plt.pause(0.5)


def registrar_trafico_simulado(red, historial_trafico, paso, fase):
    infectados = red.contar_infectados()
    aislados = red.contar_aislados()
    recuperandose = red.contar_recuperandose()
    recuperados = red.contar_recuperados()

    trafico_legitimo = max(
        20,
        120
        - infectados * 12
        - aislados * 8
        - recuperandose * 5
        + recuperados * 6
        + random.randint(-5, 5)
    )

    pico_anomalia = 0
    if infectados > 0 and fase in ("propagacion", "aislamiento"):
        pico_anomalia = infectados * random.randint(20, 35)
    elif recuperandose > 0:
        pico_anomalia = random.randint(0, 3)

    trafico_malicioso = max(
        0,
        infectados * 18
        + max(0, infectados - recuperados) * 4
        + pico_anomalia
        + random.randint(0, 6)
    )

    capacidad = max(
        15,
        140
        - aislados * 10
        - infectados * 14
        - recuperandose * 4
        + recuperados * 5
    )

    umbral_anomalia = min(UMBRAL_ANOMALIA_TRAFICO, capacidad * 0.8)
    anomalia_detectada = trafico_malicioso > umbral_anomalia

    historial_trafico.append({
        "paso": paso,
        "fase": fase,
        "trafico_legitimo": trafico_legitimo,
        "trafico_malicioso": trafico_malicioso,
        "capacidad": capacidad,
        "umbral_anomalia": umbral_anomalia,
        "anomalia_detectada": anomalia_detectada,
    })

    if anomalia_detectada:
        print(
            f"Anomalia detectada en el paso {paso}: "
            f"trafico malicioso = {trafico_malicioso:.1f} Mbps, "
            f"umbral = {umbral_anomalia:.1f} Mbps"
        )


def imprimir_resumen_trafico(historial_trafico):
    if not historial_trafico:
        return

    total_anomalias = sum(1 for punto in historial_trafico if punto["anomalia_detectada"])
    pico_malicioso = max(historial_trafico, key=lambda punto: punto["trafico_malicioso"])
    mejor_capacidad = max(historial_trafico, key=lambda punto: punto["capacidad"])
    promedio_legitimo = np.mean([punto["trafico_legitimo"] for punto in historial_trafico])
    promedio_malicioso = np.mean([punto["trafico_malicioso"] for punto in historial_trafico])

    print("\n" + "="*50)
    print("RESUMEN DEL TRAFICO DE RED SIMULADO")
    print("="*50)
    print(f"Lecturas registradas: {len(historial_trafico)}")
    print(f"Promedio de trafico legitimo: {promedio_legitimo:.1f} Mbps")
    print(f"Promedio de trafico malicioso: {promedio_malicioso:.1f} Mbps")
    print(
        f"Pico de trafico malicioso: {pico_malicioso['trafico_malicioso']:.1f} Mbps "
        f"(paso {pico_malicioso['paso']}, fase {pico_malicioso['fase']})"
    )
    print(
        f"Mayor capacidad disponible: {mejor_capacidad['capacidad']:.1f} Mbps "
        f"(paso {mejor_capacidad['paso']}, fase {mejor_capacidad['fase']})"
    )
    print(f"Eventos de anomalia detectados: {total_anomalias}")

# =========================
# ACCIONES ESTRATÉGICAS
# =========================
def acciones_validas(red):
    acciones = []

    # nodos infectados
    for nodo in range(red.num_nodos):
        if red.nodos[nodo] == INFECTADO:
            acciones.append(nodo)

    # vecinos de infectados
    for nodo in range(red.num_nodos):
        if red.nodos[nodo] == SANO:
            for vecino in red.conexiones[nodo]:
                if red.nodos[vecino] == INFECTADO:
                    acciones.append(nodo)
                    break

    acciones = list(set(acciones))

    if not acciones:
        acciones = [i for i in range(red.num_nodos) if red.nodos[i] != AISLADO]

    return acciones

# =========================
# Q-LEARNING
# =========================
def elegir_accion(estado, red):
    validas = acciones_validas(red)

    if random.random() < epsilon:
        accion = random.choice(validas)
        print(f"Exploración: nodo {accion}")
        return accion

    mejor = max(validas, key=lambda a: Q[estado][a])
    print(f"Explotación: nodo {mejor} (valor: {Q[estado][mejor]:.2f})")
    return mejor

def actualizar_Q(estado, accion, reward, siguiente_estado):
    Q[estado][accion] += alpha * (
        reward + gamma * np.max(Q[siguiente_estado]) - Q[estado][accion]
    )

# =========================
# CARGA ROBUSTA Q-TABLE
# =========================
def cargar_q_table_acumulativo(filename=NOMBRE_ARCHIVO_FIJO):
    if not os.path.exists(filename):
        print("No existe archivo, creando nuevo")
        return np.zeros(FORMA_Q), 0

    try:
        df_q = pd.read_excel(filename, sheet_name='Q_Table', index_col=0)
    except Exception:
        print("No existe hoja Q_Table, creando nueva")
        return np.zeros(FORMA_Q), 0

    q_cargada = df_q.values
    q_ajustada = np.zeros(FORMA_Q)
    filas = min(q_cargada.shape[0], FORMA_Q[0])
    columnas = min(q_cargada.shape[1], FORMA_Q[1])
    q_ajustada[:filas, :columnas] = q_cargada[:filas, :columnas]
    print("Q-table cargada correctamente")
    return q_ajustada, 0

# =========================
# GUARDAR Q-TABLE
# =========================
def guardar_q_table(Q, recuperados=None):
    df_q = pd.DataFrame(Q)
    
    with pd.ExcelWriter(NOMBRE_ARCHIVO_FIJO, engine='openpyxl') as writer:
        df_q.to_excel(writer, sheet_name='Q_Table')
        
        # Guardar información de recuperados si existe
        if recuperados:
            df_recup = pd.DataFrame({
                'Nodos_Recuperados': [str(recuperados)],
                'Cantidad': [len(recuperados)]
            })
            df_recup.to_excel(writer, sheet_name='Recuperados', index=False)
    
    print("Q-table guardada correctamente")

# =========================
# MATEMÁTICAS AVANZADAS PARA IA
# =========================
# Este bloque NO cambia la simulación, la Q-table, la recompensa ni la acción
# elegida. Se ejecuta al finalizar para estudiar matemáticamente la red que
# acaba de simularse y dejar evidencia para la materia.
#
# 1) Matriz de adyacencia A:
#       A[i,j] = 1 si el nodo i se conecta con j; A[i,j] = 0 si no.
#    Es la representación matricial del grafo de la red.
#
# 2) Matriz de grados D y laplaciano L:
#       D[i,i] = número de conexiones del nodo i
#       L = D - A
#    Los autovalores de L describen la estructura de la red. El segundo
#    autovalor menor, lambda_2, es la conectividad algebraica: si es alto,
#    hay más rutas alternativas entre servicios; si es bajo, pocos cortes
#    pueden separar zonas de la red.
#
# 3) Centralidades:
#    - grado: cuántas conexiones directas tiene un nodo;
#    - intermediación: cuántos caminos cortos pasan por él (nodo puente);
#    - vector propio: importancia de estar conectado con nodos importantes,
#      obtenida a partir de A*v = lambda*v.
#
# 4) Índice de riesgo:
#       R_i = 0.35*C_grado + 0.35*C_intermediacion
#             + 0.20*C_vector_propio + 0.10*(criticidad/10)
#    Sirve para comparar el valor estratégico de cada activo con los nodos
#    aislados por Q-Learning. Es análisis posterior, no una regla nueva.
def guardar_analisis_matematico_red(red):
    """Analiza la topología sin cambiar la simulación ni las decisiones del agente.

    A es la matriz de adyacencia, L = D - A es el laplaciano del grafo.
    El segundo autovalor de L (conectividad algebraica) indica qué tan
    robusta es la comunicación de la red ante cortes o aislamientos.
    """
    nodos = list(red.grafo.nodes())
    matriz_adyacencia = nx.to_numpy_array(red.grafo, nodelist=nodos, dtype=int)
    matriz_grados = np.diag(matriz_adyacencia.sum(axis=1))
    laplaciano = matriz_grados - matriz_adyacencia
    autovalores = np.linalg.eigvalsh(laplaciano)
    conectividad_algebraica = autovalores[1] if len(autovalores) > 1 else 0

    centralidad_grado = nx.degree_centrality(red.grafo)
    centralidad_intermediacion = nx.betweenness_centrality(red.grafo, normalized=True)
    centralidad_vector_propio = nx.eigenvector_centrality_numpy(red.grafo)

    filas = []
    for nodo in nodos:
        criticidad = red.obtener_criticidad_nodo(nodo)
        # Índice ponderado: estructura de la red + importancia operativa.
        indice_riesgo = (
            0.35 * centralidad_grado[nodo]
            + 0.35 * centralidad_intermediacion[nodo]
            + 0.20 * centralidad_vector_propio[nodo]
            + 0.10 * (criticidad / 10)
        )
        filas.append({
            "Nodo": nodo,
            "Activo": red.obtener_nombre_nodo(nodo),
            "Criticidad (1-10)": criticidad,
            "Grado": red.grafo.degree[nodo],
            "Centralidad de grado": centralidad_grado[nodo],
            "Centralidad de intermediacion": centralidad_intermediacion[nodo],
            "Centralidad de vector propio": centralidad_vector_propio[nodo],
            "Indice matematico de riesgo": indice_riesgo,
        })

    df_riesgo = pd.DataFrame(filas).sort_values("Indice matematico de riesgo", ascending=False)
    df_adyacencia = pd.DataFrame(matriz_adyacencia, index=nodos, columns=nodos)
    df_laplaciano = pd.DataFrame(laplaciano, index=nodos, columns=nodos)
    df_espectro = pd.DataFrame({"Autovalores del laplaciano": autovalores})
    df_resumen = pd.DataFrame([{
        "Formula laplaciano": "L = D - A",
        "Conectividad algebraica (lambda_2)": conectividad_algebraica,
        "Interpretacion": "Mayor lambda_2 implica una red más conectada y robusta",
    }])

    with pd.ExcelWriter(NOMBRE_ARCHIVO_ANALISIS_MATEMATICO, engine="openpyxl") as writer:
        df_riesgo.to_excel(writer, sheet_name="Riesgo_y_centralidad", index=False)
        df_adyacencia.to_excel(writer, sheet_name="Matriz_adyacencia")
        df_laplaciano.to_excel(writer, sheet_name="Laplaciano_L")
        df_espectro.to_excel(writer, sheet_name="Autovalores_L", index=False)
        df_resumen.to_excel(writer, sheet_name="Resumen", index=False)

    print("\nANALISIS MATEMATICO DE LA RED")
    print(f"Conectividad algebraica (lambda_2): {conectividad_algebraica:.4f}")
    print("Tres nodos con mayor indice matematico de riesgo:")
    for _, fila in df_riesgo.head(3).iterrows():
        print(f"  Nodo {int(fila['Nodo'])}: {fila['Activo']} | Riesgo {fila['Indice matematico de riesgo']:.4f}")
    print(f"Analisis guardado en: {NOMBRE_ARCHIVO_ANALISIS_MATEMATICO}")

    # os.startfile usa la aplicación predeterminada de Windows para .xlsx;
    # normalmente será Microsoft Excel. Se llama sólo después de cerrar el
    # archivo con ExcelWriter, para que Excel pueda abrirlo sin conflictos.
    if ABRIR_EXCEL_ANALISIS:
        try:
            os.startfile(os.path.abspath(NOMBRE_ARCHIVO_ANALISIS_MATEMATICO))
            print("Abriendo el archivo de análisis matemático en Excel...")
        except OSError as error:
            print(f"No fue posible abrir Excel automáticamente: {error}")

# =========================
# CONFIGURACIÓN Q-LEARNING
# =========================
if USAR_APRENDIZAJE_PREVIO:
    Q, _ = cargar_q_table_acumulativo()
else:
    Q = np.zeros(FORMA_Q)

alpha = TASA_APRENDIZAJE
gamma = 0.9
epsilon = 0.3

# =========================
# CREAR RED
# =========================
red = Red(NUM_NODOS)

conexiones = construir_conexiones_red(NUM_NODOS)

for a, b in conexiones:
    red.conectar(a, b)

red.pos = nx.spring_layout(red.grafo, seed=seed)

print("\nCATALOGO DE ACTIVOS CRITICOS:")
for nodo, info in CATALOGO_NODOS.items():
    print(f" Nodo {nodo}: {info['nombre']} | Criticidad: {info['criticidad']}/10")

PACIENTE_CERO = random.randint(0, NUM_NODOS - 1)
red.infectar_nodo(PACIENTE_CERO)

print(f"Paciente cero: {PACIENTE_CERO}")
print(f"Sistema afectado inicialmente: {red.obtener_nombre_nodo(PACIENTE_CERO)}")

# =========================
# SIMULACIÓN - FASE 1: PROPAGACIÓN Y AISLAMIENTO
# =========================
print("\n" + "="*50)
print("FASE 1: PROPAGACIÓN Y AISLAMIENTO")
print("="*50)

plt.ion()
plt.figure(figsize=(18, 8))

# Registrar historial de recuperados
recuperados_totales = []
historial_trafico = []

for paso in range(NUM_PASOS_SIMULACION):
    print(f"\n--- Paso {paso} ---")

    registrar_trafico_simulado(red, historial_trafico, paso, "propagacion")
    red.visualizar(paso, fase="propagacion", historial_trafico=historial_trafico)

    estado = red.contar_infectados()

    if estado == 0:
        print("Sin infección activa")
        accion = None
    else:
        accion = elegir_accion(estado, red)

    if accion is not None:
        red.aislar_nodo(accion)
        registrar_trafico_simulado(red, historial_trafico, paso + 0.1, "aislamiento")
        red.visualizar(paso, fase="aislamiento", historial_trafico=historial_trafico)

    antes = red.contar_infectados()
    red.propagar(0.4)
    despues = red.contar_infectados()

    reward = -(despues - antes)

    if accion is not None:
        if red.nodos[accion] == INFECTADO:
            reward += 3
        elif red.nodos[accion] == SANO:
            reward -= 1

    reward -= 0.7 * red.contar_aislados()

    if despues == antes:
        reward += 2

    print(f"Recompensa: {reward}")

    if accion is not None:
        actualizar_Q(estado, accion, reward, despues)

    time.sleep(1)

# =========================
# FASE 2: RECUPERACIÓN DE NODOS INFECTADOS Y AISLADOS
# =========================
print("\n" + "="*50)
print("FASE 2: RECUPERACIÓN DE NODOS INFECTADOS Y AISLADOS")
print("="*50)

# Mostrar estado antes de la recuperación
infectados_finales = red.obtener_infectados()
aislados_finales = red.obtener_aislados()

print(f"Nodos infectados al final de la propagación: {infectados_finales}")
print(f"Nodos aislados al final de la propagación: {aislados_finales}")
print(f"Total de nodos a recuperar: {len(infectados_finales) + len(aislados_finales)}")

if infectados_finales or aislados_finales:
    # Iniciar recuperación
    red.iniciar_recuperacion()
    registrar_trafico_simulado(red, historial_trafico, NUM_PASOS_SIMULACION, "recuperacion")
    red.visualizar(0, fase="recuperacion", historial_trafico=historial_trafico)
    time.sleep(2)

    recuperados = []
    plan_recuperacion = red.obtener_plan_recuperacion()

    print("\nPRIORIDAD DE RECUPERACIÓN INTELIGENTE:")
    for posicion, info in enumerate(plan_recuperacion, start=1):
        print(
            f" {posicion}. Nodo {info['nodo']} - {info['nombre']} | "
            f"Estado: {info['estado']} | "
            f"Criticidad: {info['criticidad']}/10 | "
            f"Vecinos sanos: {info['vecinos_sanos']} | "
            f"Vecinos infectados: {info['vecinos_infectados']} | "
            f"Conexiones: {info['grado']} | Puntaje: {info['puntaje']}"
        )

    for indice, info in enumerate(plan_recuperacion, start=1):
        nodo = info["nodo"]
        print(
            f"\nRecuperación progresiva {indice}/{len(plan_recuperacion)}: "
            f"nodo {nodo} - {info['nombre']} con prioridad {info['puntaje']}"
        )
        red.recuperar_siguiente_nodo(nodo)
        registrar_trafico_simulado(
            red,
            historial_trafico,
            NUM_PASOS_SIMULACION + indice,
            "recuperacion"
        )
        red.visualizar(indice, fase="recuperacion", historial_trafico=historial_trafico)
        time.sleep(1.5)

        red.finalizar_recuperacion_nodo(nodo)
        recuperados.append(nodo)
        registrar_trafico_simulado(
            red,
            historial_trafico,
            NUM_PASOS_SIMULACION + indice + len(plan_recuperacion),
            "recuperacion"
        )
        red.visualizar(
            indice + len(plan_recuperacion),
            fase="recuperacion",
            historial_trafico=historial_trafico
        )
        time.sleep(1.5)

    red.en_recuperacion = False
    
    # Guardar en variable global
    recuperados_totales = recuperados
    
    # Mostrar resumen final de recuperación
    print("\n" + "="*50)
    print("RESUMEN DE RECUPERACIÓN")
    print("="*50)
    print(f"Nodos que estaban infectados: {infectados_finales}")
    print(f"Nodos que estaban aislados: {aislados_finales}")
    print(f"Nodos recuperados exitosamente: {recuperados}")
    print(f"Tasa de recuperación: {len(recuperados)}/{len(infectados_finales) + len(aislados_finales)} = {(len(recuperados)/(len(infectados_finales) + len(aislados_finales)))*100:.1f}%")
    
    # Mostrar estado final de todos los nodos
    print("\nESTADO FINAL DE LOS NODOS:")
    for nodo in range(NUM_NODOS):
        print(f"   Nodo {nodo}: {red.nodos[nodo]}")
    
    # Contar cuántos de cada tipo
    print("\nESTADÍSTICAS FINALES:")
    print(f"   Nodos Sanos: {sum(1 for e in red.nodos.values() if e == SANO)}")
    print(f"   Nodos Infectados: {red.contar_infectados()}")
    print(f"   Nodos Aislados: {red.contar_aislados()}")
    print(f"   Nodos Recuperados: {red.contar_recuperados()}")
    
else:
    print("No hay nodos infectados ni aislados para recuperar")

# Se ejecuta antes de plt.show(), porque plt.show() espera a que el usuario
# cierre la ventana de la gráfica. Así el análisis matemático se imprime y se
# guarda automáticamente al terminar la recuperación.
guardar_analisis_matematico_red(red)

plt.ioff()
plt.savefig(NOMBRE_IMAGEN_TRAFICO, dpi=300, bbox_inches="tight")
plt.show()

# =========================
# GUARDAR RESULTADOS
# =========================
print("\n" + "="*50)
print("GUARDANDO RESULTADOS")
print("="*50)

guardar_q_table(Q, recuperados_totales)
print(f"Grafica guardada en: {NOMBRE_IMAGEN_TRAFICO}")
imprimir_resumen_trafico(historial_trafico)

# Mostrar resumen final
print("\n" + "="*50)
print("RESUMEN FINAL DE LA SIMULACIÓN")
print("="*50)
print(f"Semilla: {seed}")
print(f"Paciente cero: {PACIENTE_CERO}")
print(f"Sistema inicial comprometido: {red.obtener_nombre_nodo(PACIENTE_CERO)}")
print(f"Nodos aislados durante la simulación: {len(aislados_finales)}")
print(f"Nodos recuperados: {len(recuperados_totales)}")
print(f"Nodos recuperados (lista): {recuperados_totales}")
print(f"Nodos que quedaron infectados: {red.contar_infectados()}")
print(f"Nodos en estado SANO: {sum(1 for e in red.nodos.values() if e == SANO)}")
print(f"Nodos en estado RECUPERADO: {red.contar_recuperados()}")
print(f"Nodos en estado AISLADO: {red.contar_aislados()}")

print("\n" + "="*50)
print("SIMULACIÓN COMPLETADA EXITOSAMENTE")
print("="*50)
