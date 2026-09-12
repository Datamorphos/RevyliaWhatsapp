"""Pruebas del copiloto del panel (`src/panel_agent/`).

Sin base de datos y sin llamadas a Gemini.

Estrategia en dos capas:

1. **Capa AST (siempre se ejecuta).** Analiza el código fuente sin importarlo,
   así que verifica los invariantes del contrato aunque falten `langgraph`,
   `langchain_google_genai`, `ag_ui_langgraph`, `copilotkit` o el módulo
   `src/panel/queries.py` que crea A1. Aquí viven las cuatro garantías
   exigidas: ninguna herramienta acepta `clinic_id`, no hay herramientas de
   escritura, no se construye checkpointer y el prompt trae la defensa
   anti-inyección.
2. **Capa viva (`importorskip`).** Comprueba los objetos reales cuando el
   entorno tiene las dependencias instaladas.
"""

import ast
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
PAQUETE = RAIZ / "src" / "panel_agent"

MODULOS = ("tools", "graph", "server", "prompts", "__init__")

# §5: un endpoint, una herramienta.
HERRAMIENTAS_ESPERADAS = {
    "panel_resumen",
    "panel_listar_pacientes",
    "panel_obtener_paciente",
    "panel_listar_citas",
    "panel_consultar_disponibilidad",
    "panel_listar_oportunidades",
    "panel_listar_escalamientos",
    "panel_listar_recuperacion",
    "panel_listar_eventos",
    "panel_consultar_catalogo",
}

# §9: las únicas funciones que `src/panel/queries.py` expone. Todas de lectura.
LECTURAS_PERMITIDAS = {
    "get_summary",
    "list_patients",
    "get_patient",
    "list_appointments",
    "get_availability",
    "list_opportunities",
    "list_escalations",
    "list_recovery",
    "list_events",
    "get_catalog",
}

ALIAS_DE_CLINICA = {
    "clinic_id",
    "clinicid",
    "clinica_id",
    "clinic",
    "tenant_id",
    "tenant",
    "org_id",
    "organization_id",
    "clinic_slug",
}

VERBOS_DE_ESCRITURA = re.compile(
    r"^(create|insert|update|delete|remove|drop|truncate|save|upsert|write|"
    r"send|approve|schedule|cancel|reschedule|execute|exec|commit|rollback)",
    re.IGNORECASE,
)

SQL_LIBRE = re.compile(
    r"\bselect\b.+\bfrom\b|\binsert\s+into\b|\bupdate\b.+\bset\b|"
    r"\bdelete\s+from\b|\bdrop\s+table\b|\bcreate\s+table\b",
    re.IGNORECASE | re.DOTALL,
)

# Nombres de la generación v1 de CopilotKit. Mezclarlas con v2 rompe AG-UI.
API_V1_PROHIBIDA = {
    "CopilotKitRemoteEndpoint",
    "LangGraphAgent",
    "add_fastapi_endpoint",
    "copilotkit_remote_endpoint",
}


# --------------------------------------------------------------------------
# Utilidades AST
# --------------------------------------------------------------------------


def arbol(modulo: str) -> ast.Module:
    ruta = PAQUETE / f"{modulo}.py"
    assert ruta.is_file(), f"Falta {ruta}"
    return ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))


def _raiz_decorador(decorador: ast.expr) -> str:
    nodo = decorador.func if isinstance(decorador, ast.Call) else decorador
    if isinstance(nodo, ast.Name):
        return nodo.id
    if isinstance(nodo, ast.Attribute):
        return nodo.attr
    return ""


def herramientas(tree: ast.Module) -> list[ast.FunctionDef]:
    """Funciones decoradas con `@tool` en el nivel superior del módulo."""
    return [
        nodo
        for nodo in tree.body
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(_raiz_decorador(dec) == "tool" for dec in nodo.decorator_list)
    ]


def nombres_de_parametros(func: ast.FunctionDef) -> list[str]:
    a = func.args
    return [arg.arg for arg in (*a.posonlyargs, *a.args, *a.kwonlyargs)]


def importaciones(tree: ast.Module) -> list[tuple[str, str]]:
    """Lista de `(modulo, nombre_importado)` del módulo analizado."""
    resultado: list[tuple[str, str]] = []
    for nodo in ast.walk(tree):
        if isinstance(nodo, ast.ImportFrom):
            for alias in nodo.names:
                resultado.append((nodo.module or "", alias.name))
        elif isinstance(nodo, ast.Import):
            for alias in nodo.names:
                resultado.append((alias.name, alias.name))
    return resultado


