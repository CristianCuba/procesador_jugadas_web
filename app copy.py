import os
import json
import re
import base64
import requests
import urllib.parse
from datetime import datetime, timedelta
import unicodedata

from flask import Flask, render_template, request, jsonify, send_from_directory
import pandas as pd
import numpy as np
from thefuzz import process, fuzz

# --- IMPORTACIÓN DE MÓDULOS Y BLUEPRINTS ---
from diccionario_ocr import (
    cargar_diccionario, 
    agregar_regla, 
    eliminar_regla, 
    aplicar_correcciones_diccionario
)

from ocr_module import ocr_bp
from pikes_processor import pikes_bp
from ocr_futbol_module import ocr_futbol_bp

# ==============================================================================
# 1. INICIALIZACIÓN DE LA APLICACIÓN Y CONFIGURACIÓN
# ==============================================================================

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Registrar todos los Blueprints en la app creada
app.register_blueprint(pikes_bp)
app.register_blueprint(ocr_bp)
app.register_blueprint(ocr_futbol_bp)

JSON_MLB_PATH = 'equipos_mlb_oficiales.json'
JSON_FUTBOL_PATH = 'equipos_futbol_oficiales.json'
JSON_UFC_PATH = 'peleadores_ufc_oficiales.json'
JSON_PIKES_PATH = 'pikeshoy.json'

# ==============================================================================
# 2. CARGA DE BASES DE DATOS Y NORMALIZACIÓN DE NOMBRES (THEFUZZ)
# ==============================================================================

def cargar_json_seguro(path):
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []

def cargar_equipos_mlb():
    return cargar_json_seguro(JSON_MLB_PATH)

def cargar_equipos_futbol():
    return cargar_json_seguro(JSON_FUTBOL_PATH)

def cargar_peleadores_ufc():
    return cargar_json_seguro(JSON_UFC_PATH)

# Preparación global del índice de búsqueda para thefuzz
alias_to_oficial = {}
candidatos_busqueda = []

def inicializar_indice_normalizador():
    global alias_to_oficial, candidatos_busqueda
    
    # Cargar únicamente MLB y Fútbol (UFC excluido del automatch)
    todas_entidades = cargar_equipos_mlb() + cargar_equipos_futbol()
    
    alias_to_oficial.clear()
    candidatos_tmp = set()

    for item in todas_entidades:
        nombre_oficial = item.get("nombre_oficial")
        if not nombre_oficial:
            continue

        aliases = item.get("aliases", [])
        nombres_asociados = set([nombre_oficial] + aliases)

        for alias in nombres_asociados:
            alias_clean = alias.strip().upper()
            alias_to_oficial[alias_clean] = nombre_oficial
            candidatos_tmp.add(alias_clean)

    candidatos_busqueda = list(candidatos_tmp)  

# Inicializar índice al arrancar el servidor
inicializar_indice_normalizador()

SUFIJOS_MERCADO = ["ALTA", "BAJA", "RL", "MLB", "PARLEY", "DIRECTA", "ML", "PAREJO"]

def sanitizar_texto_equipo(texto: str) -> str:
    """
    Elimina acentos, puntos, caracteres especiales, y estandariza espacios.
    Ejemplo: "Atlético-Madrid." -> "ATLETICO MADRID"
    """
    if not texto:
        return ""
    
    # 1. Quitar acentos/tilde
    texto_nfkd = unicodedata.normalize('NFD', texto)
    texto_sin_acentos = "".join([c for c in texto_nfkd if unicodedata.category(c) != 'Mn'])
    
    # 2. Mayúsculas
    texto_upper = texto_sin_acentos.upper()
    
    # 3. Reemplazar guiones, puntos y caracteres especiales por espacios
    texto_limpio = re.sub(r'[^A-Z0-9\s_]', ' ', texto_upper)
    
    # 4. Remover palabras/términos de apuesta comunes que puedan entorpecer
    palabras_basura = [
        r'\bVS\b', r'\bGANA\b', r'\bGANADOR\b', r'\bEMPATE\b', 
        r'\bOVER\b', r'\bUNDER\b', r'\bDIRECTA\b', r'\bPARLEY\b'
    ]
    for pb in palabras_basura:
        texto_limpio = re.sub(pb, '', texto_limpio)
        
    # 5. Normalizar espacios múltiples
    return re.sub(r'\s+', ' ', texto_limpio).strip()


