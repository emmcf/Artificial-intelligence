import re
import time
from enum import Enum, auto
import gradio as gr

# 1. DATOS ENUMERADOS (ENUMS) EXTENDIDOS

class EstadoAgente(Enum):
    INICIAL = auto()
    ATENDIENDO = auto()
    DIAGNOSTICO_ESPECIALIDAD = auto()  # Estado activo durante el cuestionario
    FINALIZADO = auto()


class IntencionUsuario(Enum):
    SALUDO = auto()
    OBJETIVO = auto()
    PERFIL_EGRESO = auto()
    PLAN_ESTUDIOS = auto()
    MATERIAS_SEMESTRE = auto()
    CONTACTO = auto()
    TRAMITE_SERVICIO_SOCIAL = auto()
    TRAMITE_RESIDENCIAS = auto()
    TRAMITE_ACTIVIDADES_COMP = auto()
    TRAMITE_TITULACION = auto()
    TRAMITE_CARGA_BAJAS = auto()
    INICIAR_TEST_ESPECIALIDAD = auto()  # Disparador del test
    DESPEDIDA = auto()
    DESCONOCIDO = auto()


# 2. BASE DE CONOCIMIENTO Y TRÁMITES EXTENDIDOS

MATERIAS_POR_SEMESTRE = {
    "1° Semestre": [("Cálculo Diferencial", 5), ("Fundamentos de Programación", 5), ("Taller de Ética", 4), ("Matemáticas Discretas", 5), ("Taller de Administración", 4), ("Fundamentos de Investigación", 4)],
    "2° Semestre": [("Cálculo Integral", 5), ("Programación Orientada a Objetos", 5), ("Contabilidad Financiera", 4), ("Química", 4), ("Álgebra Lineal", 5), ("Probabilidad y Estadística", 5)],
    "3° Semestre": [("Cálculo Vectorial", 5), ("Estructura de Datos", 5), ("Cultura Empresarial", 4), ("Investigación de Operaciones", 4), ("Desarrollo Sustentable", 5), ("Física General", 5)],
    "4° Semestre": [("Ecuaciones Diferenciales", 5), ("Métodos Numéricos", 5), ("Tópicos Avanzados de Programación", 5), ("Fundamentos de Bases de Datos", 5), ("Simulación", 5), ("Principios Eléctricos y Aplicaciones Digitales", 5)],
    "5° Semestre": [("Graficación", 5), ("Fundamentos de Telecomunicaciones", 5), ("Taller de Bases de Datos", 4), ("Sistemas Operativos", 5), ("Fundamentos de Ingeniería de Software", 4), ("Arquitectura de Computadoras", 5)],
    "6° Semestre": [("Lenguajes y Autómatas I", 5), ("Redes de Computadoras", 5), ("Administración de Bases de Datos", 5), ("Taller de Sistemas Operativos", 4), ("Ingeniería de Software", 5), ("Lenguajes de Interfaz", 4)],
    "7° Semestre": [("Lenguajes y Autómatas II", 5), ("Conmutación y Enrutamiento en Redes", 5), ("Taller de Investigación I", 4), ("Gestión de Proyectos de Software", 5), ("Sistemas Programables", 5)],
    "8° Semestre": [("Programación Web", 5), ("Administración de Redes", 5), ("Taller de Investigación II", 4), ("Programación Lógica y Funcional", 5), ("Aprendizaje Automático", 5), ("Visión Artificial", 5)],
    "9° Semestre": [("Inteligencia Artificial", 5), ("Procesamiento de Lenguaje Natural", 5), ("Aprendizaje Profundo", 5), ("Internet de las Cosas", 5)]
}

TOTAL_CREDITOS_CARRERA = 260