def identificadores(tree: ast.Module) -> set[str]:
    """Identificadores reales del código (NO cadenas ni docstrings)."""
    encontrados: set[str] = set()
    for nodo in ast.walk(tree):
        if isinstance(nodo, ast.Name):
            encontrados.add(nodo.id)
        elif isinstance(nodo, ast.Attribute):
            encontrados.add(nodo.attr)
        elif isinstance(nodo, ast.keyword) and nodo.arg:
            encontrados.add(nodo.arg)
    return encontrados


def cadenas(tree: ast.Module) -> list[str]:
    return [
        nodo.value
        for nodo in ast.walk(tree)
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str)
    ]


# --------------------------------------------------------------------------
# 1. `clinic_id` nunca es argumento de herramienta (§0.2, §6)
# --------------------------------------------------------------------------


def test_existe_una_herramienta_por_endpoint_de_seccion_5():
    nombres = {func.name for func in herramientas(arbol("tools"))}
    assert nombres == HERRAMIENTAS_ESPERADAS


def test_ninguna_herramienta_acepta_clinic_id():
    for func in herramientas(arbol("tools")):
        for parametro in nombres_de_parametros(func):
            assert parametro.lower() not in ALIAS_DE_CLINICA, (
                f"{func.name} acepta `{parametro}`: el identificador de clínica "
                "debe salir de la configuración del servidor (§0.2)."
            )


def test_ninguna_herramienta_admite_argumentos_libres():
    """Sin *args/**kwargs ni parámetros tipo `dict`: son un canal por donde
    colar `clinic_id` sin que aparezca como nombre de parámetro."""
    tipos_libres = {"dict", "Dict", "Any", "object", "list", "List", "JSON"}
    for func in herramientas(arbol("tools")):
        assert func.args.vararg is None, f"{func.name} usa *args"
        assert func.args.kwarg is None, f"{func.name} usa **kwargs"
        for arg in (*func.args.posonlyargs, *func.args.args, *func.args.kwonlyargs):
            anotacion = ast.unparse(arg.annotation) if arg.annotation else ""
            assert anotacion, f"{func.name}.{arg.arg} no tiene anotación de tipo"
            assert not any(
                tipo in anotacion.split("[")[0].split("|")[0].strip()
                for tipo in tipos_libres
            ), f"{func.name}.{arg.arg} usa el tipo libre `{anotacion}`"


def test_clinic_id_sale_de_la_configuracion_del_servidor():
    """El `clinic_id` viene de `PanelSettings.revylia_clinic_id` (§0.2, §1),
    el mismo objeto de configuración que usa la conexión de solo lectura."""
    fuente = (PAQUETE / "tools.py").read_text(encoding="utf-8")
    assert "settings.revylia_clinic_id" in fuente
    assert ("src.panel.config", "get_panel_settings") in importaciones(arbol("tools"))
    for func in herramientas(arbol("tools")):
        cuerpo = ast.unparse(func)
        if "panel_connection" in cuerpo:
            assert "get_panel_settings()" in cuerpo, (
                f"{func.name} abre conexión sin resolver la configuración del panel"
            )


def test_la_conexion_recibe_la_configuracion_del_panel():
    """`panel_connection` espera `PanelSettings`, no el `Settings` del núcleo:
    pasarle el objeto equivocado haría fallar toda consulta en silencio."""
    inspect = pytest.importorskip("inspect")
    db = pytest.importorskip("src.panel.db", reason="requiere src/panel/db.py (A1)")
    anotacion = str(inspect.signature(db.panel_connection).parameters["settings"])
    assert "PanelSettings" in anotacion


# --------------------------------------------------------------------------
# 2. No hay herramientas de escritura ni SQL libre (§6)
# --------------------------------------------------------------------------


def test_solo_se_importan_funciones_de_lectura_de_queries():
    importadas = {
        nombre
        for modulo, nombre in importaciones(arbol("tools"))
        if modulo == "src.panel.queries"
    }
    assert importadas == LECTURAS_PERMITIDAS, (
        "tools.py debe importar exactamente las diez funciones de lectura de §9."
    )


