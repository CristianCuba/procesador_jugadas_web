import os
import json
import re
from datetime import datetime
from flask import Blueprint, request, jsonify

# 1. Definir el Blueprint
pikes_bp = Blueprint('pikes_bp', __name__)

# 2. Configurar la carpeta donde se guardará un JSON por cada foto
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CARPETA_PIKES = os.path.join(BASE_DIR, 'pikes_guardados')

# Aseguramos que la carpeta exista desde el inicio
os.makedirs(CARPETA_PIKES, exist_ok=True)


def limpiar_nombre_equipo(texto):
    """
    Limpia sufijos de ligas, mercados y espacios para facilitar la coincidencia.
    """
    if not texto:
        return ""
    texto = str(texto).upper().strip()
    sufijos = ["_RL", "_MLB", "_ML", "_ALTA", "_BAJA", "_OVER", "_UNDER", " RL", " MLB"]
    for sufijo in sufijos:
        texto = texto.replace(sufijo, "")
    return texto.strip()


def guardar_pikes_foto(nuevos_pikes):
    if not nuevos_pikes:
        return 0

    os.makedirs(CARPETA_PIKES, exist_ok=True)

    if isinstance(nuevos_pikes, dict):
        nuevos_pikes = [nuevos_pikes]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    nombre_archivo = f"pikes_{timestamp}.json"
    ruta_archivo = os.path.join(CARPETA_PIKES, nombre_archivo)

    try:
        with open(ruta_archivo, 'w', encoding='utf-8') as f:
            json.dump({"pikes": nuevos_pikes}, f, ensure_ascii=False, indent=4)
        print(f"✅ Se guardó el lote en: {nombre_archivo}")
        return len(nuevos_pikes)
    except Exception as e:
        print(f"❌ Error al guardar {nombre_archivo}: {e}")
        return 0


def cargar_todos_los_pikes():
    """
    LEE TODOS LOS JSON DENTRO DE /pikes_guardados/ Y LOS UNIFICA EN MEMORIA.
    """
    mapa_id = {}
    mapa_nombre = {}

    if not os.path.exists(CARPETA_PIKES):
        return mapa_id, mapa_nombre

    archivos = [f for f in os.listdir(CARPETA_PIKES) if f.endswith('.json')]

    for archivo in archivos:
        ruta_completa = os.path.join(CARPETA_PIKES, archivo)
        try:
            with open(ruta_completa, 'r', encoding='utf-8') as f:
                datos = json.load(f)
                lista_pikes = datos.get("pikes", [])

                for item in lista_pikes:
                    id_p = str(item.get("id", "")).strip()
                    nombre_p = str(item.get("nombre", "") or item.get("equipo", "")).upper().strip()

                    datos_equipo = {
                        "pike1": str(item.get("pike1", "")).strip(), # Cuota ML
                        "pike2": str(item.get("pike2", "")).strip(), # Cuota RL
                        "pike3": str(item.get("pike3", "")).strip()  # Hándicap RL / Línea A/B
                    }

                    if id_p:
                        mapa_id[id_p] = datos_equipo
                    if nombre_p:
                        mapa_nombre[nombre_p] = datos_equipo
        except Exception as e:
            print(f"⚠️ Error leyendo {archivo}: {e}")

    return mapa_id, mapa_nombre


# ==========================================
# 1. ENDPOINT PARA GUARDAR DESDE CÁMARA / GEMINI
# ==========================================
@pikes_bp.route('/guardar_pikes', methods=['POST'])
def guardar_pikes():
    try:
        data = request.json or {}
        pikes = data.get('pikes', []) or data.get('filas', [])

        if not pikes:
            return jsonify({"success": False, "mensaje": "No se recibieron pikes."}), 400

        guardados = guardar_pikes_foto(pikes)

        return jsonify({
            "success": True,
            "mensaje": f"Se guardó el lote con {guardados} pikes correctamente."
        })
    except Exception as e:
        return jsonify({"success": False, "mensaje": f"Error guardando pikes: {str(e)}"}), 500


