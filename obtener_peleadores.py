import requests
from bs4 import BeautifulSoup
import json
import os
import re

JSON_UFC_PATH = 'peleadores_ufc_oficiales.json'

def obtener_peleadores_wikipedia():
    print("⏳ Extrayendo lista de peleadores desde Wikipedia...")
    url = "https://en.wikipedia.org/wiki/List_of_current_UFC_fighters"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    peleadores = []
    nombres_procesados = set()

    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            # Las tablas de peleadores en esta página tienen la clase 'wikitable'
            tablas = soup.find_all('table', class_='wikitable')
            
            print(f"📊 Buscando en {len(tablas)} tablas de categorías de peso...")

            id_counter = 1
            for tabla in tablas:
                filas = tabla.find_all('tr')
                for fila in filas[1:]:  # Saltar el encabezado
                    columnas = fila.find_all(['td', 'th'])
                    if columnas:
                        # En la mayoría de las tablas, la primera o segunda columna es el nombre
                        texto_nombre = ""
                        for col in columnas[:2]:
                            enlace = col.find('a')
                            if enlace and enlace.text.strip():
                                texto_nombre = enlace.text.strip()
                                break
                            elif col.text.strip():
                                texto_nombre = col.text.strip()
                                break
                        
                        # Limpiar anotaciones como [1], *, etc.
                        nombre_limpio = re.sub(r'\[.*?\]', '', texto_nombre).strip().upper()
                        nombre_limpio = re.sub(r'[^\w\s]', '', nombre_limpio).strip()

                        # Validaciones de longitud e ignorar textos no válidos
                        if nombre_limpio and len(nombre_limpio) > 3 and nombre_limpio not in nombres_procesados:
                            if nombre_limpio in ['NAME', 'FIGHTER', 'ROSTER', 'COUNTRY', 'AGE']:
                                continue

                            nombres_procesados.add(nombre_limpio)
                            
                            partes = nombre_limpio.split()
                            aliases = [nombre_limpio]
                            
                            # Generar alias con el apellido si tiene 2 o más palabras
                            if len(partes) >= 2:
                                apellido = partes[-1]
                                if len(apellido) > 3:
                                    aliases.append(apellido)

                            peleadores.append({
                                "id": f"ufc_wiki_{id_counter}",
                                "nombre_oficial": nombre_limpio,
                                "aliases": list(set(aliases))
                            })
                            id_counter += 1

            print(f"✅ Se extrajeron exitosamente {len(peleadores)} peleadores.")
        else:
            print(f"❌ Error al acceder a Wikipedia. Estado: {res.status_code}")

    except Exception as e:
        print(f"❌ Error durante el web scraping: {e}")

    return peleadores


def guardar_json_peleadores(lista_peleadores):
    if not lista_peleadores:
        print("⚠️ No se obtuvieron peleadores para guardar.")
        return

    # Preservar alias anteriores si ya existe el archivo
    if os.path.exists(JSON_UFC_PATH):
        try:
            with open(JSON_UFC_PATH, 'r', encoding='utf-8') as f:
                existentes = json.load(f)
                dict_existentes = {p['nombre_oficial']: p.get('aliases', []) for p in existentes}
                
                for p in lista_peleadores:
                    oficial = p['nombre_oficial']
                    if oficial in dict_existentes:
                        union_aliases = set(p['aliases'] + dict_existentes[oficial])
                        p['aliases'] = list(union_aliases)
        except Exception as e:
            print(f"Nota: No se pudo fusionar con el JSON anterior ({e}).")

    with open(JSON_UFC_PATH, 'w', encoding='utf-8') as f:
        json.dump(lista_peleadores, f, ensure_ascii=False, indent=4)
        
    print(f"\n🎉 ¡Proceso completado! Se guardaron {len(lista_peleadores)} peleadores en '{JSON_UFC_PATH}'.")


if __name__ == '__main__':
    datos = obtener_peleadores_wikipedia()
    guardar_json_peleadores(datos)