def normalizar_linea_apuesta(cadena_raw: str, umbral: int = 70, logs_list: list = None) -> str:
    """
    Normaliza el nombre del equipo usando un pipeline multi-capa:
    1. Filtro exacto / Mapa directo de alias (Alias -> Oficial)
    2. Limpieza de ruido, acentos y sufijos de mercado
    3. Fuzzy matching con thefuzz como fallback
    """
    def log(msg):
        if logs_list is not None:
            logs_list.append(msg)

    log(f"   🔍 Normalizando: '{cadena_raw}'")

    if not cadena_raw or cadena_raw.upper() == "PARLEY" or not candidatos_busqueda:
        log("      └─ ⏭️ Se omite normalización (Vacío, PARLEY o sin candidatos).")
        return cadena_raw

    # --- PASO 1: Extraer Sufijos (Monto, Mercado, Pikes) ---
    partes = cadena_raw.split("_")
    partes_equipo = []
    partes_sufijo = []

    for p in partes:
        if any(char.isdigit() for char in p) or p.upper() in SUFIJOS_MERCADO or p.startswith(('+', '-')):
            partes_sufijo.append(p)
        else:
            partes_equipo.append(p)

    nombre_bruto = " ".join(partes_equipo).strip()
    
    # --- PASO 2: Sanitización de Texto ---
    nombre_limpio = sanitizar_texto_equipo(nombre_bruto)
    log(f"      ├─ Nombre extraído: '{nombre_bruto}' | Sanitizado: '{nombre_limpio}'")

    if not nombre_limpio:
        log("      └─ ⚠️ Nombre limpio vacío, se conserva original.")
        return cadena_raw

    # --- PASO 3: Búsqueda Exacta Directa en Alias ---
    if nombre_limpio in alias_to_oficial:
        nombre_oficial = alias_to_oficial[nombre_limpio]
        resultado = f"{nombre_oficial}_{'_'.join(partes_sufijo)}" if partes_sufijo else nombre_oficial
        log(f"      └─ ✅ MATCH EXACTO: '{nombre_limpio}' ──> '{nombre_oficial}' | Final: '{resultado}'")
        return resultado

    # --- PASO 4: Fallback con TheFuzz (Fuzzy Matching) ---
    match, score = process.extractOne(
        nombre_limpio, 
        candidatos_busqueda, 
        scorer=fuzz.token_sort_ratio
    )

    if score >= umbral:
        nombre_oficial = alias_to_oficial[match]
        resultado = f"{nombre_oficial}_{'_'.join(partes_sufijo)}" if partes_sufijo else nombre_oficial
        log(f"      └─ 🎯 FUZZY MATCH ({score}%): Match '{match}' ──> Oficial '{nombre_oficial}' | Final: '{resultado}'")
        return resultado

    log(f"      └─ ⚠️ NO RECONOCIDO ({score}% < Umbral {umbral}%). Mejor intento: '{match}'")
    return cadena_raw


# ==============================================================================
# 3. FUNCIONES DE LÓGICA INTERNA (OCR, LIMPIEZA Y MANEJO DE DATOS)
# ==============================================================================
# Lista de palabras clave que representan separadores de deporte/categoría en el Excel
SEPARADORES_DEPORTE = [
    "FUTBOL", "FÚTBOL", "FC", "MLB", "PELOTA", "BEISBOL", "BÉISBOL", 
    "BASKETBALL", "BASKET", "NBA", "UFC", "BOXEO"
]
def limpiar_jugadas(texto_crudo, logs_list: list = None):
    def log(msg):
        if logs_list is not None:
            logs_list.append(msg)

    if pd.isna(texto_crudo) or str(texto_crudo).strip() == '' or str(texto_crudo).strip().lower() == 'nan':
        return pd.Series([np.nan, np.nan, np.nan, np.nan, "Pendiente", False])

    texto = str(texto_crudo).strip()

    # --- OMITIR SEPARADORES DE DEPORTE/CATEGORÍA ---
    # Limpiamos emojis y caracteres especiales para evaluar solo el texto puro
    texto_solo_letras = re.sub(r'[^A-Za-zÁÉÍÓÚáéíóúÑñ]', '', texto).upper()
    
    if texto_solo_letras in SEPARADORES_DEPORTE:
        log(f"🏷️ SEPARADOR DE DEPORTE DETECTADO ('{texto}'): Se omite el procesamiento.")
        return pd.Series([np.nan, np.nan, np.nan, np.nan, "Ignorado", True])

    # 1. Detección de Encabezado (Nombre de Cliente/Jugador)
    match_header = re.search(r'\]\s*Deportes:\s*(.*)', texto, re.IGNORECASE)
    if match_header:
        nombre = match_header.group(1).strip().upper()
        nombre = re.sub(r'[^\w\s]', '', nombre).strip()
        log(f"👤 ENCABEZADO DETECTADO: Jugador '{nombre}'")
        return pd.Series([nombre, np.nan, np.nan, np.nan, "Pendiente", True])

    # 2. Reemplazo de palabras clave de montos
    texto_modificado = re.sub(r'(?i)(\d+)\s*mil\b', r'\g<1>000', texto)

    # 3. Detección de ALTA / BAJA
    tipo_ab = None
    match_ab = re.search(r'\b(ALTA|BAJA)\b', texto_modificado, re.IGNORECASE)
    if match_ab:
        tipo_ab = match_ab.group(1).upper()
        texto_modificado = re.sub(r'\b(ALTA|BAJA)\b', '', texto_modificado, flags=re.IGNORECASE)

    # 4. Extracción de Monto
    numeros_aislados = re.findall(r'\b\d+\b', texto_modificado)
    monto = np.nan
    jugada = texto_modificado.upper()

    if numeros_aislados:
        for num_str in reversed(numeros_aislados):
            if int(num_str) >= 10:
                monto = float(num_str)
                jugada = re.sub(rf'\b{num_str}\b', '', jugada, count=1).strip()
                break

    # 5. Identificación de Parley / Jugadas Múltiples y Extracción de Pikes (Línea)
    es_parley = re.search(r'\b(TRIPLE|TRIPLETE|SESTETA|TRIPLETA|QUINTETO|TRIPLETAS|CUARTETA|CUARTETAS|QUINTETA|QUINTETAS|SEXTETA|SEXTETAS|QUINTA|\d+\s*CON)\b', jugada, re.IGNORECASE)
    if es_parley:
        jugada = "PARLEY"
        linea = np.nan
    else:
        match_linea = re.search(r'([+-]?\d+(?:\.\d+)?)', jugada)
        if match_linea:
            linea = match_linea.group(1)
            jugada = re.sub(r'[+-]?\d+(?:\.\d+)?', '', jugada).strip()
        else:
            tiene_ml_o_parejo = bool(re.search(r'\b(ML|PAREJO)\b', jugada, re.IGNORECASE))
            linea = 'ML' if tiene_ml_o_parejo else '0.0'

        jugada = re.sub(r'\bF[ÚU]TBOL\b', 'FC', jugada, flags=re.IGNORECASE).strip()
        jugada = re.sub(r'\b(ML|RL|PAREJO)\b', '', jugada, flags=re.IGNORECASE).strip()

        tiene_mlb = bool(re.search(r'\bMLB\b', jugada, re.IGNORECASE))
        jugada = re.sub(r'\bMLB\b', '', jugada, flags=re.IGNORECASE).strip()

        # Aplicar reglas del diccionario OCR
        jugada = aplicar_correcciones_diccionario(jugada)

        if tiene_mlb and "MLB" not in jugada:
            jugada = (jugada + " MLB").strip() if jugada else "MLB"

        jugada = re.sub(r'\s+', '_', jugada).strip('_')

        if tipo_ab:
            jugada = f"{jugada}_{tipo_ab}" if jugada else tipo_ab

        # Normalización con Fuzzy Matching (thefuzz)
        jugada = normalizar_linea_apuesta(jugada, logs_list=logs_list)

    log(f"📊 RESULTADO FINAL -> Jugada: '{jugada}' | Monto: {monto} | Línea: {linea}")
    return pd.Series([jugada, monto, linea, np.nan, "Pendiente", False])