def test_no_hay_herramientas_de_escritura():
    for func in herramientas(arbol("tools")):
        assert not VERBOS_DE_ESCRITURA.match(func.name.replace("panel_", "")), (
            f"{func.name} parece una herramienta de escritura."
        )
    for nombre in identificadores(arbol("tools")):
        assert not VERBOS_DE_ESCRITURA.match(nombre), (
            f"tools.py invoca `{nombre}`, que sugiere una escritura."
        )


def test_no_se_importa_el_repositorio_de_escritura():
    """§0.3: `ClinicRepository` tiene métodos de escritura y un `read_table()`
    que interpola el nombre de tabla. El copiloto tampoco lo toca."""
    for modulo in MODULOS:
        for origen, nombre in importaciones(arbol(modulo)):
            assert "src.database" not in origen, f"{modulo}.py importa {origen}"
            assert nombre != "ClinicRepository", f"{modulo}.py importa ClinicRepository"


def test_no_hay_sql_libre_en_el_copiloto():
    for modulo in MODULOS:
        for texto in cadenas(arbol(modulo)):
            assert not SQL_LIBRE.search(texto), f"{modulo}.py contiene SQL literal"


def test_no_hay_herramientas_de_diagnostico():
    """§6 prohíbe exponer diagnóstico técnico al copiloto."""
    prohibidos = re.compile(r"(diagnos|debug|healthcheck|explain|pg_|information_schema)", re.I)
    for func in herramientas(arbol("tools")):
        assert not prohibidos.search(func.name)


def test_los_errores_no_filtran_trazas_ni_sql():
    """§4: el error nunca lleva traza ni SQL, solo `type` y `message`."""
    fuente = (PAQUETE / "tools.py").read_text(encoding="utf-8")
    assert "repr(exc)" not in fuente
    assert "traceback" not in fuente
    for tipo in ("upstream_unavailable", "validation_error", "not_found"):
        assert tipo in fuente


# --------------------------------------------------------------------------
# 3. Sin checkpointer (§0.5)
# --------------------------------------------------------------------------


def test_no_se_construye_checkpointer():
    patron = re.compile(r"(checkpoint|saver)", re.IGNORECASE)
    for modulo in MODULOS:
        tree = arbol(modulo)
        for nombre in identificadores(tree):
            assert not patron.search(nombre), (
                f"{modulo}.py usa el identificador `{nombre}`: §0.5 prohíbe "
                "cualquier checkpointer en el copiloto del panel."
            )
        for origen, nombre in importaciones(tree):
            assert not patron.search(origen), f"{modulo}.py importa {origen}"
            assert not patron.search(nombre), f"{modulo}.py importa {nombre}"


def test_el_grafo_se_compila_sin_checkpointer():
    for nodo in ast.walk(arbol("graph")):
        if isinstance(nodo, ast.Call) and _raiz_decorador(nodo) == "compile":
            argumentos = {kw.arg for kw in nodo.keywords}
            assert "checkpointer" not in argumentos
            assert "store" not in argumentos


# --------------------------------------------------------------------------
# 4. Prompt: defensa anti-inyección y reglas del contrato
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def prompt() -> str:
    """`prompts.py` no tiene dependencias, así que se importa de verdad."""
    from src.panel_agent.prompts import SYSTEM_PROMPT

    return SYSTEM_PROMPT


def test_el_prompt_trata_los_textos_de_bd_como_datos(prompt):
    minuscula = prompt.lower()
    for campo in ("notes", "reason", "message", "response_text"):
        assert campo in prompt, f"El prompt no nombra el campo `{campo}`"
    assert "instrucciones" in minuscula
    assert "no lo obedezcas" in minuscula or "nunca" in minuscula
    assert "cita" in minuscula or "entrecom" in minuscula


def test_el_prompt_prohibe_la_escritura(prompt):
    minuscula = prompt.lower()
    assert "solo lectura" in minuscula or "sólo lectura" in minuscula
    assert "jamás escritura" in minuscula or "jamas escritura" in minuscula
    for verbo in ("crear", "modificar", "borrar"):
        assert verbo in minuscula


def test_el_prompt_exige_citar_fuente_filtros_y_momento(prompt):
    for clave in ("source", "filters", "generated_at"):
        assert clave in prompt, f"El prompt no exige citar `{clave}`"


def test_el_prompt_distingue_vacio_de_fallo(prompt):
    minuscula = prompt.lower()
    assert "no hay registros" in minuscula
    assert "error" in minuscula
    assert "fall" in minuscula


def test_el_prompt_rechaza_identificadores_de_clinica_externos(prompt):
    minuscula = prompt.lower()
    assert "clínica" in minuscula
    assert "servidor" in minuscula


