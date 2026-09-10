import re
import json
import os

JSON_DICCIONARIO_PATH = 'diccionario_ocr.json'

def cargar_diccionario():
    """Carga el diccionario desde el archivo JSON persistente."""
    if os.path.exists(JSON_DICCIONARIO_PATH):
        try:
            with open(JSON_DICCIONARIO_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error cargando {JSON_DICCIONARIO_PATH}:", e)
    return {}

def guardar_diccionario(diccionario):
    """Guarda el diccionario en el archivo JSON."""
    with open(JSON_DICCIONARIO_PATH, 'w', encoding='utf-8') as f:
        json.dump(diccionario, f, ensure_ascii=False, indent=4)

def agregar_regla(patron, reemplazo):
    """Añade o actualiza una regla."""
    dicc = cargar_diccionario()
    dicc[patron.strip()] = reemplazo.strip()
    guardar_diccionario(dicc)

def eliminar_regla(patron):
    """Elimina una regla del diccionario."""
    dicc = cargar_diccionario()
    if patron in dicc:
        del dicc[patron]
        guardar_diccionario(dicc)
        return True
    return False

def aplicar_correcciones_diccionario(texto):
    """Aplica las reglas cargadas desde el JSON al texto sin romper por referencias a grupos."""
    diccionario = cargar_diccionario()
    if not texto or not diccionario:
        return texto

    lineas = texto.split('\n')
    lineas_procesadas = []

    for linea in lineas:
        linea_temp = linea
        for patron, reemplazo in diccionario.items():
            try:
                # Usar lambda evita errores de referencia a grupos (\1, \11, etc.)
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