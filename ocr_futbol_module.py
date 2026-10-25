import os
import re
import json
import base64
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify

import easyocr
from diccionario_ocr_futbol import (
    cargar_diccionario_futbol,
    aplicar_correcciones_diccionario_futbol,
    agregar_regla_futbol,
    eliminar_regla_futbol
)

ocr_futbol_bp = Blueprint('ocr_futbol_bp', __name__)

# Carpeta aislada donde se guardarán los pikes de fútbol
CARPETA_PIKES_FUTBOL = 'pikes_futbol'

# Inicialización del lector EasyOCR
reader_ocr = easyocr.Reader(['es', 'en'], gpu=False)

def procesar_y_alinear_ocr_futbol(image_bytes):
    """
    Procesador OCR especializado para listas de fútbol.
    Filtra horas, limpia caracteres raros y organiza los equipos con sus líneas.
    """
    resultados = reader_ocr.readtext(image_bytes, detail=1)
    if not resultados:
        return ""

    elementos = []
    for box, texto_raw, prob in resultados:
        txt = texto_raw.strip()
        # Omitir horas (ej. 12:30 PM, 15:00)
        if re.search(r'\d{1,2}[\.:]\d{2}\s*(AM|PM)?', txt, re.IGNORECASE):
            continue
        if txt:
            txt = re.sub(r'~', '-', txt)
            y_centro = (box[0][1] + box[2][1]) / 2.0
            x_centro = (box[0][0] + box[1][0]) / 2.0
            elementos.append({'texto': txt, 'x': x_centro, 'y': y_centro})

    # Filtrar IDs de partidos o equipos si empiezan con números
    equipos = [el for el in elementos if re.match(r'^\d{3,5}\b', el['texto'])]
    equipos.sort(key=lambda item: item['y'])

    # Si la lista no es par o no se hallaron IDs claros, devolvemos en orden de altura (Y)
    if not equipos:
        elementos.sort(key=lambda item: (item['y'], item['x']))
        return "\n".join([el['texto'] for el in elementos])

    cuotas_y_numeros = [el for el in elementos if not re.match(r'^\d{3,5}\b', el['texto'])]
    cuotas_y_numeros.sort(key=lambda item: item['x'])

    # Agrupar cuotas por columnas verticales (X)
    columnas = []
    UMBRAL_X = 40.0

    for num in cuotas_y_numeros:
        agrupado = False
        for col in columnas:
            x_promedio = sum(e['x'] for e in col) / len(col)
            if abs(num['x'] - x_promedio) <= UMBRAL_X:
                col.append(num)
                agrupado = True
                break
        if not agrupado:
            columnas.append([num])

    matriz_cuotas = {i: [] for i in range(len(equipos))}

    for col in columnas:
        col_ordenada_y = sorted(col, key=lambda item: item['y'])
        for idx, item in enumerate(col_ordenada_y):
            if idx < len(equipos):
                matriz_cuotas[idx].append(item)

    lineas_resultado = []
    for index, eq in enumerate(equipos):
        cuotas_eq = matriz_cuotas[index]
        cuotas_eq.sort(key=lambda item: item['x'])

        texto_cuotas = " ".join([c['texto'] for c in cuotas_eq])
        linea_final = f"{eq['texto']} {texto_cuotas}".strip()
        lineas_resultado.append(linea_final)

        # Separador entre partidos (cada 2 equipos)
        if (index + 1) % 2 == 0 and (index + 1) < len(equipos):
            lineas_resultado.append("")

    return "\n".join(lineas_resultado)


# ==============================================================================
# RUTAS DE FÚTBOL OCR
# ==============================================================================


@ocr_futbol_bp.route('/ocr_futbol', methods=['GET', 'POST'])
def vista_ocr_futbol():
    texto_resultado = ""
    imagen_base64 = ""

    if request.method == 'POST':
        if 'imagen' in request.files:
            file = request.files['imagen']
            if file.filename != '':
                image_bytes = file.read()

                # Pipeline de OCR + Diccionario de Fútbol
                texto_alineado = procesar_y_alinear_ocr_futbol(image_bytes)
                texto_resultado = aplicar_correcciones_diccionario_futbol(texto_alineado)

                imagen_base64 = base64.b64encode(image_bytes).decode('utf-8')

    reglas = cargar_diccionario_futbol()
    return render_template(
        'ocr_futbol.html', 
        texto_resultado=texto_resultado, 
        imagen_base64=imagen_base64,
        reglas=reglas,
        deporte_activo='futbol'
    )


