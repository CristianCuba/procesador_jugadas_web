import re
import json
import os

JSON_DICCIONARIO_FUTBOL_PATH = 'diccionario_ocr_futbol.json'

def cargar_diccionario_futbol():
    """Carga el diccionario exclusivo de fútbol desde el archivo JSON persistente."""
    if os.path.exists(JSON_DICCIONARIO_FUTBOL_PATH):
        try:
            with open(JSON_DICCIONARIO_FUTBOL_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error cargando {JSON_DICCIONARIO_FUTBOL_PATH}:", e)
    return {}

def guardar_diccionario_futbol(diccionario):
    """Guarda el diccionario de fútbol en el archivo JSON."""
    with open(JSON_DICCIONARIO_FUTBOL_PATH, 'w', encoding='utf-8') as f:
        json.dump(diccionario, f, ensure_ascii=False, indent=4)

def agregar_regla_futbol(patron, reemplazo):
    """Añade o actualiza una regla de fútbol."""
    dicc = cargar_diccionario_futbol()
    dicc[patron.strip()] = reemplazo.strip()
    guardar_diccionario_futbol(dicc)

def eliminar_regla_futbol(patron):
    """Elimina una regla del diccionario de fútbol."""
    dicc = cargar_diccionario_futbol()
    if patron in dicc:
        del dicc[patron]
        guardar_diccionario_futbol(dicc)
        return True
    return False

def aplicar_correcciones_diccionario_futbol(texto):
    """Aplica las reglas del diccionario de fútbol al texto."""
    diccionario = cargar_diccionario_futbol()
    if not texto or not diccionario:
        return texto

    lineas = texto.split('\n')
    lineas_procesadas = []

    for linea in lineas:
        linea_temp = linea
        for patron, reemplazo in diccionario.items():
            try:
                linea_temp = re.sub(
                    patron, 
                    lambda m, r=reemplazo: r, 
                    linea_temp, 
                    flags=re.IGNORECASE
                )
            except Exception:
                linea_temp = linea_temp.replace(patron, reemplazo)

        lineas_procesadas.append(linea_temp)

    return "\n".join(lineas_procesadas)