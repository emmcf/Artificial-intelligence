"""
ROBOT RECOLECTOR DE BASURA - VERSIÓN 1
 
Agente inteligente con ciclo  PERCEPCIÓN -> DECISIÓN -> ACCIÓN  y una máquina
de estados basada en el diagrama de transiciones del enunciado de la actividad.
 
  * El robot NO conoce la ubicación de la basura: solo la detecta si pasa a
    menos de RADIO_DETECCION píxeles de ella.
  * Sí conoce la ubicación de la estación de carga y de la caja.
  * Moverse, recoger y depositar consumen batería (según el peso).
  * Si la batería baja de UMBRAL_BATERIA, va a recargar.
  * Al terminar la basura, vaga al azar hasta que la batería se agota.
 
Controles: ESPACIO pausa | + / - velocidad | R reiniciar | ESC salir

October 1th 2026
I.S.C. Emmanuel Cisneros Flores
"""
import math
import random
import sys
from collections import deque, namedtuple
from enum import Enum, unique, auto
 
import pygame
from pygame.math import Vector2 as V2
 
# CONFIGURACIÓN variables ajustables

ANCHO, ALTO = 1120, 700
FPS = 60
HAB = pygame.Rect(20, 20, 800, 660) # la habitación
 
CAPACIDAD_BATERIA = 1000
UMBRAL_BATERIA = 350                # si está por debajo de 350, ir a cargar
TASA_RECARGA = 5.0                  # energía recuperada por paso
 
N_BASURA = (10, 15)                 # mínimo y máximo de objetos
PESOS = range(1, 16)                # pesos posibles de cada objeto (1 a 16)
 
VELOCIDAD = 3.0                     # píxeles por paso
RADIO_DETECCION = 95                # visión del robot para detectar objetos
ALCANCE_RECOGER = 20                # distancia para tomar un objeto
ALCANCE_CAJA = 80                   # distancia al centro de la caja
ALCANCE_ESTACION = 8
 
COSTO_MOVER = 0.20                  # energía por píxel sin carga
COSTO_CARGA = 0.02                  # extra por píxel y por unidad de peso
COSTO_RECOGER = 5.0                 # energía por unidad de peso
COSTO_DEPOSITAR = 2.0               # energía por unidad de peso
 
DUR_RECOGER = 45                    # pasos que dura cada animación
DUR_DEPOSITAR = 45
DUR_REVISAR = 30

 
# ENUMERADOS

@unique
class Estado(Enum):
    """Estados de la máquina de estados. Cada uno lleva (número, etiqueta, color)."""
    BUSQUEDA       = (1, "Búsqueda",       (52, 152, 219))  #Azul
    NUEVA_BUSQUEDA = (2, "Nueva búsqueda", (155, 89, 182))  #Morado
    IR_A_BATERIA   = (3, "Ir a batería",   (230, 126, 34))  #Naranja
    RECARGAR       = (4, "Recargar",       (39, 174, 96))   #Verde
    MUERTO         = (5, "Muerto",         (127, 140, 141)) #Gris
    ALEATORIO      = (6, "Aleatorio",      (241, 196, 15))  #Amarillo
    LLEVAR_A_CAJA  = (7, "Llevar a caja",  (26, 188, 156))  #Turqueza
 
    def __init__(self, numero, etiqueta, color):
        self.numero, self.etiqueta, self.color = numero, etiqueta, color
 
class Accion(Enum):
    CAMINAR = auto()
    RECOGER = auto()
    DEPOSITAR = auto()
    RECARGAR = auto()
    ESPERAR = auto()
    NADA = auto()
 
Percepcion = namedtuple("Percepcion", "energia pos visibles quedan")
 

# AMBIENTE

class Basura:
    def __init__(self, pos, peso):
        self.pos = V2(pos)
        self.peso = peso
 
    @property
    def radio(self):
        return 6 + self.peso * 0.9
 
    @property
    def color(self):
        u = (self.peso - 1) / 14
        a, b = (240, 210, 90), (150, 60, 40)
        return tuple(int(a[i] + (b[i] - a[i]) * u) for i in range(3))
 