# ==========================================
# 2. ENDPOINT PARA PIKES MONEYLINE (ML)
# ==========================================
@pikes_bp.route('/procesar_pikes_ml', methods=['POST'])
def procesar_pikes_ml():
    try:
        data = request.json or {}
        filas = data.get('filas', [])

        if not filas:
            return jsonify({"success": False, "mensaje": "No se recibieron filas."}), 400

        mapa_id, mapa_nombre = cargar_todos_los_pikes()

        coincidencias_aplicadas = 0

        for fila in filas:
            jugada_raw = str(fila.get("jugada", "")).upper().strip()
            jugada_limpia = limpiar_nombre_equipo(jugada_raw)
            id_equipo = str(fila.get("id", "")).strip()

            datos_eq = None

            if id_equipo in mapa_id:
                datos_eq = mapa_id[id_equipo]
            else:
                for nombre_eq, info in mapa_nombre.items():
                    nombre_limpio = limpiar_nombre_equipo(nombre_eq)
                    if nombre_limpio and (nombre_limpio in jugada_limpia or jugada_limpia in nombre_limpio):
                        datos_eq = info
                        break

            if datos_eq and datos_eq.get("pike1"):
                fila["pike1"] = datos_eq["pike1"]
                coincidencias_aplicadas += 1

        return jsonify({
            "success": True,
            "mensaje": f"Se asignaron {coincidencias_aplicadas} pikes ML.",
            "filas": filas
        })

    except Exception as e:
        return jsonify({"success": False, "mensaje": f"Error interno: {str(e)}"}), 500


# ==========================================
# 3. ENDPOINT PARA PIKES RUNLINE (RL)
# ==========================================
@pikes_bp.route('/procesar_pikes_rl', methods=['POST'])
def procesar_pikes_rl():
    try:
        data = request.json or {}
        filas = data.get('filas', [])

        if not filas:
            return jsonify({"success": False, "mensaje": "No se recibieron filas."}), 400

        mapa_id, mapa_nombre = cargar_todos_los_pikes()

        coincidencias_aplicadas = 0

        for fila in filas:
            jugada_raw = str(fila.get("jugada", "")).upper().strip()
            jugada_limpia = limpiar_nombre_equipo(jugada_raw)
            id_equipo = str(fila.get("id", "")).strip()
            linea_actual = str(fila.get("linea_actual", "")).upper().strip()

            if "ML" in linea_actual:
                continue

            datos_eq = None

            if id_equipo in mapa_id:
                datos_eq = mapa_id[id_equipo]
            else:
                for nombre_eq, info in mapa_nombre.items():
                    nombre_limpio = limpiar_nombre_equipo(nombre_eq)
                    if nombre_limpio and (nombre_limpio in jugada_limpia or jugada_limpia in nombre_limpio):
                        datos_eq = info
                        break

            if datos_eq:
                raw_pike3 = datos_eq.get("pike3", "").strip()
                cuota_rl = datos_eq.get("pike2", "").strip()

                if raw_pike3.startswith("-") or raw_pike3.startswith("+"):
                    linea_final = raw_pike3
                else:
                    linea_final = "+1.5"

                fila["linea_rl"] = linea_final
                fila["cuota_rl"] = cuota_rl
                coincidencias_aplicadas += 1

        return jsonify({
            "success": True,
            "mensaje": f"Se asignaron {coincidencias_aplicadas} pikes RL.",
            "filas": filas
        })

    except Exception as e:
        return jsonify({"success": False, "mensaje": f"Error interno: {str(e)}"}), 500