@ocr_futbol_bp.route('/guardar_pikes_futbol', methods=['POST'])
def guardar_pikes_futbol():
    try:
        data = request.json or {}
        pikes_recibidos = data.get('pikes', [])
        texto_editado = data.get('texto', '').strip()

        lista_equipos = []

        # 1. Parsear los pikes recibidos o el texto editado en una lista plana temporal de equipos
        if pikes_recibidos:
            for item in pikes_recibidos:
                lista_equipos.append({
                    "id": str(item.get('id', '')).strip(),
                    "equipo": str(item.get('equipo', '') or item.get('nombre', '')).strip(),
                    "pike1": str(item.get('pike1', '')).strip(),
                    "pike2": str(item.get('pike2', '')).strip(),
                    "pike3": str(item.get('pike3', '')).strip()
                })
        elif texto_editado:
            lineas = [linea.strip() for linea in texto_editado.splitlines() if linea.strip()]
            patron_linea = re.compile(r'^(\d{3,5})\s+(.+?)\s+([\+\-]?\d+(?:\.\d+)?)\s+([\+\-]?\d+(?:\.\d+)?)(?:\s+([\+\-]?\d+(?:\.\d+)?))?$')

            for linea in lineas:
                match = patron_linea.match(linea)
                if match:
                    lista_equipos.append({
                        "id": match.group(1),
                        "equipo": match.group(2).strip(),
                        "pike1": match.group(3),
                        "pike2": match.group(4),
                        "pike3": match.group(5) if match.group(5) else ""
                    })
                else:
                    partes = linea.split()
                    if len(partes) >= 2 and partes[0].isdigit():
                        id_equipo = partes[0]
                        idx_cuota = 1
                        for i in range(1, len(partes)):
                            if re.match(r'^[\+\-]?\d', partes[i]):
                                idx_cuota = i
                                break
                        
                        nombre_equipo = " ".join(partes[1:idx_cuota])
                        cuotas = partes[idx_cuota:]

                        lista_equipos.append({
                            "id": id_equipo,
                            "equipo": nombre_equipo,
                            "pike1": cuotas[0] if len(cuotas) > 0 else "",
                            "pike2": cuotas[1] if len(cuotas) > 1 else "",
                            "pike3": cuotas[2] if len(cuotas) > 2 else ""
                        })

        if not lista_equipos:
            return jsonify({"success": False, "mensaje": "No hay pikes válidos para guardar en fútbol."}), 400

        # 2. Agrupar de 2 en 2 líneas para formar los partidos (Local y Visitante)
        partidos_estructurados = []
        for i in range(0, len(lista_equipos) - 1, 2):
            local = lista_equipos[i]
            visitante = lista_equipos[i+1]
            partidos_estructurados.append({
                "local": local,
                "visitante": visitante
            })
        
        # Manejo por seguridad si la cantidad total de líneas fuera impar
        if len(lista_equipos) % 2 != 0:
            partidos_estructurados.append({
                "local": lista_equipos[-1],
                "visitante": {"id": "", "equipo": "", "pike1": "", "pike2": "", "pike3": ""}
            })

        # 3. Guardar el archivo JSON estructurado por partidos
        os.makedirs(CARPETA_PIKES_FUTBOL, exist_ok=True)
        nombre_archivo = f"pikes_futbol_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        ruta_archivo = os.path.join(CARPETA_PIKES_FUTBOL, nombre_archivo)

        datos_guardar = {
            "fecha_actualizacion": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "deporte": "FUTBOL",
            "total_partidos": len(partidos_estructurados),
            "partidos": partidos_estructurados
        }

        with open(ruta_archivo, 'w', encoding='utf-8') as f:
            json.dump(datos_guardar, f, ensure_ascii=False, indent=4)

        print(f"⚽ [FÚTBOL PARTIDOS] Guardado en {ruta_archivo} ({len(partidos_estructurados)} partidos).")
        return jsonify({
            "success": True, 
            "mensaje": f"¡Se guardaron {len(partidos_estructurados)} partidos de fútbol correctamente en {ruta_archivo}!"
        })

    except Exception as e:
        print(f"❌ Error al guardar pikes de fútbol: {e}")
        return jsonify({"success": False, "mensaje": str(e)}), 500


@ocr_futbol_bp.route('/diccionario_futbol/agregar', methods=['POST'])
def ruta_agregar_regla_futbol():
    data = request.json or request.form
    patron = data.get('patron', '').strip()
    reemplazo = data.get('reemplazo', '').strip()

    if not patron:
        return jsonify({"success": False, "mensaje": "El patrón no puede estar vacío."})

    agregar_regla_futbol(patron, reemplazo)
    return jsonify({"success": True, "mensaje": "Regla de fútbol agregada."})


@ocr_futbol_bp.route('/diccionario_futbol/eliminar', methods=['POST'])
def ruta_eliminar_regla_futbol():
    data = request.json or request.form
    patron = data.get('patron', '').strip()

    if eliminar_regla_futbol(patron):
        return jsonify({"success": True, "mensaje": "Regla de fútbol eliminada."})
    return jsonify({"success": False, "mensaje": "Regla no encontrada."})