class Ambiente:
    def __init__(self, rng):
        self.rng = rng
        self.estacion = V2(HAB.right - 60, HAB.centery)
        self.caja_rect = pygame.Rect(0, 0, 120, 90)
        self.caja_rect.center = (HAB.left + 95, HAB.top + 85)
        self.caja = V2(self.caja_rect.center)
        self.inicio_robot = V2(HAB.right - 120, HAB.centery + 40)
        self.basuras = []          # basura que aún no se recoge
        self.en_caja = []          # basura ya recogida
        self._generar_basura()
 
    def _generar_basura(self):
        n = self.rng.randint(*N_BASURA)
        pesos = self.rng.sample(list(PESOS), n)      # todos los pesos son distintos
        ocupados = []
        for peso in pesos:
            p = self._punto_libre(ocupados)
            ocupados.append(p)
            self.basuras.append(Basura(p, peso))
 
    def _punto_libre(self, ocupados):
        zona = HAB.inflate(-80, -80)
        zona_caja = self.caja_rect.inflate(80, 80)
        p = V2(zona.center)
        for _ in range(2000):
            p = V2(self.rng.uniform(zona.left, zona.right),
                   self.rng.uniform(zona.top, zona.bottom))
            if zona_caja.collidepoint(p):
                continue
            if p.distance_to(self.estacion) < 100 or p.distance_to(self.inicio_robot) < 60:
                continue
            if any(p.distance_to(o) < 45 for o in ocupados):
                continue
            break
        return p
 

# ROBOT  (percibir -> decidir -> actuar)

