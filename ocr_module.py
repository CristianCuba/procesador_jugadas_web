import os
import re
import json
import base64
import ssl
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify

import easyocr
from diccionario_ocr import cargar_diccionario, aplicar_correcciones_diccionario

# Definición del Blueprint para OCR
ocr_bp = Blueprint('ocr_bp', __name__)

# Configuración de rutas de archivos
JSON_PIKES_PATH = 'pikeshoy.json'

# Desactivar verificación SSL para EasyOCR si es necesario
ssl._create_default_https_context = ssl._create_unverified_context

# Cargar modelo EasyOCR (se carga solo una vez al importar el módulo)
reader_ocr = easyocr.Reader(['es', 'en'], gpu=False)


# ==============================================================================
# LÓGICA DE PROCESAMIENTO DE IMAGEN - BÉISBOL / PELOTA (INTACTA)
# ==============================================================================
def procesar_y_alinear_ocr(image_bytes):
    resultados = reader_ocr.readtext(image_bytes, detail=1)
    if not resultados:
        return ""

    elementos = []
    for box, texto_raw, prob in resultados:
        txt = texto_raw.strip()
        if re.search(r'\d{1,2}[\.:]\d{2}\s*(AM|PM)?', txt, re.IGNORECASE):
            continue
        if txt:
            txt = re.sub(r'~', '-', txt)
            y_centro = (box[0][1] + box[2][1]) / 2.0
            x_centro = (box[0][0] + box[1][0]) / 2.0
            elementos.append({'texto': txt, 'x': x_centro, 'y': y_centro})

    equipos = [el for el in elementos if re.match(r'^\d{4,5}\b', el['texto'])]
    equipos.sort(key=lambda item: item['y'])

    if not equipos or len(equipos) % 2 != 0:
        return "\n".join([el['texto'] for el in elementos])

    cuotas_y_numeros = [el for el in elementos if not re.match(r'^\d{4,5}\b', el['texto'])]
    cuotas_y_numeros.sort(key=lambda item: item['x'])

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

        if (index + 1) % 2 == 0 and (index + 1) < len(equipos):
            lineas_resultado.append("")

    return "\n".join(lineas_resultado)


# ==============================================================================
# RUTAS DEL MÓDULO OCR
# ==============================================================================
@ocr_bp.route('/ocr', methods=['GET', 'POST'])
def vista_ocr():
    texto_resultado = ""
    imagen_base64 = ""
    deporte_seleccionado = 'mlb'

    if request.method == 'POST':
        deporte_seleccionado = request.form.get('deporte', 'mlb').lower()

        if 'imagen' in request.files:
            file = request.files['imagen']
            if file.filename != '':
                image_bytes = file.read()

                # Decidir procesador según el deporte
                if deporte_seleccionado == 'futbol':
                    texto_resultado = procesar_y_alinear_ocr_futbol(image_bytes)
                else:
                    texto_alineado = procesar_y_alinear_ocr(image_bytes)
                    texto_resultado = aplicar_correcciones_diccionario(texto_alineado)

                imagen_base64 = base64.b64encode(image_bytes).decode('utf-8')

    reglas = cargar_diccionario()
    return render_template(
        'ocr.html', 
        texto_resultado=texto_resultado, 
        imagen_base64=imagen_base64,
        reglas=reglas,
        deporte_activo=deporte_seleccionado
    )


@ocr_bp.route('/guardar_pikes', methods=['POST'])
def guardarPikesEditados():
    try:
        data = request.json or {}
        pikes_recibidos = data.get('pikes', [])
        texto_editado = data.get('texto', '').strip()

        pikes_estructurados = []

        # 1. Si vienen pikes en el array `pikes` desde JS:
        if pikes_recibidos:
            for item in pikes_recibidos:
                pikes_estructurados.append({
                    "id": str(item.get('id', '')).strip(),
                    "nombre": str(item.get('equipo', '') or item.get('nombre', '')).strip(),
                    "pike1": str(item.get('pike1', '')).strip(),
                    "pike2": str(item.get('pike2', '')).strip(),
                    "pike3": str(item.get('pike3', '')).strip()
                })
        # 2. Si viene texto crudo para parsear:
        elif texto_editado:
            lineas = [linea.strip() for linea in texto_editado.splitlines() if linea.strip()]
            patron_linea = re.compile(r'^(\d{4,5})\s+(.+?)\s+([\+\-]?\d+(?:\.\d+)?)\s+([\+\-]?\d+(?:\.\d+)?)(?:\s+([\+\-]?\d+(?:\.\d+)?))?$')

            for linea in lineas:
                match = patron_linea.match(linea)
                if match:
                    pikes_estructurados.append({
                        "id": match.group(1),
                        "nombre": match.group(2).strip(),
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

                        pikes_estructurados.append({
                            "id": id_equipo,
                            "nombre": nombre_equipo,
                            "pike1": cuotas[0] if len(cuotas) > 0 else "",
                            "pike2": cuotas[1] if len(cuotas) > 1 else "",
                            "pike3": cuotas[2] if len(cuotas) > 2 else ""
                        })

        if not pikes_estructurados:
            return jsonify({"success": False, "mensaje": "No hay pikes válidos para guardar."}), 400

        datos_guardar = {
            "fecha_actualizacion": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "total_lineas": len(pikes_estructurados),
            "pikes": pikes_estructurados
        }

        with open(JSON_PIKES_PATH, 'w', encoding='utf-8') as f:
            json.dump(datos_guardar, f, ensure_ascii=False, indent=4)

        print(f"✅ [PIKES] pikeshoy.json guardado con éxito ({len(pikes_estructurados)} pikes).")
        return jsonify({
            "success": True, 
            "mensaje": f"¡Se guardaron {len(pikes_estructurados)} pikes estructurados en pikeshoy.json!"
        })

    except Exception as e:
        print(f"❌ Error al guardar pikeshoy.json: {e}")
        return jsonify({"success": False, "mensaje": str(e)}), 500


@ocr_bp.route('/api/procesar-ocr', methods=['POST'])
def procesar_ocr_endpoint():
    file = request.files.get('file') or request.files.get('imagen')
    if not file:
        return jsonify({'success': False, 'mensaje': 'No se envió ninguna imagen.'}), 400

    deporte = request.form.get('deporte', 'MLB').upper()  # 'MLB' o 'FUTBOL'
    reglas_json = request.form.get('reglas', '{}')
    
    try:
        reglas = json.loads(reglas_json)
    except Exception:
        reglas = {}

    image_bytes = file.read()

    # 1. Ejecutar pipeline según deporte
    if deporte == 'FUTBOL':
        texto_raw = procesar_y_alinear_ocr_futbol(image_bytes)
    else:
        texto_raw = procesar_y_alinear_ocr(image_bytes)

    # 2. Aplicar correcciones enviadas por la interfaz
    texto_final = texto_raw
    for err, corr in reglas.items():
        if err:
            texto_final = re.sub(r'\b' + re.escape(err) + r'\b', corr, texto_final)

    return jsonify({
        'success': True,
        'texto': texto_final
    })