# ==============================================================================
# 4. RUTAS Y ENDPOINTS DE LA APLICACIÓN
# ==============================================================================

# Definir la ruta del archivo donde guardaremos el último reporte de logs
RUTA_REPORTE_JSON = 'ultimo_reporte.json'

RUTA_REPORTE_JSON = 'ultimo_reporte.json'

@app.route('/', methods=['GET', 'POST'])
def index():
    jugadas = []
    reporte_detallado = []

    if request.method == 'POST':
        file = next(iter(request.files.values()), None) if request.files else None

        if file and file.filename != '':
            df = pd.read_excel(file)
            primera_columna = df.columns[0]
            jugador_actual = ""

            for i, row in df.iterrows():
                # 1. Asignación garantizada de texto_raw al inicio del bucle
                texto_raw = str(row[primera_columna]).strip()

                # 2. Validación de celda vacía
                if not texto_raw or texto_raw.lower() == 'nan':
                    continue

                logs_fila = []
                
                # 3. Procesar jugada y extraer serie limpia
                serie_limpia = limpiar_jugadas(texto_raw, logs_list=logs_fila)

                jugada_limpia = serie_limpia[0]
                monto_extraido = serie_limpia[1] if pd.notna(serie_limpia[1]) else ''
                linea_extraida = serie_limpia[2] if pd.notna(serie_limpia[2]) else ''
                logro_extraido = serie_limpia[3] if pd.notna(serie_limpia[3]) else ''
                resultado_estado = serie_limpia[4] if pd.notna(serie_limpia[4]) else 'Pendiente'
                es_encabezado = serie_limpia[5]

                # 4. Descarte de separadores de deporte (Si es separador, no guarda en el reporte)
                if es_encabezado and pd.isna(jugada_limpia):
                    continue

                # 5. Categorización del evento para la vista de reportes
                logs_unidos = "".join(logs_fila)
                if es_encabezado:
                    tipo_evento = "CLIENTE"
                elif "NO RECONOCIDO" in logs_unidos:
                    tipo_evento = "ADVERTENCIA"
                else:
                    tipo_evento = "NORMALIZADO"

                # 6. Guardar en el reporte estructurado
                reporte_detallado.append({
                    "fila": i + 1,
                    "raw": texto_raw,
                    "tipo": tipo_evento,
                    "detalles": logs_fila,
                    "resultado": {
                        "jugada": jugada_limpia,
                        "monto": monto_extraido,
                        "linea": linea_extraida
                    }
                })

                # 7. Lógica de asignación a la tabla principal
                if es_encabezado:
                    jugador_actual = jugada_limpia
                    jugadas.append({
                        'jugador': jugador_actual,
                        'jugada': jugada_limpia,
                        'monto': '',
                        'linea': '',
                        'logro': '',
                        'resultado': '',
                        'es_encabezado': True
                    })
                else:
                    jugadas.append({
                        'jugador': jugador_actual,
                        'jugada': jugada_limpia,
                        'monto': monto_extraido,
                        'linea': linea_extraida,
                        'logro': logro_extraido,
                        'resultado': resultado_estado,
                        'es_encabezado': False
                    })

            # Guardar el JSON del último reporte
            ruta_absoluta = os.path.join(app.root_path, RUTA_REPORTE_JSON)
            with open(ruta_absoluta, 'w', encoding='utf-8') as f:
                json.dump(reporte_detallado, f, ensure_ascii=False, indent=2)

    equipos_mlb = cargar_equipos_mlb()
    nombres_oficiales = [eq.get('nombre_oficial') for eq in equipos_mlb if 'nombre_oficial' in eq]

    equipos_futbol = cargar_equipos_futbol()
    nombres_futbol = [eq.get('nombre_oficial') for eq in equipos_futbol if 'nombre_oficial' in eq]

    return render_template(
        'index.html', 
        filas=jugadas, 
        jugadas=jugadas, 
        nombres_oficiales=nombres_oficiales,
        nombres_futbol=nombres_futbol
    )


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