class Robot:
    def __init__(self, amb, rng):
        self.rng = rng
        # Conocimiento previo: Ubicación de la estación de recarga
        # y del cesto de basura o caja.
        self.pos_estacion = V2(amb.estacion)
        self.pos_caja = V2(amb.caja)
 
        self.pos = V2(amb.inicio_robot)
        self.rumbo = math.pi
        self.energia = float(CAPACIDAD_BATERIA)
        self.estado = Estado.BUSQUEDA
        self.destino = None
        self.destino_vagar = None
        self.objetivo = None        # basura que está buscando
        self.carga = None           # basura que lleva encima
        self.anim = None            # animación en curso de recoger o depositar
        self.espera = 0
        self.recargas = 0
        self.log = deque(maxlen=10)
        self.estela = deque(maxlen=300)
        self._contador = 0
        self.log.append("Inicia búsqueda")
 
    # --- PERCEPCIÓN
    def percibir(self, amb):
        """Solo ve la basura dentro de su radio de detección."""
        visibles = sorted(
            (b for b in amb.basuras if self.pos.distance_to(b.pos) <= RADIO_DETECCION),
            key=lambda b: self.pos.distance_to(b.pos))
        # Sabe SI quedan objetos (transición 'hay otro objeto'), pero no DÓNDE.
        return Percepcion(self.energia, V2(self.pos), visibles, bool(amb.basuras))
 
    # --- DECISIÓN
    def decidir(self, p):
        if self.estado is Estado.MUERTO:
            return Accion.NADA
        if p.energia <= 0:
            self._cambiar(Estado.MUERTO, "Batería agotada")
            return Accion.NADA
        if self.anim:
            return Accion.ESPERAR
 
        e = self.estado
        if e is Estado.BUSQUEDA:
            if p.energia < UMBRAL_BATERIA:
                self.objetivo = None
                self._cambiar(Estado.IR_A_BATERIA, "Batería baja: a cargar")
                self.destino = self.pos_estacion
                return Accion.CAMINAR
            if p.visibles:
                obj = self.objetivo if self.objetivo in p.visibles else p.visibles[0]
                if obj is not self.objetivo:
                    self.log.append(f"Detección objeto de {obj.peso} kg")
                self.objetivo = obj
                self.destino = obj.pos
                if self.pos.distance_to(obj.pos) <= ALCANCE_RECOGER:
                    return Accion.RECOGER
                return Accion.CAMINAR
            self.objetivo = None
            self._vagar()
            return Accion.CAMINAR
 
        if e is Estado.LLEVAR_A_CAJA:
            self.destino = self.pos_caja
            if self.pos.distance_to(self.pos_caja) <= ALCANCE_CAJA:
                return Accion.DEPOSITAR
            return Accion.CAMINAR
 
        if e is Estado.NUEVA_BUSQUEDA:
            if self.espera > 0:
                return Accion.ESPERAR
            if p.quedan:
                self._cambiar(Estado.BUSQUEDA, "Hay más objetos")
            else:
                self._cambiar(Estado.ALEATORIO, "Sin más objetos, a vagar")
            return Accion.NADA
 
        if e is Estado.IR_A_BATERIA:
            self.destino = self.pos_estacion
            if self.pos.distance_to(self.pos_estacion) <= ALCANCE_ESTACION:
                self._cambiar(Estado.RECARGAR, "Recargando...")
                return Accion.RECARGAR
            return Accion.CAMINAR
 
        if e is Estado.RECARGAR:
            if p.energia >= CAPACIDAD_BATERIA:
                self.recargas += 1
                self._cambiar(Estado.BUSQUEDA, "Recarga completa")
                return Accion.NADA
            return Accion.RECARGAR
 
        if e is Estado.ALEATORIO:
            self._vagar()
            return Accion.CAMINAR
        return Accion.NADA
 
    # --- ACCIÓN
    def actuar(self, accion, amb):
        if accion is Accion.CAMINAR:
            self._caminar()
        elif accion is Accion.RECOGER:
            b = self.objetivo
            amb.basuras.remove(b)
            self.anim = dict(tipo="recoger", t=0, dur=DUR_RECOGER, basura=b,
                             origen=V2(b.pos), costo=COSTO_RECOGER * b.peso)
        elif accion is Accion.DEPOSITAR:
            b = self.carga
            self.anim = dict(tipo="depositar", t=0, dur=DUR_DEPOSITAR, basura=b,
                             costo=COSTO_DEPOSITAR * b.peso)
        elif accion is Accion.RECARGAR:
            self.energia = min(CAPACIDAD_BATERIA, self.energia + TASA_RECARGA)
        elif accion is Accion.ESPERAR:
            if self.anim:
                self._avanzar_anim(amb)
            elif self.espera > 0:
                self.espera -= 1
 
    # --- AUXILIARES
    def _cambiar(self, nuevo, mensaje=None):
        self.estado = nuevo
        if nuevo is Estado.NUEVA_BUSQUEDA:
            self.espera = DUR_REVISAR
        if nuevo is Estado.MUERTO and self.anim:  # murió a mitad de la animación
            self.carga = self.anim["basura"]
            self.anim = None
        if mensaje:
            self.log.append(mensaje)
 
    def _gastar(self, cantidad):
        self.energia = max(0.0, self.energia - cantidad)
 
    def _vagar(self):
        """Paseo aleatorio: elige un punto al azar en la habitación y va hacia él."""
        if self.destino_vagar is None or self.pos.distance_to(self.destino_vagar) < 12:
            z = HAB.inflate(-80, -80)
            self.destino_vagar = V2(self.rng.uniform(z.left, z.right),
                                    self.rng.uniform(z.top, z.bottom))
        self.destino = self.destino_vagar
 
    def _caminar(self):
        d = self.destino - self.pos
        dist = d.length()
        if dist < 1e-6:
            return
        paso = min(VELOCIDAD, dist)
        self.pos += d / dist * paso
        self.rumbo = math.atan2(d.y, d.x)
        peso = self.carga.peso if self.carga else 0
        self._gastar(paso * (COSTO_MOVER + COSTO_CARGA * peso))
        self._contador += 1
        if self._contador % 3 == 0:
            self.estela.append(V2(self.pos))
 
    def _avanzar_anim(self, amb):
        a = self.anim
        a["t"] += 1
        self._gastar(a["costo"] / a["dur"])
        if a["t"] < a["dur"]:
            return
        self.anim = None
        b = a["basura"]
        if a["tipo"] == "recoger":
            self.carga, self.objetivo = b, None
            self._cambiar(Estado.LLEVAR_A_CAJA, f"Recogió {b.peso} kg")
        else:
            amb.en_caja.append(b)
            self.carga = None
            self._cambiar(Estado.NUEVA_BUSQUEDA, f"Depositó {b.peso} kg")
 