BASE_CONOCIMIENTO = {
    "objetivo": (
        "El objetivo general de Ingeniería en Sistemas Computacionales en el TecNM Campus Ciudad Guzmán es:\n"
        "Formar profesionistas líderes con visión estratégica y amplio sentido ético; capaces de diseñar, "
        "desarrollar, implementar y administrar tecnología computacional para aportar soluciones innovadoras "
        "en beneficio de la sociedad en un contexto global, multidisciplinario y sostenible."
    ),
    "perfil": (
        "Perfil Profesional del Egresado ISC:\n"
        "• Diseña e implementa software y aplicaciones computacionales para diversos contextos.\n"
        "• Diseña, implementa y administra bases de datos y redes de computadoras.\n"
        "• Desarrolla interfaces para la automatización de hardware y software.\n"
        "• Aplica modelos matemáticos e Inteligencia Artificial para resolver problemas complejos."
    ),
    "contacto": (
        "Información de Contacto y Coordinación (TecNM Ciudad Guzmán):\n"
        "• Coordinadora: Elva Adriana Cárdenas Chávez\n"
        "• Ubicación: Planta Alta, Centro de Información\n"
        "• Correo: coor.con@cdguzman.tecnm.mx\n"
        "• Teléfono: 341 575 20 50 Ext. 171 / Directo: 341 575 20 67"
    ),
    "servicio_social": (
        "**Información de Servicio Social (TecNM):**\n"
        "• **Requisito mínimo:** Tener acreditado al menos el 70`%` de créditos (182 créditos).\n"
        "• **Duración:** 500 horas prestadas en un periodo no menor a 6 meses ni mayor a 2 años.\n"
        "• **Valor curricular:** 10 créditos."
    ),
    "residencias": (
        "**Información de Residencias Profesionales:**\n"
        "• **Requisitos:** 80`%` de créditos (208 créditos), Servicio Social y Actividades Complementarias liberadas.\n"
        "• **Duración:** 500 horas en un periodo de 4 a 6 meses.\n"
        "• **Valor curricular:** 10 créditos."
    ),
    "actividades_comp": (
        "**Actividades Complementarias (5 Créditos):**\n"
        "• Tutorías, actividades culturales/deportivas, concursos de ciencias/robótica, cursos de capacitación técnica."
    ),
    "titulacion": (
        "**Opciones de Titulación Integrada (TecNM):**\n"
        "1. Informe Técnico de Residencias Profesionales.\n"
        "2. Proyecto de Investigación / Desarrollo Tecnológico.\n"
        "3. Tesis Profesional.\n"
        "4. Examen CENEVAL (EGEL).\n"
        "5. Créditos de Posgrado."
    ),
    "carga_bajas": (
        "**Reglamento de Carga Académica y Bajas:**\n"
        "• Carga Regular: Mínimo 22 cr, máximo 36 cr por semestre.\n"
        "• Baja Temporal: Se solicita en Servicios Escolares dentro de las primeras semanas del semestre."
    )
}


# 3. CLASE DEL AGENTE INTELIGENTE CON TEST DE ESPECIALIDAD