# Mapas y configuraciones auxiliares
MAPA_CIUDADES_MLB = {
    "COLORADO": "ROCKIES",
    "YANKEES": "NEW YORK YANKEES",
    "YANKY": "NEW YORK YANKEES",
    "BOSTON": "RED SOX",
    "DODGERS": "LOS ANGELES DODGERS",
    "CUBS": "CHICAGO CUBS",
    "METS": "NEW YORK METS",
    "ASTROS": "HOUSTON ASTROS"
}

@app.route('/diccionario/agregar', methods=['POST'])
def ruta_agregar_regla():
    data = request.json or request.form
    patron = data.get('patron', '').strip()
    reemplazo = data.get('reemplazo', '').strip()

    if not patron:
        return jsonify({"success": False, "mensaje": "El patrón no puede estar vacío."})

    agregar_regla(patron, reemplazo)
    return jsonify({"success": True, "mensaje": "Regla agregada."})

@app.route('/diccionario/eliminar', methods=['POST'])
def ruta_eliminar_regla():
    data = request.json or request.form
    patron = data.get('patron', '').strip()

    if eliminar_regla(patron):
        return jsonify({"success": True, "mensaje": "Regla eliminada."})
    return jsonify({"success": False, "mensaje": "Regla no encontrada."})


@app.route('/deportes')
def listas_guardadas():
    deporte_activo = request.args.get('deporte', 'mlb').lower()
    
    mlb_list = cargar_equipos_mlb()
    futbol_list = cargar_equipos_futbol()
    ufc_list = cargar_peleadores_ufc()
    
    conteos = {
        'mlb': len(mlb_list),
        'futbol': len(futbol_list),
        'ufc': len(ufc_list)
    }
    
    if deporte_activo == 'futbol':
        lista_mostrar = futbol_list
    elif deporte_activo == 'ufc':
        lista_mostrar = ufc_list
    else:
        lista_mostrar = mlb_list
    
    equipos = []
    for idx, item in enumerate(lista_mostrar, start=1000):
        equipos.append({
            'id': item.get('id', idx),
            'nombre_oficial': item.get('nombre_oficial', 'DESCONOCIDO'),
            'aliases': item.get('aliases', [])
        })
    
    return render_template('deportes.html', 
                           equipos=equipos, 
                           deporte_activo=deporte_activo, 
                           conteos=conteos)

@app.route('/agregar_equivalencia', methods=['POST'])
def agregar_equivalencia():
    try:
        data = request.json or {}
        oficial = data.get('oficial', '').strip().upper()
        alias = data.get('alias', '').strip().upper()

        if not oficial or not alias:
            return jsonify({"success": False, "mensaje": "Faltan datos (equipo oficial o alias)."}), 400

        equipos = cargar_equipos_mlb()
        encontrado = False

        for equipo in equipos:
            if equipo.get('nombre_oficial', '').upper() == oficial:
                aliases = equipo.get('aliases', [])
                if alias not in [a.upper() for a in aliases]:
                    aliases.append(alias)
                    equipo['aliases'] = aliases
                    encontrado = True
                else:
                    return jsonify({"success": True, "mensaje": f"El alias '{alias}' ya existía para {oficial}."})
                break

        if encontrado:
            with open(JSON_MLB_PATH, 'w', encoding='utf-8') as f:
                json.dump(equipos, f, ensure_ascii=False, indent=4)
            
            inicializar_indice_normalizador()
            return jsonify({"success": True, "mensaje": f"Alias '{alias}' guardado exitosamente para {oficial}."})
        else:
            return jsonify({"success": False, "mensaje": f"No se encontró el equipo oficial '{oficial}'."}), 404

    except Exception as e:
        print(f"❌ Error en /agregar_equivalencia: {e}")
        return jsonify({"success": False, "mensaje": str(e)}), 500

@app.route('/agregar_equivalencia_futbol', methods=['POST'])
def agregar_equivalencia_futbol():
    try:
        data = request.json or {}
        oficial = data.get('oficial', '').strip().upper()
        alias = data.get('alias', '').strip().upper()

        if not oficial or not alias:
            return jsonify({"success": False, "mensaje": "Faltan datos (equipo oficial o alias)."}), 400

        equipos = cargar_equipos_futbol()
        encontrado = False

        for equipo in equipos:
            if equipo.get('nombre_oficial', '').upper() == oficial:
                aliases = equipo.get('aliases', [])
                if alias not in [a.upper() for a in aliases]:
                    aliases.append(alias)
                    equipo['aliases'] = aliases
                    encontrado = True
                else:
                    return jsonify({"success": True, "mensaje": f"El alias '{alias}' ya existía para {oficial}."})
                break

        if encontrado:
            with open(JSON_FUTBOL_PATH, 'w', encoding='utf-8') as f:
                json.dump(equipos, f, ensure_ascii=False, indent=4)
            
            inicializar_indice_normalizador()
            return jsonify({"success": True, "mensaje": f"Alias '{alias}' guardado para {oficial}."})
        else:
            return jsonify({"success": False, "mensaje": f"No se encontró el equipo oficial '{oficial}'."}), 404

    except Exception as e:
        print(f"❌ Error en /agregar_equivalencia_futbol: {e}")
        return jsonify({"success": False, "mensaje": str(e)}), 500