# ==========================================
# 4. ENDPOINT PARA ALTAS Y BAJAS (OVER / UNDER)
# ==========================================
@pikes_bp.route('/procesar_pikes_altas_bajas', methods=['POST'])
def procesar_pikes_altas_bajas():
    try:
        data = request.json or {}
        filas = data.get('filas', [])

        if not filas:
            return jsonify({"success": False, "mensaje": "No se recibieron filas."}), 400

        mapa_id, mapa_nombre = cargar_todos_los_pikes()

        # Buscar el archivo marcadores_guardados.json tanto en BASE_DIR como en su carpeta padre
        ruta_1 = os.path.join(BASE_DIR, 'marcadores_guardados.json')
        ruta_2 = os.path.join(os.path.dirname(BASE_DIR), 'marcadores_guardados.json')
        ruta_json_marcadores = ruta_1 if os.path.exists(ruta_1) else ruta_2

        resultados_mlb = {}
        if os.path.exists(ruta_json_marcadores):
            try:
                with open(ruta_json_marcadores, 'r', encoding='utf-8') as f:
                    resultados_mlb = json.load(f)
                print(f"✅ Marcadores cargados correctamente ({len(resultados_mlb)} equipos encontrados).")
            except Exception as e:
                print(f"⚠️ Error cargando marcadores_guardados.json: {e}")
        else:
            print(f"❌ ERROR: No se encontró 'marcadores_guardados.json' en '{ruta_1}' ni en '{ruta_2}'")

        coincidencias = 0

        # Normalización estricta
        def normalizar_nombre(texto):
            if not texto:
                return ""
            texto = str(texto).upper().strip()
            texto = texto.replace("_", " ")
            basura = ["MLB", "ALTA", "BAJA", "OVER", "UNDER", "RL", "ML", "FUTBOL", "BEISBOL"]
            palabras = texto.split()
            palabras_limpias = [p for p in palabras if p not in basura]
            return " ".join(palabras_limpias).strip()

        # Helper para obtener pikes
        def obtener_datos_pikes(id_eq, nombre_eq):
            if id_eq and id_eq in mapa_id:
                return mapa_id[id_eq]
            
            nombre_norm = normalizar_nombre(nombre_eq)
            if not nombre_norm:
                return None

            for k_nombre, info in mapa_nombre.items():
                k_norm = normalizar_nombre(k_nombre)
                if k_norm and (k_norm in nombre_norm or nombre_norm in k_norm):
                    return info
            return None

        for fila in filas:
            jugada_raw = str(fila.get("jugada", "")).upper().strip()

            # Normalizar la jugada
            equipo_puro = normalizar_nombre(jugada_raw)
            id_equipo = str(fila.get("id", "")).strip()

            print(f"\n[INICIO] Jugada raw: '{jugada_raw}' -> Equipo normalizado: '{equipo_puro}'")

            # Buscar si el propio equipo tiene el pike3
            datos_eq = obtener_datos_pikes(id_equipo, equipo_puro)
            raw_pike3 = datos_eq.get("pike3", "").strip() if datos_eq else ""

            linea_encontrada = None

            # CASO A: El equipo tiene la línea directa (ej: "8.5")
            if raw_pike3 and not raw_pike3.startswith("-") and not raw_pike3.startswith("+"):
                linea_encontrada = raw_pike3
                print(f" 🟢 Encontrado pike3 directo: '{linea_encontrada}'")

            # CASO B: No la tiene -> Buscar al rival en marcadores_guardados.json
            else:
                print(f" 🟡 El equipo no tiene pike3 directo (Valor: '{raw_pike3}'). Buscando rival en marcadores_guardados.json...")
                datos_partido = None
                
                # Búsqueda por coincidencia de nombre normalizado
                for eq_key, info_partido in resultados_mlb.items():
                    eq_key_norm = normalizar_nombre(eq_key)
                    if eq_key_norm and (eq_key_norm == equipo_puro or eq_key_norm in equipo_puro or equipo_puro in eq_key_norm):
                        datos_partido = info_partido
                        break

                if datos_partido:
                    eq1 = datos_partido.get("equipo1", "").strip()
                    eq2 = datos_partido.get("equipo2", "").strip()

                    eq1_norm = normalizar_nombre(eq1)
                    
                    if eq1_norm and (eq1_norm in equipo_puro or equipo_puro in eq1_norm):
                        nombre_rival = eq2
                    else:
                        nombre_rival = eq1

                    print(f" ✅ Partido hallado en JSON. Rival identificado: '{nombre_rival}'")

                    # Buscamos el pike3 del rival
                    datos_rival = obtener_datos_pikes(None, nombre_rival)

                    if datos_rival:
                        pike3_rival = datos_rival.get("pike3", "").strip()
                        print(f" 🔍 Pike3 del rival '{nombre_rival}': '{pike3_rival}'")
                        if pike3_rival and not pike3_rival.startswith("-") and not pike3_rival.startswith("+"):
                            linea_encontrada = pike3_rival
                            print(f" 🟢 Línea asignada desde el rival: '{linea_encontrada}'")
                        else:
                            print(f" ❌ El rival '{nombre_rival}' tampoco tiene una línea válida de Altas/Bajas.")
                    else:
                        print(f" ❌ No se encontraron pikes guardados para el rival '{nombre_rival}'.")
                else:
                    print(f" ❌ NO se encontró el partido de '{equipo_puro}' en marcadores_guardados.json.")

            # Asignar a la fila
            if linea_encontrada:
                fila["linea_ab"] = linea_encontrada
                fila["cuota_ab"] = "-120"
                coincidencias += 1

        return jsonify({
            "success": True,
            "mensaje": f"Se asignaron {coincidencias} pikes de Altas/Bajas.",
            "filas": filas
        })

    except Exception as e:
        print(f"💥 Error en procesar_pikes_altas_bajas: {str(e)}")
        return jsonify({"success": False, "mensaje": f"Error interno: {str(e)}"}), 500