class AgenteConversacionalISC:
    def __init__(self, nombre="SistemasBot"):
        self.nombre = nombre
        self.estado = EstadoAgente.INICIAL
        self.paso_test = 0
        self.respuestas_test = []

    def normalizar_texto(self, texto: str) -> str:
        texto = texto.lower()
        replacements = (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"))
        for a, b in replacements:
            texto = texto.replace(a, b)
        return texto

    def percibir(self, mensaje_usuario: str):
        texto = self.normalizar_texto(mensaje_usuario)

        # Si el agente está en modo test, procesa la opción seleccionada
        if self.estado == EstadoAgente.DIAGNOSTICO_ESPECIALIDAD:
            return IntencionUsuario.INICIAR_TEST_ESPECIALIDAD, texto

        semestre_match = re.search(r'\b([1-9])\b|primer|segundo|tercer|cuarto|quinto|sexto|septimo|octavo|noveno', texto)
        num_semestre = None
        if semestre_match:
            val = semestre_match.group(0)
            mapa_semestres = {
                "1": "1", "primer": "1", "2": "2", "segundo": "2",
                "3": "3", "tercer": "3", "4": "4", "cuarto": "4",
                "5": "5", "quinto": "5", "6": "6", "sexto": "6",
                "7": "7", "septimo": "7", "8": "8", "octavo": "8",
                "9": "9", "noveno": "9"
            }
            num_semestre = mapa_semestres.get(val, val)

        if any(w in texto for w in ["especialidad", "orientacion", "test", "recomiendame", "perfil laboral"]):
            return IntencionUsuario.INICIAR_TEST_ESPECIALIDAD, ""
        elif any(w in texto for w in ["adios", "bye", "hasta luego", "salir", "terminar", "gracias"]):
            return IntencionUsuario.DESPEDIDA, ""
        elif any(w in texto for w in ["hola", "buenas", "inicio", "saludos"]):
            return IntencionUsuario.SALUDO, ""
        elif any(w in texto for w in ["servicio social", "servicio"]):
            return IntencionUsuario.TRAMITE_SERVICIO_SOCIAL, ""
        elif any(w in texto for w in ["residencia", "residencias"]):
            return IntencionUsuario.TRAMITE_RESIDENCIAS, ""
        elif any(w in texto for w in ["actividades complementarias", "complementarias"]):
            return IntencionUsuario.TRAMITE_ACTIVIDADES_COMP, ""
        elif any(w in texto for w in ["titulacion", "titularme", "ceneval"]):
            return IntencionUsuario.TRAMITE_TITULACION, ""
        elif any(w in texto for w in ["baja", "carga academica", "creditos"]):
            return IntencionUsuario.TRAMITE_CARGA_BAJAS, ""
        elif any(w in texto for w in ["objetivo", "meta", "de que trata"]):
            return IntencionUsuario.OBJETIVO, ""
        elif any(w in texto for w in ["perfil", "egresado", "campo laboral"]):
            return IntencionUsuario.PERFIL_EGRESO, ""
        elif num_semestre:
            return IntencionUsuario.MATERIAS_SEMESTRE, num_semestre
        elif any(w in texto for w in ["materia", "reticula", "plan de estudio", "semestre"]):
            return IntencionUsuario.PLAN_ESTUDIOS, ""
        elif any(w in texto for w in ["contacto", "coordinador", "telefono", "correo"]):
            return IntencionUsuario.CONTACTO, ""
        else:
            return IntencionUsuario.DESCONOCIDO, ""

    def decidir(self, intencion: IntencionUsuario, detalle: str) -> str:
        # LÓGICA DEL CUESTIONARIO DE ESPECIALIDAD
        if intencion == IntencionUsuario.INICIAR_TEST_ESPECIALIDAD:
            if self.estado != EstadoAgente.DIAGNOSTICO_ESPECIALIDAD:
                self.estado = EstadoAgente.DIAGNOSTICO_ESPECIALIDAD
                self.paso_test = 1
                self.respuestas_test = []
                return (
                    "**Cuestionario de Orientación de Especialidad**\n\n"
                    "Te haré 3 preguntas rápidas para determinar tu perfil ideal.\n\n"
                    "**Pregunta 1/3:** ¿Qué tipo de proyectos te motivan más desarrollar?\n"
                    "a) Modelos inteligentes, visión por computadora o análisis de datos.\n"
                    "b) Aplicaciones web/móviles, sistemas de gestión y bases de datos.\n"
                    "c) Configuración de redes, servidores, ciberseguridad e Internet de las Cosas (IoT)."
                )

            elif self.paso_test == 1:
                self.respuestas_test.append(detalle)
                self.paso_test = 2
                return (
                    "**Pregunta 2/3:** ¿En qué grupo de asignaturas sientes mayor facilidad o interés?\n"
                    "a) Programación Web, Programación Orientada a Objetos, Bases de Datos.\n"
                    "b) Redes de Computadoras, Conmutación y Enrutamiento, Sistemas Operativos, IoT.\n."
                    "c) Aprendizaje Automático, Programación Lógica, Inteligencia Artificial.\n"
                )

            elif self.paso_test == 2:
                self.respuestas_test.append(detalle)
                self.paso_test = 3
                return (
                    "**Pregunta 3/3:** ¿En qué rol profesional te visualizas trabajando al egresar?\n"
                    "a) Administrador de Redes/Ciberseguridad, DevOps o Ingeniero de IoT / Embebidos.\n."
                    "b) Full Stack Developer, Arquitecto de Software o Administrador de Bases de Datos.\n"
                    "c) AI Engineer, Data Scientist o Desarrollador de Modelos Inteligentes.\n"
                )

            elif self.paso_test == 3:
                self.respuestas_test.append(detalle)
                self.estado = EstadoAgente.ATENDIENDO
                
                # Evaluación de Respuestas
                conteo_a = sum(1 for r in self.respuestas_test if 'a' in r)
                conteo_b = sum(1 for r in self.respuestas_test if 'b' in r)
                conteo_c = sum(1 for r in self.respuestas_test if 'c' in r)

                if conteo_a >= conteo_b and conteo_a >= conteo_c:
                    return (
                        "**Dictamen de Especialidad Sugerida:**\n\n"
                        "**Especialidad Recomendada: Inteligencia Artificial y Ciencia de Datos**\n"
                        "• **Perfil:** Demuestras una clara inclinación por el análisis de patrones, algoritmos avanzados y automatización inteligente.\n"
                        "• **Materias Clave de tu Retícula:** *Aprendizaje Automático, Visión Artificial, Procesamiento de Lenguaje Natural, Aprendizaje Profundo e Inteligencia Artificial*.\n"
                        "• **Oportunidades:** Machine Learning Engineer, Data Analyst, Especialista en NLP/Computer Vision."
                    )
                elif conteo_b >= conteo_a and conteo_b >= conteo_c:
                    return (
                        "**Dictamen de Especialidad Sugerida:**\n\n"
                        "**Especialidad Recomendada: Desarrollo de Software y Arquitectura Web/Cloud**\n"
                        "• **Perfil:** Tu enfoque está orientado a construir soluciones funcionales, diseño de software robusto y gestión eficiente de bases de datos.\n"
                        "• **Materias Clave de tu Retícula:** *Programación Web, Ingeniería de Software, Tópicos Avanzados de Programación, Bases de Datos*.\n"
                        "• **Oportunidades:** Desarrollador Full-Stack, Ingeniero de Software, Backend Developer, DB Admin."
                    )
                else:
                    return (
                        "**Dictamen de Especialidad Sugerida:**\n\n"
                        "**Especialidad Recomendada: Redes, Ciberseguridad y Sistemas Integrados (IoT)**\n"
                        "• **Perfil:** Te apasiona la infraestructura tecnológica, la conectividad segura y la integración entre hardware y software.\n"
                        "• **Materias Clave de tu Retícula:** *Redes de Computadoras, Conmutación y Enrutamiento, Sistemas Programables, Internet de las Cosas, Administración de Redes*.\n"
                        "• **Oportunidades:** Network Engineer, Especialista en Ciberseguridad, Ingeniero de IoT / Embebidos, DevOps."
                    )

        self.estado = EstadoAgente.ATENDIENDO

        if intencion == IntencionUsuario.SALUDO:
            return (
                f"¡Hola! Soy {self.nombre}, tu asistente para la carrera de ISC en TecNM Cd. Guzmán.\n\n"
                "¿En qué te puedo ayudar hoy?\n"
                "• Información general o materias por semestre.\n"
                "• Trámites (Servicio Social, Residencias, Titulación).\n"
                "• Escribe **'recomiéndame una especialidad'** para hacer el test de orientación."
            )
        elif intencion == IntencionUsuario.OBJETIVO:
            return BASE_CONOCIMIENTO["objetivo"]
        elif intencion == IntencionUsuario.PERFIL_EGRESO:
            return BASE_CONOCIMIENTO["perfil"]
        elif intencion == IntencionUsuario.TRAMITE_SERVICIO_SOCIAL:
            return BASE_CONOCIMIENTO["servicio_social"]
        elif intencion == IntencionUsuario.TRAMITE_RESIDENCIAS:
            return BASE_CONOCIMIENTO["residencias"]
        elif intencion == IntencionUsuario.TRAMITE_ACTIVIDADES_COMP:
            return BASE_CONOCIMIENTO["actividades_comp"]
        elif intencion == IntencionUsuario.TRAMITE_TITULACION:
            return BASE_CONOCIMIENTO["titulacion"]
        elif intencion == IntencionUsuario.TRAMITE_CARGA_BAJAS:
            return BASE_CONOCIMIENTO["carga_bajas"]
        elif intencion == IntencionUsuario.MATERIAS_SEMESTRE:
            for k, v in MATERIAS_POR_SEMESTRE.items():
                if k.startswith(detalle):
                    return f"Materias de {k}:\n• " + "\n• ".join([m[0] for m in v])
            return "No encontré materias para ese semestre."
        elif intencion == IntencionUsuario.PLAN_ESTUDIOS:
            res = "Plan General de Estudios por Semestre:\n\n"
            for sem, mats in MATERIAS_POR_SEMESTRE.items():
                m_str = ", ".join([m[0] for m in mats])
                res += f"• {sem}: {m_str}\n\n"
            return res.strip()
        elif intencion == IntencionUsuario.CONTACTO:
            return BASE_CONOCIMIENTO["contacto"]
        elif intencion == IntencionUsuario.DESPEDIDA:
            self.estado = EstadoAgente.FINALIZADO
            return "¡Gracias por consultar el portal de ISC en TecNM Cd. Guzmán! ¡Mucho éxito!"
        else:
            return (
                "Lo siento, no comprendí bien tu solicitud. Puedes preguntarme sobre 'Servicio Social', "
                "'Residencias', 'Titulación', 'Materias de x semestre', o escribir **'test de especialidad'**."
            )

    def actuar_stream(self, mensaje_usuario: str):
        if self.estado == EstadoAgente.FINALIZADO:
            self.estado = EstadoAgente.INICIAL

        intencion, detalle = self.percibir(mensaje_usuario)
        respuesta_completa = self.decidir(intencion, detalle)

        respuesta_parcial = ""
        palabras = respuesta_completa.split(" ")
        for palabra in palabras:
            respuesta_parcial += palabra + " "
            time.sleep(0.03)
            yield respuesta_parcial.strip()


# 4. LÓGICA DEL PANEL DE AVANCE CURRICULAR

def calcular_avance(materias_seleccionadas, act_comp, servicio_soc, residencias):
    creditos_obtenidos = 0
    for sem, lista_mats in MATERIAS_POR_SEMESTRE.items():
        for nombre_mat, creds in lista_mats:
            if nombre_mat in materias_seleccionadas:
                creditos_obtenidos += creds

    if act_comp:
        creditos_obtenidos += 5
    if servicio_soc:
        creditos_obtenidos += 10
    if residencias:
        creditos_obtenidos += 10

    porcentaje = round((creditos_obtenidos / TOTAL_CREDITOS_CARRERA) * 100, 2)

    diagnostico = f"Resumen de Créditos:\n"
    diagnostico += f"• **Créditos Acumulados:** {creditos_obtenidos} / {TOTAL_CREDITOS_CARRERA}\n"
    diagnostico += f"• **Porcentaje de Avance:** {porcentaje}%\n\n"
    diagnostico += "Estado de Trámites Requeridos:\n"

    if servicio_soc:
        diagnostico += "**Servicio Social:** Liberado (10 créditos).\n"
    elif creditos_obtenidos >= 182:
        diagnostico += "**Servicio Social:** ¡Elegible para iniciar! (Superaste el 70`%` de créditos).\n"
    else:
        faltantes_ss = 182 - creditos_obtenidos
        diagnostico += f"**Servicio Social:** No elegible. Te faltan {faltantes_ss} créditos para alcanzar el 70%.\n"

    if residencias:
        diagnostico += "**Residencias Profesionales:** Liberadas (10 créditos).\n"
    elif creditos_obtenidos >= 208 and servicio_soc and act_comp:
        diagnostico += "**Residencias Profesionales:** ¡Elegible para solicitar! Cumples con todos los requisitos previos.\n"
    else:
        motivos = []
        if creditos_obtenidos < 208:
            motivos.append(f"alcanzar el 80% de créditos (te faltan {208 - creditos_obtenidos} cr)")
        if not servicio_soc:
            motivos.append("liberar el Servicio Social")
        if not act_comp:
            motivos.append("liberar las Actividades Complementarias")
        diagnostico += f"**Residencias Profesionales:** No elegible aún. Necesitas: {', '.join(motivos)}.\n"

    return porcentaje, diagnostico


# 5. INTERFAZ GRADIO MULTITABULAR

agente = AgenteConversacionalISC()

def responder_chat_stream(mensaje, historial):
    if not mensaje or not mensaje.strip():
        yield "", historial
        return

    historial.append({"role": "user", "content": mensaje})
    historial.append({"role": "assistant", "content": "..."})
    yield "", historial

    for respuesta_parcial in agente.actuar_stream(mensaje):
        historial[-1]["content"] = respuesta_parcial
        yield "", historial


with gr.Blocks(title="Portal Inteligente ISC - TecNM Cd. Guzmán") as demo:
    gr.Markdown("# Sistema Inteligente de Orientación y Avance Curricular ISC")
    gr.Markdown("### TecNM Campus Ciudad Guzmán")

    with gr.Tabs():
        with gr.TabItem("Chatbot Asistente"):
            chatbot = gr.Chatbot(label="SistemasBot", height=450)
            msg_input = gr.Textbox(placeholder="Escribe 'test de especialidad', pregunta sobre la carrera o trámites...", label="Mensaje")
            
            with gr.Row():
                btn_enviar = gr.Button("Enviar", variant="primary")
                btn_limpiar = gr.ClearButton([msg_input, chatbot], value="Limpiar Chat")

            msg_input.submit(responder_chat_stream, inputs=[msg_input, chatbot], outputs=[msg_input, chatbot])
            btn_enviar.click(responder_chat_stream, inputs=[msg_input, chatbot], outputs=[msg_input, chatbot])

        with gr.TabItem("Panel de Avance Curricular"):
            gr.Markdown("### Selecciona las materias que ya has acreditado:")
            
            checkboxes_materias = []
            
            with gr.Row():
                with gr.Column(scale=2):
                    for sem, lista_mats in MATERIAS_POR_SEMESTRE.items():
                        with gr.Accordion(f"{sem}", open=False):
                            nombres_mats = [m[0] for m in lista_mats]
                            cb = gr.CheckboxGroup(choices=nombres_mats, label="Materias Aprobadas")
                            checkboxes_materias.append(cb)
                            
                            btn_toggle = gr.Button(f"Seleccionar todo", size="sm")
                            estado_btn = gr.State(value=False)

                            btn_toggle.click(
                                fn=lambda est, l=nombres_mats: (l, True, gr.update(value="Desmarcar todo")) if not est else ([], False, gr.update(value="Seleccionar todo")),
                                inputs=[estado_btn],
                                outputs=[cb, estado_btn, btn_toggle]
                            )
                            
                with gr.Column(scale=1):
                    gr.Markdown("### Requisitos Especiales:")
                    cb_act_comp = gr.Checkbox(label="Actividades Complementarias (5 cr)")
                    cb_servicio = gr.Checkbox(label="Servicio Social (10 cr)")
                    cb_residencias = gr.Checkbox(label="Residencias Profesionales (10 cr)")

                    btn_calcular = gr.Button("Calcular Avance Académico", variant="primary")
                    
                    slider_avance = gr.Slider(minimum=0, maximum=100, label="Porcentaje de Avance General (%)", interactive=False)
                    out_diagnostico = gr.Markdown(value="*Haz clic en 'Calcular Avance' para ver tu estatus.*")

            def procesar_panel(*inputs):
                mats_seleccionadas = []
                for lista_sem in inputs[:9]:
                    if lista_sem:
                        mats_seleccionadas.extend(lista_sem)

                act_comp = inputs[9]
                servicio_soc = inputs[10]
                residencias = inputs[11]

                return calcular_avance(mats_seleccionadas, act_comp, servicio_soc, residencias)

            btn_calcular.click(
                fn=procesar_panel,
                inputs=checkboxes_materias + [cb_act_comp, cb_servicio, cb_residencias],
                outputs=[slider_avance, out_diagnostico]
            )

if __name__ == "__main__":
    demo.launch()