@app.route('/importar_raw_futbol', methods=['POST'])
def importar_raw_futbol():
    try:
        data = request.json or {}
        raw_text = data.get('raw_text', '').strip()

        if not raw_text:
            return jsonify({"success": False, "mensaje": "El texto está vacío."}), 400

        equipos_futbol = cargar_equipos_futbol()
        nombres_existentes = {eq.get('nombre_oficial', '').upper() for eq in equipos_futbol}

        lineas = raw_text.splitlines()
        nuevos_agregados = 0
        omitidos = 0
        siguiente_id = 2000 + len(equipos_futbol)

        for linea in lineas:
            linea_limpia = linea.strip().upper()
            if not linea_limpia or len(linea_limpia) < 2:
                continue

            nombre_limpio = re.sub(r'^\d+\s*', '', linea_limpia).strip()

            if not nombre_limpio:
                continue

            nombre_limpio = re.sub(r'\bF[ÚU]TBOL\b', 'FC', nombre_limpio, flags=re.IGNORECASE).strip()

            if nombre_limpio not in nombres_existentes:
                siguiente_id += 1
                nuevo_equipo = {
                    "id": str(siguiente_id),
                    "nombre_oficial": nombre_limpio,
                    "apodo": nombre_limpio,
                    "aliases": [
                        nombre_limpio
                    ]
                }
                equipos_futbol.append(nuevo_equipo)
                nombres_existentes.add(nombre_limpio)
                nuevos_agregados += 1
            else:
                omitidos += 1

        if nuevos_agregados > 0:
            with open(JSON_FUTBOL_PATH, 'w', encoding='utf-8') as f:
                json.dump(equipos_futbol, f, ensure_ascii=False, indent=4)

            inicializar_indice_normalizador()

        return jsonify({
            "success": True, 
            "nuevos": nuevos_agregados, 
            "omitidos": omitidos,
            "mensaje": f"Se agregaron {nuevos_agregados} equipos nuevos bien estructurados."
        })

    except Exception as e:
        print(f"❌ Error en /importar_raw_futbol: {e}")
        return jsonify({"success": False, "mensaje": str(e)}), 500

# ==============================================================================
# BÚSQUEDA Y GUARDADO DE RESULTADOS MLB EN JSON
# ==============================================================================

RUTA_JSON_MARCADORES = 'marcadores_guardados.json'

def obtener_resultados_mlb(fecha_str, logs_audit=None):
    if logs_audit is None:
        logs_audit = []

    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={fecha_str}"
    marcadores = {}

    try:
        response = requests.get(url, timeout=10)
        logs_audit.append(f"⚾ API MLB Status Code: {response.status_code}")

        if response.status_code != 200:
            logs_audit.append(f"❌ Error API MLB: Status {response.status_code}")
            return marcadores

        data = response.json()
        dates = data.get("dates", [])

        if not dates:
            logs_audit.append(f"⚠️ MLB API responded OK pero no hay juegos en la fecha {fecha_str}.")
            return marcadores

        games = dates[0].get("games", [])
        logs_audit.append(f"⚾ Juegos MLB encontrados: {len(games)}")

        for game in games:
            status = game.get("status", {}).get("detailedState", "Final")
            teams = game.get("teams", {})

            away = teams.get("away", {})
            home = teams.get("home", {})

            raw_away = away.get("team", {}).get("name", "").strip()
            raw_home = home.get("team", {}).get("name", "").strip()

            if not raw_away or not raw_home:
                continue

            # Normalización segura
            try:
                away_team = normalizar_linea_apuesta(raw_away) if 'normalizar_linea_apuesta' in globals() else raw_away.upper()
                home_team = normalizar_linea_apuesta(raw_home) if 'normalizar_linea_apuesta' in globals() else raw_home.upper()
            except Exception:
                away_team = raw_away.upper()
                home_team = raw_home.upper()

            away_score = str(away.get("score", 0))
            home_score = str(home.get("score", 0))

            texto_juego = f"{away_team} {away_score} - {home_score} {home_team} ({status})"

            objeto_resultado = {
                "juego": texto_juego,
                "estado": status,
                "equipo1": away_team,
                "marcador_equipo1": away_score,
                "equipo2": home_team,
                "marcador_equipo2": home_score
            }

            dict_away = {"jugada": away_team, **objeto_resultado}
            dict_home = {"jugada": home_team, **objeto_resultado}

            marcadores[away_team] = dict_away
            marcadores[home_team] = dict_home

    except Exception as e:
        logs_audit.append(f"💥 Excepción al consultar MLB API: {str(e)}")

    return marcadores

import requests
import json
import os
import re
from datetime import datetime, timedelta
from flask import jsonify, render_template, request

RUTA_REPORTE_MARCADORES = 'reporte_marcadores.json'