#PROCESA LOS PIKES DE FUTBOL RL 

import os
import json
import traceback
from flask import Blueprint, request, jsonify

# pikes_bp = Blueprint('pikes_bp', __name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

import traceback

RUTA_REPORTE_PIKES = 'reporte_pikes_futbol.json'

@pikes_bp.route('/procesar_pikes_rl_futbol', methods=['POST'])
def procesar_pikes_rl_futbol():
    try:
        data = request.json or {}
        filas = data.get('filas', [])
        reporte_pikes = []  # <--- Array para la auditoría en la vista web

        if not filas:
            return jsonify({"success": False, "mensaje": "No se recibieron filas."}), 400

        # 1. CARGAR PIKES
        carp_pikes_futbol = os.path.join(BASE_DIR, 'pikes_futbol')
        mapa_id, mapa_nombre = {}, {}
        archivo_cargado_nombre = "Ninguno"

        if os.path.exists(carp_pikes_futbol):
            archivos_json = [
                os.path.join(carp_pikes_futbol, f) 
                for f in os.listdir(carp_pikes_futbol) if f.endswith('.json')
            ]
            if archivos_json:
                archivo_mas_reciente = max(archivos_json, key=os.path.getmtime)
                archivo_cargado_nombre = os.path.basename(archivo_mas_reciente)

                with open(archivo_mas_reciente, 'r', encoding='utf-8') as f:
                    datos_pikes = json.load(f)
                    lista_pikes = datos_pikes if isinstance(datos_pikes, list) else datos_pikes.get('pikes', [])
                    for item in lista_pikes:
                        p_id = str(item.get('id', '')).strip()
                        p_nombre = str(item.get('equipo', '') or item.get('nombre', '')).strip().upper()
                        if p_id: mapa_id[p_id] = item
                        if p_nombre: mapa_nombre[p_nombre] = item

        # 2. CARGAR MARCADORES
        ruta_json_marcadores = os.path.join(BASE_DIR, 'marcadores_guardados.json')
        resultados_guardados = {}
        if os.path.exists(ruta_json_marcadores):
            try:
                with open(ruta_json_marcadores, 'r', encoding='utf-8') as f:
                    resultados_guardados = json.load(f)
            except Exception as e:
                pass

        coincidencias = 0

        def normalizar_nombre(texto):
            if not texto: return ""
            texto = str(texto).upper().strip().replace("_", " ")
            basura = ["MLB", "ALTA", "BAJA", "OVER", "UNDER", "RL", "ML", "FUTBOL", "BEISBOL", "FK", "FC", "CF", "CD"]
            palabras = texto.split()
            palabras_limpias = [p for p in palabras if p not in basura]
            return " ".join(palabras_limpias).strip()

        def obtener_datos_pikes(id_eq, nombre_eq):
            if id_eq and id_eq in mapa_id:
                return mapa_id[id_eq]
            nombre_norm = normalizar_nombre(nombre_eq)
            if not nombre_norm: return None
            for k_nombre, info in mapa_nombre.items():
                k_norm = normalizar_nombre(k_nombre)
                if k_norm and (k_norm in nombre_norm or nombre_norm in k_norm):
                    return info
            return None

        def invertir_signo(linea):
            linea = str(linea).strip()
            if linea.startswith("-"): return "+" + linea[1:]
            elif linea.startswith("+"): return "-" + linea[1:]
            return None

        # 3. PROCESAMIENTO CON AUDITORÍA REGISTRADA
        for idx, fila in enumerate(filas):
            logs_fila = []
            jugada_raw = str(fila.get("jugada", "")).upper().strip()
            id_equipo = str(fila.get("id", "")).strip()
            equipo_puro = normalizar_nombre(jugada_raw)

            logs_fila.append(f"🔍 Raw: '{jugada_raw}' | Normalizado: '{equipo_puro}' | ID: {id_equipo or 'Sin ID'}")

            # Filtro Alta/Baja
            if any(palabra in jugada_raw for palabra in ["ALTA", "BAJA", "OVER", "UNDER"]):
                logs_fila.append("⏭️ OMITIDA: Es una jugada de Alta/Baja.")
                reporte_pikes.append({
                    "index": fila.get("index", idx + 1),
                    "jugada": jugada_raw,
                    "estado": "OMITIDO",
                    "linea_asignada": None,
                    "logs": logs_fila
                })
                continue

            datos_eq = obtener_datos_pikes(id_equipo, equipo_puro)
            if datos_eq:
                logs_fila.append(f"✅ Coincidencia de equipo hallada en Pikes JSON ({datos_eq.get('equipo') or datos_eq.get('nombre')})")
            else:
                logs_fila.append("❌ NO se halló coincidencia directa en Pikes JSON.")

            raw_pike1 = datos_eq.get("pike1", "").strip() if datos_eq else ""
            if raw_pike1.upper() == "V2":
                raw_pike1 = "-0.5"
                logs_fila.append("🔄 Transformado 'V2' a '-0.5'")

            linea_encontrada = None
            logro_encontrado = datos_eq.get("pike2", "").strip() if datos_eq else ""

            # CASO A: RL directo
            if raw_pike1 and (raw_pike1.startswith("-") or raw_pike1.startswith("+")):
                linea_encontrada = raw_pike1
                logs_fila.append(f"🟢 CASO A -> RL directo asignado: '{linea_encontrada}'")
            
            # CASO B: Rival
            else:
                logs_fila.append("🟡 CASO B -> Buscando rival en marcadores_guardados.json...")
                datos_partido = None
                for eq_key, info_partido in resultados_guardados.items():
                    eq_key_norm = normalizar_nombre(eq_key)
                    if eq_key_norm and (eq_key_norm == equipo_puro or eq_key_norm in equipo_puro or equipo_puro in eq_key_norm):
                        datos_partido = info_partido
                        break

                if datos_partido:
                    eq1, eq2 = datos_partido.get("equipo1", "").strip(), datos_partido.get("equipo2", "").strip()
                    eq1_norm = normalizar_nombre(eq1)
                    nombre_rival = eq2 if (eq1_norm and (eq1_norm in equipo_puro or equipo_puro in eq1_norm)) else eq1
                    logs_fila.append(f"   ├─ Partido en marcador: {eq1} vs {eq2}")
                    logs_fila.append(f"   ├─ Rival deducido: '{nombre_rival}'")

                    datos_rival = obtener_datos_pikes(None, nombre_rival)
                    if datos_rival:
                        pike1_rival = datos_rival.get("pike1", "").strip()
                        if pike1_rival.upper() == "V2": pike1_rival = "-0.5"

                        if pike1_rival and (pike1_rival.startswith("-") or pike1_rival.startswith("+")):
                            linea_encontrada = invertir_signo(pike1_rival)
                            logs_fila.append(f"   └─ 🟢 Línea de rival ({pike1_rival}) invertida asignada: '{linea_encontrada}'")
                        else:
                            logs_fila.append(f"   └─ ⚠️ El rival no tenía pike1 válido con +/- (Tenía: '{pike1_rival}')")
                    else:
                        logs_fila.append(f"   └─ ⚠️ No se halló al rival '{nombre_rival}' en el JSON de Pikes.")
                else:
                    logs_fila.append("   └─ ⚠️ No se encontró partido para este equipo en marcadores_guardados.json.")

            estado_final = "ASIGNADO" if (linea_encontrada or logro_encontrado) else "FALLIDO"

            if linea_encontrada or logro_encontrado:
                fila["linea_rl"] = linea_encontrada
                fila["cuota_rl"] = logro_encontrado
                coincidencias += 1

            reporte_pikes.append({
                "index": fila.get("index", idx + 1),
                "jugada": jugada_raw,
                "estado": estado_final,
                "linea_asignada": linea_encontrada,
                "cuota_asignada": logro_encontrado,
                "logs": logs_fila
            })

        # Guardar archivo JSON con la auditoría
        with open(os.path.join(BASE_DIR, RUTA_REPORTE_PIKES), 'w', encoding='utf-8') as f:
            json.dump({
                "archivo_pikes_usado": archivo_cargado_nombre,
                "total_pikes_cargados": len(mapa_nombre),
                "total_marcadores": len(resultados_guardados),
                "coincidencias": coincidencias,
                "reporte": reporte_pikes
            }, f, ensure_ascii=False, indent=2)

        return jsonify({
            "success": True,
            "mensaje": f"Se asignaron {coincidencias} pikes.",
            "filas": filas
        })

    except Exception as e:
        error_detallado = traceback.format_exc()
        return jsonify({"success": False, "mensaje": f"Error: {str(e)}", "trace": error_detallado}), 500