# SIMULACIÓN Y DIBUJO

RAYO = [(3, -14), (-7, 3), (-1, 3), (-4, 14), (7, -4), (1, -4)]
 
def dibujar_rayo(sup, centro, escala, color):
    pts = [(centro[0] + x * escala, centro[1] + y * escala) for x, y in RAYO]
    pygame.draw.polygon(sup, color, pts)
 
def suavizar(u):
    return u * u * (3 - 2 * u)
 
class Simulacion:
    def __init__(self, pantalla, semilla=None):
        self.p = pantalla
        self.f_titulo = pygame.font.Font(None, 32)
        self.f_normal = pygame.font.Font(None, 24)
        self.f_chico = pygame.font.Font(None, 20)
        self.f_peso = pygame.font.Font(None, 18)
        d = RADIO_DETECCION
        self.vision = pygame.Surface((2 * d, 2 * d), pygame.SRCALPHA)
        pygame.draw.circle(self.vision, (52, 152, 219, 40), (d, d), d)
        pygame.draw.circle(self.vision, (52, 152, 219, 120), (d, d), d, 2)
        self.reiniciar(semilla)
 
    def reiniciar(self, semilla=None):
        self.semilla = semilla if semilla is not None else random.randrange(10**6)
        self.rng = random.Random(self.semilla)
        self.amb = Ambiente(self.rng)
        self.robot = Robot(self.amb, self.rng)
        self.total = len(self.amb.basuras)
        self.pausa = False
        self.mult = 2
        self.pasos = 0
 
    @property
    def terminada(self):
        return self.robot.estado is Estado.MUERTO
 
    def paso(self):
        if self.terminada:
            return
        p = self.robot.percibir(self.amb)
        a = self.robot.decidir(p)
        self.robot.actuar(a, self.amb)
        self.pasos += 1
 
    # --- DIBUJO
    def txt(self, s, fuente, color, pos, centro=False):
        img = fuente.render(s, True, color)
        r = img.get_rect(center=pos) if centro else img.get_rect(topleft=pos)
        self.p.blit(img, r)
 
    def dibujar(self):
        self.p.fill((22, 25, 33))
        self._dibujar_habitacion()
        self._dibujar_estacion()
        self._dibujar_caja()
        self._dibujar_basura()
        self._dibujar_robot()
        self._dibujar_panel()
        if self.pausa:
            self.txt("PAUSA", self.f_titulo, (255, 255, 255), (HAB.centerx, HAB.top + 25), True)
        if self.terminada:
            self._dibujar_fin()
 
    def _dibujar_habitacion(self):
        pygame.draw.rect(self.p, (236, 232, 222), HAB)
        for x in range(HAB.left, HAB.right, 40):
            pygame.draw.line(self.p, (226, 221, 210), (x, HAB.top), (x, HAB.bottom))
        for y in range(HAB.top, HAB.bottom, 40):
            pygame.draw.line(self.p, (226, 221, 210), (HAB.left, y), (HAB.right, y))
        pygame.draw.rect(self.p, (70, 74, 90), HAB, 6)
        if len(self.robot.estela) > 1:
            pygame.draw.lines(self.p, (150, 185, 225), False,
                              [tuple(q) for q in self.robot.estela], 2)
 
    def _dibujar_estacion(self):
        c = self.amb.estacion
        cargando = self.robot.estado is Estado.RECARGAR
        if cargando:
            r = 46 + 6 * math.sin(self.pasos * 0.25)
            s = pygame.Surface((120, 120), pygame.SRCALPHA)
            pygame.draw.circle(s, (46, 204, 113, 90), (60, 60), int(r))
            self.p.blit(s, (c.x - 60, c.y - 60))
        pygame.draw.circle(self.p, (39, 130, 80), c, 32)
        pygame.draw.circle(self.p, (60, 180, 110), c, 28)
        dibujar_rayo(self.p, c, 1.2, (255, 245, 150))
        self.txt("F  Recarga", self.f_chico, (30, 90, 55), (c.x, c.y + 46), True)
 
    def _dibujar_caja(self):
        r = self.amb.caja_rect
        flash = self.robot.anim and self.robot.anim["tipo"] == "depositar" \
            and self.robot.anim["t"] > 0.8 * self.robot.anim["dur"]
        pygame.draw.rect(self.p, (155, 108, 62), r, border_radius=6)
        pygame.draw.rect(self.p, (255, 220, 120) if flash else (95, 62, 30), r, 5, border_radius=6)
        pygame.draw.rect(self.p, (120, 80, 45), r.inflate(-24, -24), border_radius=4)
        for i, b in enumerate(self.amb.en_caja):
            cx = r.x + 22 + (i % 5) * 19
            cy = r.y + 24 + (i // 5) * 21
            pygame.draw.circle(self.p, b.color, (cx, cy), min(8, int(b.radio)))
            pygame.draw.circle(self.p, (60, 40, 20), (cx, cy), min(8, int(b.radio)), 1)
        self.txt("CAJA", self.f_normal, (95, 62, 30), (r.centerx, r.top - 14), True)
 
    def _dibujar_item(self, b, pos, escala=1.0):
        rad = max(3, int(b.radio * escala))
        pygame.draw.circle(self.p, b.color, pos, rad)
        pygame.draw.circle(self.p, (60, 40, 30), pos, rad, 2)
        if escala > 0.7:
            self.txt(str(b.peso), self.f_peso, (30, 20, 15), pos, True)
 
    def _dibujar_basura(self):
        for b in self.amb.basuras:
            self._dibujar_item(b, b.pos)
 
    def _dibujar_robot(self):
        r = self.robot
        pos = r.pos
        muerto = r.estado is Estado.MUERTO
        if r.estado is Estado.BUSQUEDA:
            self.p.blit(self.vision, (pos.x - RADIO_DETECCION, pos.y - RADIO_DETECCION))
        pygame.draw.ellipse(self.p, (190, 185, 175), (pos.x - 16, pos.y + 10, 32, 14))
 
        # animaciones de recoger / depositar
        a = r.anim
        arriba = V2(pos.x, pos.y - 28)
        cuerpo = r.estado.color
        pygame.draw.circle(self.p, (40, 40, 50), pos, 19)
        pygame.draw.circle(self.p, cuerpo, pos, 16)
        fx, fy = math.cos(r.rumbo), math.sin(r.rumbo)
        px, py = -fy, fx
        for s in (-1, 1):
            ox, oy = pos.x + fx * 6 + px * 6 * s, pos.y + fy * 6 + py * 6 * s
            if muerto:
                pygame.draw.line(self.p, (30, 30, 30), (ox - 3, oy - 3), (ox + 3, oy + 3), 2)
                pygame.draw.line(self.p, (30, 30, 30), (ox - 3, oy + 3), (ox + 3, oy - 3), 2)
            else:
                pygame.draw.circle(self.p, (255, 255, 255), (ox, oy), 4)
                pygame.draw.circle(self.p, (20, 20, 20), (ox + fx * 1.5, oy + fy * 1.5), 2)
        pygame.draw.circle(self.p, (50, 50, 60), (pos.x + fx * 20, pos.y + fy * 20), 4)
 
        # brazo y objeto subiendo al robot (se dibuja encima del robot)
        if a and a["tipo"] == "recoger":
            u = suavizar(a["t"] / a["dur"])
            ip = a["origen"].lerp(arriba, u)
            pygame.draw.line(self.p, (90, 90, 95), pos, ip, 4)
            self._dibujar_item(a["basura"], ip, 1 - 0.2 * u)
            pygame.draw.circle(self.p, (60, 60, 65), ip, 4)
 
        # minibatería bajo el robot
        pct = r.energia / CAPACIDAD_BATERIA
        bx, by = pos.x - 20, pos.y + 24
        pygame.draw.rect(self.p, (40, 40, 40), (bx - 1, by - 1, 42, 8))
        pygame.draw.rect(self.p, self._color_bateria(pct), (bx, by, 40 * pct, 6))
 
        # objeto cargado / en camino hacia la caja
        if a and a["tipo"] == "depositar":
            u = suavizar(a["t"] / a["dur"])
            ip = arriba.lerp(self.amb.caja, u)
            ip.y -= math.sin(math.pi * u) * 35
            self._dibujar_item(a["basura"], ip, 1 - 0.25 * u)
        elif r.carga:
            self._dibujar_item(r.carga, arriba)
 
        # chispas al recargar batería
        if r.estado is Estado.RECARGAR and (self.pasos // 6) % 2 == 0:
            dibujar_rayo(self.p, (pos.x + 26, pos.y - 20), 0.9, (255, 235, 90))
            dibujar_rayo(self.p, (pos.x - 26, pos.y - 20), 0.9, (255, 235, 90))
 
    @staticmethod
    def _color_bateria(pct):
        if pct * CAPACIDAD_BATERIA < UMBRAL_BATERIA:
            return (231, 76, 60)
        return (241, 196, 15) if pct < 0.6 else (46, 204, 113)
 
    def _dibujar_panel(self):
        r = self.robot
        x0 = HAB.right + 20
        w = ANCHO - x0 - 20
        panel = pygame.Rect(x0, 20, w, ALTO - 40)
        pygame.draw.rect(self.p, (32, 36, 48), panel, border_radius=12)
        x, y = x0 + 16, 36
        blanco, gris = (240, 240, 245), (150, 155, 170)
 
        self.txt("ROBOT RECOGEDOR", self.f_titulo, blanco, (x, y)); y += 28
        self.txt("Versión 1", self.f_chico, gris, (x, y)); y += 28
 
        badge = pygame.Rect(x, y, w - 32, 34)
        pygame.draw.rect(self.p, r.estado.color, badge, border_radius=8)
        self.txt(f"{r.estado.numero} · {r.estado.etiqueta}", self.f_normal,
                 (255, 255, 255), badge.center, True)
        y += 50
 
        self.txt("Batería", self.f_chico, gris, (x, y)); y += 20
        barra = pygame.Rect(x, y, w - 32, 26)
        pct = r.energia / CAPACIDAD_BATERIA
        pygame.draw.rect(self.p, (20, 22, 30), barra, border_radius=6)
        relleno = barra.copy()
        relleno.width = int(barra.width * pct)
        pygame.draw.rect(self.p, self._color_bateria(pct), relleno, border_radius=6)
        mx = barra.x + barra.width * UMBRAL_BATERIA / CAPACIDAD_BATERIA
        pygame.draw.line(self.p, (255, 255, 255), (mx, barra.top - 3), (mx, barra.bottom + 3), 2)
        self.txt(f"{int(r.energia)} / {CAPACIDAD_BATERIA}", self.f_normal,
                 (255, 255, 255), barra.center, True)
        y += 34
        self.txt(f"umbral de recarga: {UMBRAL_BATERIA}", self.f_chico, gris, (x, y)); y += 30
 
        carga = f"{r.carga.peso} kg" if r.carga else "—"
        filas = [
            ("Cargando", carga),
            ("En el piso", f"{len(self.amb.basuras)} (sin ubicación)"),
            ("En la caja", f"{len(self.amb.en_caja)} / {self.total}"),
            ("Recargas", str(r.recargas)),
            ("Velocidad", f"x{self.mult}"),
            ("Semilla", str(self.semilla)),
        ]
        for k, v in filas:
            self.txt(k, self.f_chico, gris, (x, y))
            self.txt(v, self.f_chico, blanco, (x + 95, y))
            y += 22
 
        y += 12
        self.txt("Eventos", self.f_chico, gris, (x, y)); y += 22
        pygame.draw.line(self.p, (60, 65, 80), (x, y - 4), (x + w - 32, y - 4))
        for i, m in enumerate(r.log):
            fresco = i >= len(r.log) - 3
            self.txt(m, self.f_chico, blanco if fresco else gris, (x, y)); y += 20
 
        yb = panel.bottom - 56
        self.txt("ESPACIO pausa  |  R reiniciar", self.f_chico, gris, (x, yb))
        self.txt("+ / -  velocidad  |  ESC salir", self.f_chico, gris, (x, yb + 20))
 
    def _dibujar_fin(self):
        s = pygame.Surface(HAB.size, pygame.SRCALPHA)
        s.fill((0, 0, 0, 60))
        self.p.blit(s, HAB.topleft)
        caja = pygame.Rect(0, 0, 440, 150)
        caja.midtop = (HAB.centerx + 30, HAB.top + 14)
        pygame.draw.rect(self.p, (32, 36, 48), caja, border_radius=14)
        pygame.draw.rect(self.p, (231, 76, 60), caja, 3, border_radius=14)
        quedan = len(self.amb.basuras)
        self.txt("El robot murió", self.f_titulo, (255, 255, 255), (caja.centerx, caja.y + 26), True)
        if quedan == 0:
            msg = "Recogió todo y vagó hasta agotar la batería."
        else:
            msg = f"No llegó a tiempo: quedaron {quedan} objetos."
        self.txt(msg, self.f_normal, (220, 220, 230), (caja.centerx, caja.y + 60), True)
        self.txt(f"Recolectados: {len(self.amb.en_caja)} de {self.total}  ·  Recargas: {self.robot.recargas}",
                 self.f_normal, (220, 220, 230), (caja.centerx, caja.y + 86), True)
        self.txt("Presiona R para una nueva simulación", self.f_chico, (150, 155, 170),
                 (caja.centerx, caja.y + 122), True)
 
 
# PROGRAMA PRINCIPAL

def main():
    semilla = int(sys.argv[1]) if len(sys.argv) > 1 else None
    pygame.init()
    pantalla = pygame.display.set_mode((ANCHO, ALTO))
    pygame.display.set_caption("Robot recogedor de basura - Versión 1")
    reloj = pygame.time.Clock()
    sim = Simulacion(pantalla, semilla)
 
    corriendo = True
    while corriendo:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                corriendo = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    corriendo = False
                elif ev.key == pygame.K_SPACE:
                    sim.pausa = not sim.pausa
                elif ev.key == pygame.K_r:
                    sim.reiniciar()
                elif ev.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS, pygame.K_UP):
                    sim.mult = min(10, sim.mult + 1)
                elif ev.key in (pygame.K_MINUS, pygame.K_KP_MINUS, pygame.K_DOWN):
                    sim.mult = max(1, sim.mult - 1)
        if not sim.pausa:
            for _ in range(sim.mult):
                sim.paso()
        sim.dibujar()
        pygame.display.flip()
        reloj.tick(FPS)
    pygame.quit()
 
 
if __name__ == "__main__":
    main()