def obtener_resultados_futbol_api(fecha_str, logs_audit=None, partidos_audit=None):
    if logs_audit is None: logs_audit = []
    if partidos_audit is None: partidos_audit = []

    url = f"https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d={fecha_str}&s=Soccer"
    marcadores = {}

    try:
        response = requests.get(url, timeout=12)
        logs_audit.append(f"⚽ API Fútbol Status Code: {response.status_code}")
        
        if response.status_code != 200:
            logs_audit.append(f"❌ Error API Fútbol: Status {response.status_code}")
            return marcadores

        data = response.json()
        events = data.get("events") or []
        logs_audit.append(f"⚽ Eventos/Partidos de Fútbol recibidos: {len(events)}")

        for idx, event in enumerate(events):
            # 1. EXTRAER IDs ÚNICOS DE LOS EQUIPOS
            id_home_team = event.get("idHomeTeam")
            id_away_team = event.get("idAwayTeam")

            raw_home = event.get("strHomeTeam", "").strip()
            raw_away = event.get("strAwayTeam", "").strip()
            
            home_score = str(event.get("intHomeScore") if event.get("intHomeScore") is not None else "0")
            away_score = str(event.get("intAwayScore") if event.get("intAwayScore") is not None else "0")
            
            str_status = event.get("strStatus", "")
            status = "Final" if str_status in ["Match Finished", "FT", "AET", "AP"] else str_status or "In Progress"

            home_team = normalizar_linea_apuesta(raw_home) if 'normalizar_linea_apuesta' in globals() and raw_home else raw_home.upper()
            away_team = normalizar_linea_apuesta(raw_away) if 'normalizar_linea_apuesta' in globals() and raw_away else raw_away.upper()

            # Guardar en auditoría con IDs de equipo
            partidos_audit.append({
                "index": idx + 1,
                "fixture_id": event.get("idEvent"),
                "liga_id": event.get("strLeague"),
                "home": home_team or "SIN NOMBRE",
                "id_home_team": id_home_team,
                "away": away_team or "SIN NOMBRE",
                "id_away_team": id_away_team,
                "home_score": home_score,
                "away_score": away_score,
                "status_raw": str_status,
                "estado_evaluado": status,
                "valido": bool(home_team and away_team)
            })

            if not raw_home or not raw_away:
                continue

            texto_juego = f"{away_team} {away_score} - {home_score} {home_team} ({status})"

            # 2. OBJETO DE RESULTADO CON LOS IDs DE LOS EQUIPOS INCLUIDOS
            objeto_resultado = {
                "juego": texto_juego,
                "estado": status,
                "equipo1": away_team,
                "id_equipo1": id_away_team,
                "marcador_equipo1": away_score,
                "equipo2": home_team,
                "id_equipo2": id_home_team,
                "marcador_equipo2": home_score
            }

            dict_away = {"jugada": away_team, **objeto_resultado}
            dict_home = {"jugada": home_team, **objeto_resultado}

            marcadores[away_team] = dict_away
            marcadores[home_team] = dict_home

    except Exception as e:
        logs_audit.append(f"💥 Excepción en Fútbol API: {str(e)}")

    return marcadores

@app.route('/guardar_marcadores_api', methods=['POST'])
def guardar_marcadores_api():
    logs_audit = []
    partidos_futbol_audit = []
    
    try:
        data = request.json or {}
        opcion_fecha = str(data.get('fecha_consulta', 'ayer')).strip().lower()

        fecha_obj = datetime.now() if opcion_fecha == 'hoy' else datetime.now() - timedelta(days=1)
        fecha_str = fecha_obj.strftime('%Y-%m-%d')
        logs_audit.append(f"📅 Consultando marcadores para la fecha: {fecha_str}")

        # 1. Cargar MLB de forma independiente
        marcadores_mlb = obtener_resultados_mlb(fecha_str, logs_audit)
        cant_mlb = len(marcadores_mlb)
        logs_audit.append(f"⚾ Equipos MLB cargados exitosamente: {cant_mlb}")

        # 2. Cargar Fútbol de forma independiente
        marcadores_futbol = obtener_resultados_futbol_api(fecha_str, logs_audit, partidos_futbol_audit)
        cant_futbol = len(marcadores_futbol) if isinstance(marcadores_futbol, dict) else 0
        logs_audit.append(f"⚽ Equipos Fútbol cargados exitosamente: {cant_futbol}")

        # 3. Fusionar diccionarios de forma segura
        marcadores_totales = {}
        if isinstance(marcadores_mlb, dict):
            marcadores_totales.update(marcadores_mlb)
        if isinstance(marcadores_futbol, dict):
            marcadores_totales.update(marcadores_futbol)

        # 4. Guardar archivo de marcadores
        ruta_absoluta = os.path.join(app.root_path, RUTA_JSON_MARCADORES)
        with open(ruta_absoluta, 'w', encoding='utf-8') as f:
            json.dump(marcadores_totales, f, ensure_ascii=False, indent=4)

        # 5. Guardar reporte de auditoría
        with open(os.path.join(app.root_path, RUTA_REPORTE_MARCADORES), 'w', encoding='utf-8') as f:
            json.dump({
                "fecha_consulta": fecha_str,
                "total_mlb": cant_mlb,
                "total_futbol": cant_futbol,
                "total_guardado": len(marcadores_totales),
                "logs": logs_audit,
                "partidos_futbol_desglose": partidos_futbol_audit,
                "muestra_partidos": list(marcadores_totales.values())[:15]
            }, f, ensure_ascii=False, indent=2)

        return jsonify({
            "success": True,
            "mensaje": f"Marcadores guardados correctamente para el {fecha_str}.",
            "total_equipos": len(marcadores_totales),
            "cant_mlb": cant_mlb,
            "cant_futbol": cant_futbol
        })

    except Exception as e:
        error_detal = traceback.format_exc()
        logs_audit.append(f"💥 ERROR GENERAL EN GUARDAR MARCADORES:\n{error_detal}")
        return jsonify({"success": False, "mensaje": str(e), "trace": error_detal}), 500