# ALTAS Y BAJAS FUTBOL

@pikes_bp.route('/procesar_pikes_ou_futbol', methods=['POST'])
def procesar_pikes_ou_futbol():
    try:
        data = request.json or {}
        filas = data.get('filas', [])

        print(f"\n================ [INICIO PROCESAR ALTAS/BAJAS FUTBOL] ================")
        print(f"📥 Filas recibidas: {len(filas)}")

        if not filas:
            return jsonify({"success": False, "mensaje": "No se recibieron filas."}), 400

        # 1. Cargar el JSON más reciente de pikes_futbol
        carp_pikes_futbol = os.path.join(BASE_DIR, 'pikes_futbol')
        mapa_id = {}
        mapa_nombre = {}

        if os.path.exists(carp_pikes_futbol):
            archivos_json = [
                os.path.join(carp_pikes_futbol, f) 
                for f in os.listdir(carp_pikes_futbol) 
                if f.endswith('.json')
            ]
            
            if archivos_json:
                archivo_mas_reciente = max(archivos_json, key=os.path.getmtime)
                print(f"📂 Cargando pikes desde: {os.path.basename(archivo_mas_reciente)}")

                with open(archivo_mas_reciente, 'r', encoding='utf-8') as f:
                    datos_pikes = json.load(f)
                    lista_pikes = datos_pikes if isinstance(datos_pikes, list) else datos_pikes.get('pikes', [])
                    
                    for item in lista_pikes:
                        p_id = str(item.get('id', '')).strip()
                        p_nombre = str(item.get('equipo', '') or item.get('nombre', '')).strip().upper()
                        
                        if p_id:
                            mapa_id[p_id] = item
                        if p_nombre:
                            mapa_nombre[p_nombre] = item

                print(f"✅ Pikes cargados ({len(mapa_nombre)} equipos).")

        # 2. Cargar marcadores guardados
        ruta_json_marcadores = os.path.join(BASE_DIR, 'marcadores_guardados.json')
        resultados_guardados = {}
        if os.path.exists(ruta_json_marcadores):
            try:
                with open(ruta_json_marcadores, 'r', encoding='utf-8') as f:
                    resultados_guardados = json.load(f)
                print(f"✅ Marcadores cargados ({len(resultados_guardados)} registros).")
            except Exception as e:
                print(f"⚠️ Error cargando marcadores_guardados.json: {e}")

        coincidencias = 0

        # Helper para extraer nombre limpio y tipo
        def extraer_info_jugada(texto):
            if not texto:
                return "", None
            
            texto_upper = str(texto).upper().strip()
            
            tipo = None
            if "ALTA" in texto_upper or "OVER" in texto_upper:
                tipo = "ALTA"
            elif "BAJA" in texto_upper or "UNDER" in texto_upper:
                tipo = "BAJA"

            basura = ["MLB", "ALTA", "BAJA", "OVER", "UNDER", "RL", "ML", "FUTBOL", "BEISBOL", "FK", "FC", "CF", "CD"]
            palabras = texto_upper.replace("_", " ").split()
            palabras_limpias = [p for p in palabras if p not in basura]
            equipo_limpio = " ".join(palabras_limpias).strip()

            return equipo_limpio, tipo

        def obtener_datos_pikes(id_eq, nombre_eq):
            if id_eq and id_eq in mapa_id:
                return mapa_id[id_eq]
            
            if not nombre_eq:
                return None

            for k_nombre, info in mapa_nombre.items():
                k_norm, _ = extraer_info_jugada(k_nombre)
                if k_norm and (k_norm in nombre_eq or nombre_eq in k_norm):
                    return info
            return None

        # 3. Procesar filas
        for fila in filas:
            jugada_raw = str(fila.get("jugada", "")).upper().strip()

            # Filtrar: únicamente jugadas de ALTA/BAJA
            if not any(palabra in jugada_raw for palabra in ["ALTA", "BAJA", "OVER", "UNDER"]):
                print(f" ⏭️ [FILA {fila.get('index')}] Saltando '{jugada_raw}' por no ser ALTA/BAJA.")
                continue

            equipo_puro, tipo_jugada = extraer_info_jugada(jugada_raw)
            id_equipo = str(fila.get("id", "")).strip()

            print(f"\n🔍 [FILA {fila.get('index')}] Raw: '{jugada_raw}' -> Equipo: '{equipo_puro}' | Tipo: '{tipo_jugada}'")

            # Buscar la información del partido en marcadores_guardados.json
            datos_partido = None
            for eq_key, info_partido in resultados_guardados.items():
                eq_key_norm, _ = extraer_info_jugada(eq_key)
                if eq_key_norm and (eq_key_norm == equipo_puro or eq_key_norm in equipo_puro or equipo_puro in eq_key_norm):
                    datos_partido = info_partido
                    break

            if not datos_partido:
                print(f" ❌ No se encontró el partido de '{equipo_puro}' en marcadores_guardados.json.")
                continue

            # Obtener datos de ambos equipos del partido
            eq1_nombre = datos_partido.get("equipo1", "").strip()
            eq2_nombre = datos_partido.get("equipo2", "").strip()

            datos_eq1 = obtener_datos_pikes(None, extraer_info_jugada(eq1_nombre)[0])
            datos_eq2 = obtener_datos_pikes(None, extraer_info_jugada(eq2_nombre)[0])

            # Identificar cuál equipo posee la línea de gol (el que NO tiene signo + o - en pike1)
            pike1_eq1 = datos_eq1.get("pike1", "").strip() if datos_eq1 else ""
            pike1_eq2 = datos_eq2.get("pike1", "").strip() if datos_eq2 else ""

            linea_encontrada = None
            logro_encontrado = None

            # Determinar la línea O/U
            if pike1_eq1 and not (pike1_eq1.startswith("-") or pike1_eq1.startswith("+")):
                linea_encontrada = pike1_eq1
            elif pike1_eq2 and not (pike1_eq2.startswith("-") or pike1_eq2.startswith("+")):
                linea_encontrada = pike1_eq2

            # Determinar el logro según el tipo de jugada:
            # ALTA -> pike3 del equipo 1 | BAJA -> pike3 del equipo 2
            if tipo_jugada == "ALTA":
                logro_encontrado = datos_eq1.get("pike3", "").strip() if datos_eq1 else ""
            elif tipo_jugada == "BAJA":
                logro_encontrado = datos_eq2.get("pike3", "").strip() if datos_eq2 else ""

            print(f" 🟢 Resultado -> Línea: '{linea_encontrada}', Logro ({tipo_jugada}): '{logro_encontrado}'")

            if linea_encontrada or logro_encontrado:
                fila["linea_ou"] = linea_encontrada
                fila["cuota_ou"] = logro_encontrado
                coincidencias += 1

        print(f"\n================ [FIN] Coincidencias O/U: {coincidencias} ================\n")

        return jsonify({
            "success": True,
            "mensaje": f"Se asignaron {coincidencias} pikes de Altas/Bajas.",
            "filas": filas
        })

    except Exception as e:
        error_detallado = traceback.format_exc()
        print(f"💥 ERROR EN BACKEND:\n{error_detallado}")
        return jsonify({"success": False, "mensaje": f"Error: {str(e)}", "trace": error_detallado}), 500