def test_el_prompt_esta_en_espanol(prompt):
    assert any(caracter in prompt for caracter in "áéíóúñ¿")


# --------------------------------------------------------------------------
# 5. AG-UI generación v2 (§6)
# --------------------------------------------------------------------------


def test_el_servidor_usa_la_api_agui_v2():
    imports = importaciones(arbol("server"))
    assert ("ag_ui_langgraph", "add_langgraph_fastapi_endpoint") in imports
    assert ("copilotkit", "LangGraphAGUIAgent") in imports


def test_el_servidor_no_mezcla_la_api_v1():
    for origen, nombre in importaciones(arbol("server")):
        assert nombre not in API_V1_PROHIBIDA, f"server.py importa la v1 `{nombre}`"
        assert "copilotkit.integrations" not in origen


def test_el_agente_se_llama_revylia_panel():
    from src.panel_agent.prompts import AGENT_NAME

    assert AGENT_NAME == "revylia_panel"
    assert "revylia_panel" in cadenas(arbol("server"))


def test_el_paquete_no_reexporta_modulos_pesados():
    """`import src.panel_agent` no debe arrastrar LangGraph ni AG-UI."""
    assert importaciones(arbol("__init__")) == []


# --------------------------------------------------------------------------
# 6. Capa viva: solo si el entorno tiene las dependencias y `src/panel/`
# --------------------------------------------------------------------------


@pytest.fixture
def tools_modulo():
    return pytest.importorskip(
        "src.panel_agent.tools",
        reason="requiere langchain_core y src/panel/queries.py (A1)",
    )


def test_objetos_de_herramienta_sin_clinic_id(tools_modulo):
    assert len(tools_modulo.PANEL_TOOLS) == len(HERRAMIENTAS_ESPERADAS)
    for herramienta in tools_modulo.PANEL_TOOLS:
        assert herramienta.name in HERRAMIENTAS_ESPERADAS
        assert herramienta.description
        esquema = getattr(herramienta, "args_schema", None)
        campos = set(getattr(esquema, "model_fields", {}) or {})
        assert not campos & ALIAS_DE_CLINICA, (
            f"{herramienta.name} expone un identificador de clínica: {campos}"
        )


def test_la_envoltura_incluye_fuente_filtros_y_momento(tools_modulo):
    respuesta = tools_modulo._resultado([], "revylia.patients", {"status": "active"})
    assert respuesta["data"] == []
    assert respuesta["meta"]["source"] == "revylia.patients"
    assert respuesta["meta"]["filters"] == {"status": "active"}
    assert respuesta["meta"]["generated_at"].endswith("+00:00")
    assert "error" not in respuesta


def test_un_fallo_de_bd_no_se_confunde_con_ausencia_de_datos(
    tools_modulo, monkeypatch
):
    def caida(*_args, **_kwargs):
        raise RuntimeError("conexión rechazada")

    monkeypatch.setattr(tools_modulo, "panel_connection", caida)
    respuesta = tools_modulo.panel_listar_pacientes.invoke({})
    assert respuesta["error"]["type"] == "upstream_unavailable"
    assert "data" not in respuesta
    assert "conexión rechazada" not in respuesta["error"]["message"]


def test_el_clinic_id_llega_a_la_consulta_desde_la_configuracion(
    tools_modulo, monkeypatch
):
    """Camino feliz sin base de datos: la herramienta no expone `clinic_id`,
    pero sí se lo pasa a `src/panel/queries.py` tomándolo del servidor."""
    from contextlib import contextmanager

    recibido = {}

    @contextmanager
    def conexion_falsa(settings=None):
        yield "conexión-de-prueba"

    def lista_falsa(conn, clinic_id, **filtros):
        recibido["conn"] = conn
        recibido["clinic_id"] = clinic_id
        recibido["filtros"] = filtros
        return [{"id": "1", "name": "Ana"}], 1

    monkeypatch.setattr(tools_modulo, "panel_connection", conexion_falsa)
    monkeypatch.setattr(tools_modulo, "list_patients", lista_falsa)

    respuesta = tools_modulo.panel_listar_pacientes.invoke(
        {"status": "active", "limit": 500}
    )

    esperado = tools_modulo.get_panel_settings().revylia_clinic_id
    assert recibido["clinic_id"] == esperado
    assert recibido["conn"] == "conexión-de-prueba"
    assert recibido["filtros"]["limit"] == 100  # §5: recortado al máximo
    assert respuesta["data"] == [{"id": "1", "name": "Ana"}]
    assert respuesta["meta"]["source"] == "revylia.patients"
    assert respuesta["meta"]["filters"] == {"status": "active"}
    assert respuesta["meta"]["total"] == 1
    assert "generated_at" in respuesta["meta"]


