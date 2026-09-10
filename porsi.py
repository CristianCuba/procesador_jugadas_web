
#esta funcion es la que analiza las fotos y devuelve los pikes


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

    # 1. Separar Equipos
    equipos = [el for el in elementos if re.match(r'^\d{4,5}\b', el['texto'])]
    equipos.sort(key=lambda item: item['y'])

    if not equipos or len(equipos) % 2 != 0:
        # Si no hay equipos pares, caer en fallback simple
        return "\n".join([el['texto'] for el in elementos])

    cuotas_y_numeros = [el for el in elementos if not re.match(r'^\d{4,5}\b', el['texto'])]

    # 2. Agrupar los números en "Columnas" según su posición X (horizontal)
    cuotas_y_numeros.sort(key=lambda item: item['x'])
    
    columnas = []
    UMBRAL_X = 40.0  # Ancho en píxeles para agrupar en la misma columna vertical

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

    # 3. Para cada columna, ordenar sus datos de arriba hacia abajo (por Y)
    # y repartir secuencialmente entre los equipos (1 para cada uno)
    matriz_cuotas = {i: [] for i in range(len(equipos))}

    for col in columnas:
        col_ordenada_y = sorted(col, key=lambda item: item['y'])
        
        # Asignar secuencialmente a los equipos de arriba a abajo
        for idx, item in enumerate(col_ordenada_y):
            if idx < len(equipos):
                matriz_cuotas[idx].append(item)

    # 4. Reconstruir las líneas finales
    lineas_resultado = []
    for index, eq in enumerate(equipos):
        cuotas_eq = matriz_cuotas[index]
        # Ordenar las cuotas de este equipo de izquierda a derecha por X
        cuotas_eq.sort(key=lambda item: item['x'])

        texto_cuotas = " ".join([c['texto'] for c in cuotas_eq])
        linea_final = f"{eq['texto']} {texto_cuotas}".strip()
        lineas_resultado.append(linea_final)

        # Salto de línea en blanco cada pareja de partido
        if (index + 1) % 2 == 0 and (index + 1) < len(equipos):
            lineas_resultado.append("")

    return "\n".join(lineas_resultado)
    # 1. Obtener cajas de texto con coordenadas
    resultados = reader_ocr.readtext(image_bytes, detail=1)
    if not resultados:
        return ""

    elementos = []
    for box, texto_raw, prob in resultados:
        txt = texto_raw.strip()
        
        # Omitir stamps de hora (ej: 6:00 PM)
        if re.search(r'\d{1,2}[\.:]\d{2}\s*(AM|PM)?', txt, re.IGNORECASE):
            continue
            
        if txt:
            txt = re.sub(r'~', '-', txt)
            y_centro = (box[0][1] + box[2][1]) / 2.0
            x_centro = (box[0][0] + box[1][0]) / 2.0
            
            elementos.append({
                'texto': txt,
                'x': x_centro,
                'y': y_centro
            })

    # 2. Separar Equipos (ID de 4-5 dígitos) y Cuotas/Números
    equipos = []
    cuotas_y_numeros = []

    for el in elementos:
        if re.match(r'^\d{4,5}\b', el['texto']):
            equipos.append(el)
        else:
            cuotas_y_numeros.append(el)

    # Ordenar equipos verticalmente (arriba a abajo)
    equipos.sort(key=lambda item: item['y'])

    if not equipos:
        return "\n".join([el['texto'] for el in elementos])

    # 3. Calcular límites horizontales exactos (franjas) entre equipos
    # Creamos 'cortes' exactos a la mitad de la distancia Y entre equipo y equipo
    limites_y = []
    
    # Límite superior inicial (muy arriba)
    limites_y.append(-99999.0)
    
    for i in range(len(equipos) - 1):
        punto_medio = (equipos[i]['y'] + equipos[i+1]['y']) / 2.0
        limites_y.append(punto_medio)
        
    # Límite inferior final (muy abajo)
    limites_y.append(99999.0)

    # 4. Asignar cada cuota estrictamente a la franja de su equipo
    cuotas_por_equipo = {i: [] for i in range(len(equipos))}

    for num in cuotas_y_numeros:
        y_num = num['y']
        for i in range(len(equipos)):
            limite_superior = limites_y[i]
            limite_inferior = limites_y[i+1]
            
            if limite_superior <= y_num < limite_inferior:
                cuotas_por_equipo[i].append(num)
                break

    # 5. Armar las líneas finales
    lineas_resultado = []

    for index, eq in enumerate(equipos):
        cuotas_del_equipo = cuotas_por_equipo[index]

        # Ordenar las cuotas de este equipo de izquierda a derecha por X
        cuotas_del_equipo.sort(key=lambda item: item['x'])

        texto_cuotas = " ".join([c['texto'] for c in cuotas_del_equipo])
        linea_final = f"{eq['texto']} {texto_cuotas}".strip()
        
        lineas_resultado.append(linea_final)

        # Salto de línea en blanco cada 2 equipos (cada pareja de partido)
        if (index + 1) % 2 == 0 and (index + 1) < len(equipos):
            lineas_resultado.append("")

    return "\n".join(lineas_resultado)
    # 1. Obtener cajas de texto con coordenadas (detail=1)
    resultados = reader_ocr.readtext(image_bytes, detail=1)
    if not resultados:
        return ""

    elementos = []
    for box, texto_raw, prob in resultados:
        txt = texto_raw.strip()
        
        # Omitir stamps de hora (ej: 6:00 PM)
        if re.search(r'\d{1,2}[\.:]\d{2}\s*(AM|PM)?', txt, re.IGNORECASE):
            continue
            
        if txt:
            # Reemplazar confusiones comunes de OCR en símbolos (~ -> -)
            txt = re.sub(r'~', '-', txt)
            
            # Calcular el centro Y y X del texto en la imagen
            y_centro = (box[0][1] + box[2][1]) / 2.0
            x_centro = (box[0][0] + box[1][0]) / 2.0
            
            elementos.append({
                'texto': txt,
                'x': x_centro,
                'y': y_centro
            })

    # 2. Identificar los bloques de equipos (los que tienen ID de 4 o 5 dígitos)
    equipos = []
    cuotas_y_numeros = []

    for el in elementos:
        if re.match(r'^\d{4,5}\b', el['texto']):
            equipos.append(el)
        else:
            cuotas_y_numeros.append(el)

    # Ordenar equipos verticalmente de arriba hacia abajo
    equipos.sort(key=lambda item: item['y'])

    if not equipos:
        return "\n".join([el['texto'] for el in elementos])

    # 3. Asignar cada número/cuota al equipo dentro del umbral Y ampliado
    UMBRAL_TOLERANCIA_Y = 35.0  # Ampliado para capturar las cuotas del 2do equipo
    lineas_resultado = []

    for index, eq in enumerate(equipos):
        y_eq = eq['y']
        
        cuotas_del_equipo = []
        for num in cuotas_y_numeros:
            if abs(num['y'] - y_eq) <= UMBRAL_TOLERANCIA_Y:
                cuotas_del_equipo.append(num)

        # Ordenar las cuotas de este equipo de izquierda a derecha por X
        cuotas_del_equipo.sort(key=lambda item: item['x'])

        # Unir ID + Nombre del Equipo + sus Cuotas correspondientes
        texto_cuotas = " ".join([c['texto'] for c in cuotas_del_equipo])
        linea_final = f"{eq['texto']} {texto_cuotas}".strip()
        
        lineas_resultado.append(linea_final)

        # Insertar salto de línea en blanco cada 2 equipos (cada pareja de partido)
        if (index + 1) % 2 == 0 and (index + 1) < len(equipos):
            lineas_resultado.append("")

    return "\n".join(lineas_resultado)

    # 1. Obtener cajas de texto con coordenadas (detail=1)
    resultados = reader_ocr.readtext(image_bytes, detail=1)
    if not resultados:
        return ""

    elementos = []
    for box, texto_raw, prob in resultados:
        txt = texto_raw.strip()
        
        # Omitir stamps de hora (ej: 6:00 PM)
        if re.search(r'\d{1,2}[\.:]\d{2}\s*(AM|PM)?', txt, re.IGNORECASE):
            continue
            
        if txt:
            # Reemplazar confusiones comunes de OCR en símbolos
            txt = re.sub(r'~', '-', txt)
            
            # Calcular el centro Y y X del texto en la imagen
            y_centro = (box[0][1] + box[2][1]) / 2.0
            x_centro = (box[0][0] + box[1][0]) / 2.0
            
            elementos.append({
                'texto': txt,
                'x': x_centro,
                'y': y_centro
            })

    # 2. Identificar los bloques de equipos (los que tienen ID de 4 o 5 dígitos)
    equipos = []
    cuotas_y_numeros = []

    for el in elementos:
        if re.match(r'^\d{4,5}\b', el['texto']):
            equipos.append(el)
        else:
            cuotas_y_numeros.append(el)

    # Ordenar equipos verticalmente de arriba hacia abajo
    equipos.sort(key=lambda item: item['y'])

    if not equipos:
        return "\n".join([el['texto'] for el in elementos])

    # Crearmos un contenedor para agrupar las cuotas asociadas a cada equipo
    cuotas_por_equipo = {index: [] for index in range(len(equipos))}

    # 3. Asignar CADA cuota al equipo cuya altura Y esté MÁS CERCA
    for num in cuotas_y_numeros:
        # Buscamos el índice del equipo con la distancia 'y' mínima a este número
        idx_equipo_mas_cercano = min(
            range(len(equipos)), 
            key=lambda idx: abs(equipos[idx]['y'] - num['y'])
        )
        cuotas_por_equipo[idx_equipo_mas_cercano].append(num)

    # 4. Construir las líneas finales
    lineas_resultado = []

    for index, eq in enumerate(equipos):
        cuotas_del_equipo = cuotas_por_equipo[index]

        # Ordenar las cuotas de este equipo de izquierda a derecha por X
        cuotas_del_equipo.sort(key=lambda item: item['x'])

        # Unir ID + Nombre del Equipo + sus Cuotas correspondientes
        texto_cuotas = " ".join([c['texto'] for c in cuotas_del_equipo])
        linea_final = f"{eq['texto']} {texto_cuotas}".strip()
        
        lineas_resultado.append(linea_final)

        # Insertar salto de línea en blanco cada 2 equipos (cada pareja de partido)
        if (index + 1) % 2 == 0 and (index + 1) < len(equipos):
            lineas_resultado.append("")

    return "\n".join(lineas_resultado)