def evaluar_resultado_jugada(jugada_raw, linea_raw, datos_partido):
    # Modificado para aceptar 'Final', 'Completed' y 'Match Finished'
    if not datos_partido or datos_partido.get("estado") not in ["Final", "Completed", "Match Finished"]:
        return "Pendiente"

    jugada_upper = str(jugada_raw).upper().strip()

    try:
        match_linea = re.search(r'([+-]?\d+(?:\.\d+)?)', str(linea_raw))
        val_linea = float(match_linea.group(1)) if match_linea else 0.0
    except (ValueError, TypeError):
        val_linea = 0.0

    try:
        eq1 = datos_partido.get("equipo1", "").strip().upper()
        sc1 = float(datos_partido.get("marcador_equipo1", 0))

        eq2 = datos_partido.get("equipo2", "").strip().upper()
        sc2 = float(datos_partido.get("marcador_equipo2", 0))
    except (ValueError, TypeError):
        return "-"

    total_goles = sc1 + sc2

    if any(kw in jugada_upper for kw in ["ALTA", "OVER", "_A"]):
        if total_goles > val_linea: return "G"
        elif total_goles < val_linea: return "P"
        else: return "T"

    if any(kw in jugada_upper for kw in ["BAJA", "UNDER", "_B"]):
        if total_goles < val_linea: return "G"
        elif total_goles > val_linea: return "P"
        else: return "T"

    carreras_mi_equipo, carreras_rival = sc2, sc1
    palabras_jugada = [p for p in jugada_upper.replace('_', ' ').split() if len(p) > 2]
    if any(p in eq1 for p in palabras_jugada):
        carreras_mi_equipo, carreras_rival = sc1, sc2

    marcador_ajustado = carreras_mi_equipo + val_linea

    if marcador_ajustado > carreras_rival: return "G"
    elif marcador_ajustado < carreras_rival: return "P"
    else: return "T"

@app.route('/pintar_resultados_tabla', methods=['POST'])
def pintar_resultados_tabla():
    try:
        data = request.json or {}
        filas = data.get('filas', [])

        ruta_json = os.path.join(app.root_path, RUTA_JSON_MARCADORES)

        if not os.path.exists(ruta_json):
            return jsonify({
                "success": False, 
                "mensaje": "No se encontró el archivo JSON con los marcadores."
            }), 400

        with open(ruta_json, 'r', encoding='utf-8') as f:
            resultados_mlb = json.load(f)

        for fila in filas:
            if not isinstance(fila, dict) or fila.get('es_encabezado'):
                continue

            jugada_raw = str(fila.get('jugada', '')).strip().upper()
            linea_raw = str(fila.get('linea', '0.0')).strip()

            if not jugada_raw or jugada_raw in ["PARLEY", "MLB"]:
                fila['resultado'] = "-"
                continue

            equipo_limpio = re.sub(
                r'(_|\s+)(MLB|FUTBOL|BÉISBOL|ALTA|BAJA|OVER|UNDER|ML|RL|A|B)$', 
                '', jugada_raw, flags=re.IGNORECASE
            ).strip()

            datos_partido = None
            if equipo_limpio in resultados_mlb:
                datos_partido = resultados_mlb[equipo_limpio]
            else:
                for eq_key, datos in resultados_mlb.items():
                    if eq_key and (eq_key in equipo_limpio or equipo_limpio in eq_key):
                        datos_partido = datos
                        break

            if datos_partido:
                fila['resultado'] = evaluar_resultado_jugada(jugada_raw, linea_raw, datos_partido)
            else:
                fila['resultado'] = "Sin juego"

        return jsonify({"success": True, "filas": filas})

    except Exception as e:
        print(f"❌ Error al evaluar resultados: {e}")
        return jsonify({"success": False, "mensaje": str(e)}), 500

CARPETA_FUTBOL = 'pikes_futbol'