def test_las_fechas_de_cita_son_civiles_y_no_se_desplazan(tools_modulo, monkeypatch):
    """§3: las fechas de cita son fechas civiles sin zona. La herramienta debe
    entregar un `date` exacto a `list_appointments`, nunca un `datetime` ni una
    fecha corrida por conversión a UTC o a América/Bogotá."""
    from contextlib import contextmanager
    from datetime import date as Date, datetime as DateTime

    recibido = {}

    @contextmanager
    def conexion_falsa(settings=None):
        yield object()

    def citas_falsas(conn, clinic_id, **filtros):
        recibido.update(filtros)
        return [], 0

    monkeypatch.setattr(tools_modulo, "panel_connection", conexion_falsa)
    monkeypatch.setattr(tools_modulo, "list_appointments", citas_falsas)

    tools_modulo.panel_listar_citas.invoke(
        {"date_from": "2026-09-12", "date_to": "2026-09-19"}
    )

    assert recibido["date_from"] == Date(2026, 9, 12)
    assert recibido["date_to"] == Date(2026, 9, 19)
    for valor in (recibido["date_from"], recibido["date_to"]):
        assert not isinstance(valor, DateTime), "una fecha civil no lleva hora ni zona"

    # El `generated_at` sí es un instante, y va en UTC (§3).
    assert tools_modulo._ahora_utc().endswith("+00:00")


def test_la_disponibilidad_recibe_la_fecha_exacta(tools_modulo, monkeypatch):
    from contextlib import contextmanager
    from datetime import date as Date

    recibido = {}

    @contextmanager
    def conexion_falsa(settings=None):
        yield object()

    def disponibilidad_falsa(conn, clinic_id, day):
        recibido["day"] = day
        return {"date": "2026-09-13", "weekday": 6, "is_open": False, "slots": []}

    monkeypatch.setattr(tools_modulo, "panel_connection", conexion_falsa)
    monkeypatch.setattr(tools_modulo, "get_availability", disponibilidad_falsa)

    respuesta = tools_modulo.panel_consultar_disponibilidad.invoke({"day": "2026-09-13"})
    assert recibido["day"] == Date(2026, 9, 13)
    assert respuesta["meta"]["filters"] == {"day": "2026-09-13"}


def test_sin_resultados_devuelve_lista_vacia_y_no_error(tools_modulo, monkeypatch):
    from contextlib import contextmanager

    @contextmanager
    def conexion_falsa(settings=None):
        yield object()

    monkeypatch.setattr(tools_modulo, "panel_connection", conexion_falsa)
    monkeypatch.setattr(tools_modulo, "list_patients", lambda *a, **k: ([], 0))

    respuesta = tools_modulo.panel_listar_pacientes.invoke({})
    assert respuesta["data"] == []
    assert respuesta["meta"]["total"] == 0
    assert "error" not in respuesta


def test_una_fecha_invalida_es_error_de_validacion(tools_modulo):
    respuesta = tools_modulo.panel_consultar_disponibilidad.invoke({"day": "ayer"})
    assert respuesta["error"]["type"] == "validation_error"


def test_el_limite_se_recorta_a_cien(tools_modulo):
    assert tools_modulo._pagina(5000, 0) == (100, 0)
    with pytest.raises(tools_modulo._DatoInvalido):
        tools_modulo._pagina(0, 0)
    with pytest.raises(tools_modulo._DatoInvalido):
        tools_modulo._pagina(25, -1)


def test_el_grafo_compilado_no_tiene_checkpointer():
    grafo_modulo = pytest.importorskip(
        "src.panel_agent.graph", reason="requiere langgraph y langchain_google_genai"
    )
    from langchain_core.messages import AIMessage

    class ModeloFalso:
        """Doble de Gemini: no hace ninguna llamada de red."""

        def invoke(self, _mensajes):
            return AIMessage(content="respuesta de prueba")

    grafo = grafo_modulo.build_panel_graph(model=ModeloFalso())
    assert getattr(grafo, "checkpointer", None) in (None, False)