# ==========================================
# 5. ENDPOINT PARA REINICIAR DÍA
# ==========================================
# Asegúrate de definir las dos carpetas de destino al inicio de tu archivo pikes_processor.py
CARPETA_PIKES_MLB = os.path.join(BASE_DIR, 'pikes_guardados')
CARPETA_PIKES_FUTBOL = os.path.join(BASE_DIR, 'pikes_futbol')

@pikes_bp.route('/reiniciar_dia', methods=['POST'])
def reiniciar_dia():
    try:
        data = request.get_json(silent=True) or {}
        deporte = str(data.get('deporte', 'mlb')).lower()

        # Determinar qué carpeta limpiar
        if deporte == 'futbol':
            carpeta_destino = CARPETA_PIKES_FUTBOL
            nombre_deporte = "Fútbol"
        else:
            carpeta_destino = CARPETA_PIKES_MLB
            nombre_deporte = "Béisbol (MLB)"

        archivos_borrados = 0
        if os.path.exists(carpeta_destino):
            for archivo in os.listdir(carpeta_destino):
                ruta_archivo = os.path.join(carpeta_destino, archivo)
                if os.path.isfile(ruta_archivo):
                    os.remove(ruta_archivo)
                    archivos_borrados += 1

        return jsonify({
            "success": True,
            "mensaje": f"Se han borrado los pikes de {nombre_deporte} ({archivos_borrados} archivos eliminados)."
        })
    except Exception as e:
        return jsonify({"success": False, "mensaje": f"Error al reiniciar el día: {str(e)}"}), 500