@app.route('/obtener_pikes_futbol', methods=['GET'])
def obtener_pikes_futbol():
    try:
        todos_los_pikes = []

        if not os.path.exists(CARPETA_FUTBOL):
            return jsonify({"success": True, "pikes": []})

        for archivo in os.listdir(CARPETA_FUTBOL):
            if archivo.endswith('.json'):
                ruta_completa = os.path.join(CARPETA_FUTBOL, archivo)
                try:
                    with open(ruta_completa, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                        if isinstance(data, list):
                            todos_los_pikes.extend(data)
                        elif isinstance(data, dict):
                            pikes = data.get('pikes') or data.get('jugadas') or []
                            todos_los_pikes.extend(pikes)
                except Exception as e:
                    print(f"Error leyendo archivo de fútbol {archivo}: {e}")

        return jsonify({"success": True, "pikes": todos_los_pikes})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


#-------------REPORTES--------------------


@app.route('/reporte')
def ver_reporte():
    ruta_absoluta = os.path.join(app.root_path, RUTA_REPORTE_JSON)
    reporte_datos = []
    
    if os.path.exists(ruta_absoluta):
        with open(ruta_absoluta, 'r', encoding='utf-8') as f:
            try:
                reporte_datos = json.load(f)
            except Exception:
                reporte_datos = []

    return render_template('reporte.html', reporte=reporte_datos)
@app.route('/reporte_pikes_futbol')
def ver_reporte_pikes_futbol():
    ruta_absoluta = os.path.join(app.root_path, 'reporte_pikes_futbol.json')
    datos = {}
    if os.path.exists(ruta_absoluta):
        with open(ruta_absoluta, 'r', encoding='utf-8') as f:
            try: datos = json.load(f)
            except Exception: pass
    return render_template('reporte_pikes.html', datos=datos)


@app.route('/reporte_marcadores')
def ver_reporte_marcadores():
    ruta_absoluta = os.path.join(app.root_path, RUTA_REPORTE_MARCADORES)
    datos = {}
    if os.path.exists(ruta_absoluta):
        with open(ruta_absoluta, 'r', encoding='utf-8') as f:
            try: datos = json.load(f)
            except Exception: pass
    return render_template('reporte_marcadores.html', datos=datos)





    #-----------------gestor de equipos-------

    import urllib.parse

RUTA_LIGAS_FUTBOL = 'ligas_futbol_api.json'
RUTA_EQUIPOS_FUTBOL = 'equipos_futbol_api.json'

@app.route('/obtener_ligas_futbol', methods=['GET'])
def obtener_ligas_futbol():
    url = "https://www.thesportsdb.com/api/v1/json/3/all_leagues.php"
    ruta_absoluta = os.path.join(app.root_path, 'ligas_futbol_api.json')
    ligas_futbol = []

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            all_leagues = data.get("leagues", []) or []
            
            for league in all_leagues:
                if league.get("strSport") == "Soccer":
                    ligas_futbol.append({
                        "id_liga": league.get("idLeague"),
                        "nombre_liga": league.get("strLeague"),
                        "alternate": league.get("strLeagueAlternate")
                    })

            ligas_futbol.sort(key=lambda x: x["nombre_liga"])

            with open(ruta_absoluta, 'w', encoding='utf-8') as f:
                json.dump(ligas_futbol, f, ensure_ascii=False, indent=4)

            return jsonify({"success": True, "total": len(ligas_futbol), "ligas": ligas_futbol})
        else:
            return jsonify({"success": False, "mensaje": f"Error API externa: Status {response.status_code}"}), 400

    except Exception as e:
        print("Error en /obtener_ligas_futbol:", traceback.format_exc())
        return jsonify({"success": False, "mensaje": str(e)}), 500


@app.route('/importar_equipos_por_liga', methods=['POST'])
def importar_equipos_por_liga():
    try:
        data = request.json or {}
        nombre_liga = data.get("nombre_liga", "").strip()

        if not nombre_liga:
            return jsonify({"success": False, "mensaje": "Se requiere el nombre de la liga"}), 400

        liga_encoded = urllib.parse.quote(nombre_liga)
        url = f"https://www.thesportsdb.com/api/v1/json/3/search_all_teams.php?l={liga_encoded}"

        response = requests.get(url, timeout=12)
        if response.status_code != 200:
            return jsonify({"success": False, "mensaje": f"Error API externa: Status {response.status_code}"}), 400

        data_json = response.json()
        teams = data_json.get("teams") or []

        if not teams:
            return jsonify({"success": True, "mensaje": f"No se encontraron equipos para: {nombre_liga}", "nuevos_guardados": 0, "equipos_recibidos": 0, "total_equipos_db": 0})

        ruta_absoluta = os.path.join(app.root_path, 'equipos_futbol_api.json')
        equipos_db = {}
        if os.path.exists(ruta_absoluta):
            try:
                with open(ruta_absoluta, 'r', encoding='utf-8') as f:
                    equipos_db = json.load(f)
            except Exception:
                equipos_db = {}

        nuevos_agregados = 0
        for team in teams:
            id_team = team.get("idTeam")
            team_name = team.get("strTeam", "").strip()

            if id_team and id_team not in equipos_db:
                equipos_db[id_team] = {
                    "id_equipo": id_team,
                    "nombre_oficial": team_name,
                    "liga": nombre_liga,
                    "pais": team.get("strCountry", ""),
                    "insignia": team.get("strBadge", "")
                }
                nuevos_agregados += 1

        with open(ruta_absoluta, 'w', encoding='utf-8') as f:
            json.dump(equipos_db, f, ensure_ascii=False, indent=4)

        return jsonify({
            "success": True,
            "liga": nombre_liga,
            "equipos_recibidos": len(teams),
            "nuevos_guardados": nuevos_agregados,
            "total_equipos_db": len(equipos_db)
        })

    except Exception as e:
        print("Error en /importar_equipos_por_liga:", traceback.format_exc())
        return jsonify({"success": False, "mensaje": str(e)}), 500

@app.route('/gestor_equipos')
def gestor_equipos_view():
    return render_template('gestor_equipos.html')
# ==============================================================================
# 5. EJECUCIÓN
# ==============================================================================
if __name__ == '__main__':
    app.run(debug=True)