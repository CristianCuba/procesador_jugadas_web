
// Simplemente asignamos a la variable que ya existe o a window
datosFilas = window.datosFilas || typeof datosFilas !== 'undefined' ? datosFilas : [];

// 2. Función principal de búsqueda de resultados
function ejecutarBusquedaResultados() {
    const btn = document.getElementById('btn-buscar');
    const selectorFecha = document.getElementById('fecha_consulta');
    const fecha = selectorFecha ? selectorFecha.value : 'ayer';
    
    if (!btn) return;
    
    // ESTADO: CARGANDO
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-loader"></span> Buscando resultados...`;

    fetch('/buscar_resultados', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filas: datosFilas, fecha_consulta: fecha })
    })
    .then(async res => {
        const data = await res.json();
        if (!res.ok || !data.success) {
            throw new Error(data.mensaje || `Error HTTP: ${res.status}`);
        }
        return data;
    })
    .then(data => {
        datosFilas = data.filas;
        actualizarTabla(data.filas);
        
        // ESTADO: ÉXITO
        btn.innerHTML = `<i class="bi bi-check-circle-fill text-emerald"></i> Resultados Actualizados`;
        
        // Vuelve a la normalidad después de 3 segundos
        setTimeout(() => {
            btn.disabled = false;
            btn.innerHTML = `<i class="bi bi-search"></i> Consultar Resultados Ahora`;
        }, 3000);
    })
    .catch(err => {
        console.error("Error al buscar resultados:", err);
        if (typeof mostrarNotificacion === 'function') {
            mostrarNotificacion(err.message, 'error');
        } else {
            alert(err.message);
        }
        btn.disabled = false;
        btn.innerHTML = `<i class="bi bi-search"></i> Consultar Resultados Ahora`;
    });

}

    // 2. Actualizar el DOM de la tabla (Sustituye esta función completa en main.js)
function actualizarTabla(filasActualizadas) {
    const tbody = document.querySelector('.table-estilo tbody') || document.querySelector('tbody');
    
    if (!tbody) {
        console.error("No se encontró el elemento <tbody> en la tabla.");
        return;
    }

    if (!filasActualizadas || filasActualizadas.length === 0) {
        console.warn("No hay filas para actualizar.");
        return;
    }

    tbody.innerHTML = ''; // Limpiamos la tabla para redibujarla con los marcadores

    filasActualizadas.forEach(fila => {
        // 1. Fila de Encabezado (Nombre de Cliente/Jugador)
        if (fila.es_head || fila.es_encabezado) {
            const trHead = document.createElement('tr');
            trHead.className = 'fila-jugador-celda';
            trHead.innerHTML = `
                <td colspan="6" style="font-weight: bold; background-color: #1a232e; color: #38bdf8; text-align: left; padding: 8px 12px;">
                    ${fila.jugador || fila.jugada || 'JUGADOR'}
                </td>
            `;
            tbody.appendChild(trHead);
            return;
        }

        // 2. Extraer datos de jugada normal
        const jugador = fila.jugador || '';
        const jugada = fila.jugada || '';
        const monto = fila.monto || '';
        const linea = fila.linea || '';
        const logro = fila.logro || '';
        const resultado = fila.resultado || 'Pendiente';

        // 3. Formato y color del campo RESULTADO
        let estiloResultado = 'color: #eab308; font-style: italic;'; // Amarillo para Pendiente
        const resUpper = String(resultado).trim().toUpperCase();

        if (resUpper === 'G' || resUpper.includes('GAN') || resUpper.includes('VERDE')) {
            estiloResultado = 'color: #10b981; font-weight: bold;'; // Verde
        } else if (resUpper === 'P' || resUpper.includes('PERD') || resUpper.includes('ROJO')) {
            estiloResultado = 'color: #ef4444; font-weight: bold;'; // Rojo
        }

        // 4. Crear la fila TR de 6 columnas
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${jugador}</td>
            <td class="celda-jugada">${jugada}</td>
            <td>${monto ? Number(monto).toLocaleString('en-US') : ''}</td>
            <td>${linea}</td>
            <td>${logro}</td>
            <td class="celda-resultado" style="${estiloResultado}">
                ${resultado}
            </td>
        `;
        tbody.appendChild(tr);
    });
}

    // 3. Copiar la tabla al portapapeles
    function copiarTabla() {
        const tabla = document.getElementById('tabla-datos');
        if (!tabla) {
            alert("No hay datos en la tabla para copiar.");
            return;
        }

        let textoCopiar = "";
        const filas = tabla.querySelectorAll('tr');

        filas.forEach(fila => {
            const celdas = fila.querySelectorAll('th, td');
            let filaTexto = [];
            
            celdas.forEach(celda => {
                let textoLimpio = celda.innerText.replace(/\r?\n|\r/g, " ").trim();
                filaTexto.push(textoLimpio);
            });

            if (filaTexto.length > 0) {
                textoCopiar += filaTexto.join("\t") + "\n";
            }
        });

        navigator.clipboard.writeText(textoCopiar)
            .then(() => {
                const btn = document.getElementById('btn-copiar');
                if (btn) {
                    const textoOriginal = btn.innerText;
                    btn.innerText = "✅ ¡Copiado!";
                    setTimeout(() => {
                        btn.innerText = textoOriginal;
                    }, 2000);
                }
            })
            .catch(err => {
                console.error("Error al copiar: ", err);
                alert("No se pudo copiar automáticamente.");
            });
    }

    // 4. Agregar alias / equivalencias
    function agregarAlias() {
        const oficial = document.getElementById('equipo_oficial').value;
        const alias = document.getElementById('nuevo_alias').value;
        const mensajeDiv = document.getElementById('mensaje-respuesta');

        if (!oficial || !alias.trim()) {
            mensajeDiv.className = "mensaje-alerta error";
            mensajeDiv.innerText = "Selecciona un equipo e ingresa un alias.";
            mensajeDiv.style.display = "block";
            return;
        }

        fetch('/agregar_equivalencia', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ oficial: oficial, alias: alias })
        })
        .then(res => res.json())
        .then(data => {
            mensajeDiv.style.display = "block";
            if (data.success) {
                mensajeDiv.className = "mensaje-alerta exito";
                mensajeDiv.innerText = data.mensaje;
                document.getElementById('nuevo_alias').value = '';
            } else {
                mensajeDiv.className = "mensaje-alerta error";
                mensajeDiv.innerText = data.mensaje;
            }
        });
    }

    // 5. Procesar texto raw de fútbol
    function procesarTextoFutbol() {
        const texto = document.getElementById('texto_raw_futbol').value;
        const msg = document.getElementById('mensaje-futbol');
        if (!texto.trim()) {
            msg.className = "mensaje-alerta error";
            msg.innerText = "Por favor pega algún texto.";
            msg.style.display = "block";
            return;
        }

        msg.className = "mensaje-alerta exito";
        msg.innerText = "Verificando base de datos local...";
        msg.style.display = "block";

        fetch('/importar_raw_futbol', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ raw_text: texto })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                msg.className = "mensaje-alerta exito";
                msg.innerText = `¡Proceso terminado! ${data.nuevos} equipos nuevos agregados. (${data.omitidos} ya existían y fueron omitidos).`;
                document.getElementById('texto_raw_futbol').value = '';
            } else {
                msg.className = "mensaje-alerta error";
                msg.innerText = "Error al procesar el texto.";
            }
        })
        .catch(err => {
            msg.className = "mensaje-alerta error";
            msg.innerText = "Error en el servidor.";
        });
    }
   async function cargarPikesML() {
    const filasHTML = document.querySelectorAll('#tabla-datos tbody tr');
    let filasData = [];

    // 1. Recorrer la tabla fila por fila
    filasHTML.forEach((tr, index) => {
        // Omitir filas de encabezado/cliente
        if (tr.classList.contains('fila-jugador-celda')) return;

        const equipo = tr.cells[1]?.innerText.trim(); // Columna "JUGADA"
        const linea = tr.cells[3]?.innerText.trim().toUpperCase(); // Columna "LINEA"

        // REGLA CLAVE: Solo procesamos si en la Columna Línea (cells[3]) dice "ML"
        if (linea === "ML" && equipo !== "") {
            filasData.push({
                index: index,
                jugada: equipo // Nombre del equipo para buscar en los pikes cargados
            });
        }
    });

    if (filasData.length === 0) {
        alert("⚠️ No se encontraron filas que tengan 'ML' en la columna Línea.");
        return;
    }

    try {
        // 2. Consultar el servidor
        const response = await fetch('/procesar_pikes_ml', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filas: filasData })
        });

        const res = await response.json();
        console.log("📥 Respuesta servidor:", res);

        if (res.success) {
            let actualizados = 0;

            // 3. ACTUALIZAR EL DOM/TABLA HTML
            res.filas.forEach(fila => {
                if (fila.pike1) {
                    const tr = filasHTML[fila.index];
                    if (tr) {
                        // Asignar cuota ML en la columna LOGRO (celda index 4)
                        tr.cells[4].innerText = fila.pike1;
                        
                        // Resaltar visualmente la celda modificada
                        tr.cells[4].style.backgroundColor = "rgba(74, 222, 128, 0.2)";
                        actualizados++;
                    }
                }
            });

            alert(`✅ Se asignaron ${actualizados} pikes ML correctamente.`);
        } else {
            alert(`❌ Error en Python: ${res.mensaje}\n\nRevisa la consola (F12) para el detalle.`);
            console.error("Detalle del error Python:", res.trace);
        }
    } catch (err) {
        console.error("❌ Error en JavaScript:", err);
        alert("Ocurrió un error al procesar los pikes ML.");
    }
}
async function cargarPikesRL() {
    const filasHTML = document.querySelectorAll('table tbody tr');
    let filasData = [];

    // 1. Recorrer la tabla y filtrar
    filasHTML.forEach((tr, index) => {
        const cliente = tr.cells[0]?.innerText.trim();
        const equipo = tr.cells[1]?.innerText.trim().toUpperCase() || "";
        const lineaActual = tr.cells[3]?.innerText.trim().toUpperCase() || ""; // Columna Línea

        // PROTECCIÓN CRÍTICA: Si ya es ML, NO TOCAR.
        if (lineaActual === "ML" || lineaActual.includes("ML")) {
            return; // Salta esta fila por completo
        }

        // Exclusiones adicionales
        const esAltaOBaja = equipo.includes("ALTA") || equipo.includes("BAJA") || equipo.includes("OVER") || equipo.includes("UNDER");
        const esInvalido = equipo.includes("PARLEY") || equipo.includes("TRIPLETA") || equipo === cliente || equipo === "";

        if (!esAltaOBaja && !esInvalido) {
            filasData.push({
                index: index,
                jugada: equipo,
                linea_actual: lineaActual
            });
        }
    });

    if (filasData.length === 0) {
        alert("⚠️ No se encontraron jugadas candidatas para RL (o todas son ML).");
        return;
    }

    try {
        // 2. Enviar los datos al backend
        const response = await fetch('/procesar_pikes_rl', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filas: filasData })
        });

        const res = await response.json();

        if (res.success) {
            let actualizados = 0;

            // 3. Escribir únicamente en las celdas autorizadas
            res.filas.forEach((fila) => {
                if (filasHTML[fila.index]) {
                    const celdaLinea = filasHTML[fila.index].cells[3]; // Columna Línea
                    const celdaPike  = filasHTML[fila.index].cells[4]; // Columna Logro

                    // Verificar nuevamente por seguridad que la celda no sea ML
                    if (celdaLinea && celdaLinea.innerText.trim().toUpperCase() !== "ML") {
                        if (fila.linea_rl) celdaLinea.innerText = fila.linea_rl; 
                        if (celdaPike && fila.cuota_rl) celdaPike.innerText = fila.cuota_rl;
                        actualizados++;
                    }
                }
            });

            alert(`✅ Se asignaron ${actualizados} pikes RL (respetando las jugadas ML).`);
        } else {
            alert("❌ Error: " + res.mensaje);
        }
    } catch (err) {
        console.error("❌ Error en JavaScript:", err);
        alert("Ocurrió un error al procesar los pikes RL.");
    }
}
async function cargarPikesAltasBajas() {
    const filasHTML = document.querySelectorAll('table tbody tr');
    let filasData = [];

    // 1. Filtrar filas que contengan ALTA o BAJA
    filasHTML.forEach((tr, index) => {
        const equipo = tr.cells[1]?.innerText.trim().toUpperCase() || "";
        const lineaActual = tr.cells[3]?.innerText.trim().toUpperCase() || "";

        // Solo tomar filas con ALTA, BAJA, OVER o UNDER
        const esAltaOBaja = equipo.includes("ALTA") || equipo.includes("BAJA") || equipo.includes("OVER") || equipo.includes("UNDER");

        if (esAltaOBaja && equipo !== "") {
            filasData.push({
                index: index,
                jugada: equipo
            });
        }
    });

    if (filasData.length === 0) {
        alert("⚠️ No se encontraron jugadas de Altas/Bajas para procesar.");
        return;
    }

    try {
        // 2. Enviar a procesar
        const response = await fetch('/procesar_pikes_altas_bajas', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filas: filasData })
        });

        const res = await response.json();

        if (res.success) {
            let actualizados = 0;

            // 3. Escribir en la tabla
            res.filas.forEach((fila) => {
                if (filasHTML[fila.index]) {
                    const celdaLinea = filasHTML[fila.index].cells[3]; // Columna Línea (ej: 8.5)
                    const celdaPike  = filasHTML[fila.index].cells[4]; // Columna Logro (-120)

                    if (celdaLinea && fila.linea_ab) celdaLinea.innerText = fila.linea_ab;
                    if (celdaPike && fila.cuota_ab) celdaPike.innerText = fila.cuota_ab;

                    actualizados++;
                }
            });

            alert(`✅ Se asignaron ${actualizados} pikes de Altas/Bajas correctamente (-120).`);
        } else {
            alert("❌ Error: " + res.mensaje);
        }
    } catch (err) {
        console.error("❌ Error en JavaScript:", err);
        alert("Ocurrió un error al procesar Altas/Bajas.");
    }
}
// 1. EVENTO DEL BOTÓN 1: DESCARGAR Y GUARDAR MARCADORES
async function guardarMarcadoresAPI() {
    let response = await fetch('/guardar_marcadores_api', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fecha_consulta: 'ayer' })
    });
    let data = await response.json();
    if (data.success) {
        alert("✅ Marcadores guardados en JSON correctamente.");
    } else {
        alert("❌ Error al guardar marcadores: " + data.mensaje);
    }
}

// 2. EVENTO DEL BOTÓN 2: EVALUAR LOCALMENTE Y PINTAR G, P, T
async function mostrarResultados() {
    // Obtenemos las filas/jugadas actuales de tu tabla o estado
    let filasActuales = obtenerFilasDeLaTabla(); 

    let response = await fetch('/procesar_resultados_locales', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filas: filasActuales })
    });
    let data = await response.json();

    if (data.success) {
        // Actualizamos la tabla visual con las filas que ya traen 'G', 'P' o 'T'
        actualizarTablaVisual(data.filas); 
    } else {
        alert("❌ Error: " + data.mensaje);
    }
}
async function ejecutarEvaluacionLocal() {
    // Tomamos las filas actuales cargadas en tu tabla/app
    let filasActuales = window.filasTabla || []; 

    let response = await fetch('/procesar_resultados_locales', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filas: filasActuales })
    });
    
    let data = await response.json();

    if (data.success) {
        // Renderiza tu tabla con las filas actualizadas
        if (typeof renderizarTabla === 'function') {
            renderizarTabla(data.filas);
        } else {
            location.reload();
        }
    } else {
        alert("⚠️ " + data.mensaje);
    }
}
// Pequeño JS para que muestre el nombre del archivo seleccionado
function actualizarNombreArchivo(input) {
    const texto = document.getElementById('texto-archivo');
    if (input.files && input.files[0]) {
        texto.textContent = input.files[0].name;
    } else {
        texto.textContent = 'Seleccionar Archivo Excel...';
    }
}
function mostrarNotificacion(mensaje, tipo = 'exito') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast-notificacion toast-${tipo}`;
    
    const icono = tipo === 'exito' 
        ? '<i class="bi bi-check-circle-fill"></i>' 
        : '<i class="bi bi-exclamation-triangle-fill"></i>';

    toast.innerHTML = `${icono} <span>${mensaje}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('toast-ocultar');
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}
function aplicarFiltroTabla() {
    const textoFiltro = document.getElementById('inputFiltro').value.toUpperCase();
    const tabla = document.getElementById('tablaApuestas');
    const filas = tabla.querySelectorAll('tbody tr');

    let headerActual = null;
    let apuestasVisiblesEnHeader = 0;

    filas.forEach(fila => {
        // Detectar si es una fila de Encabezado de Jugador
        if (fila.classList.contains('jugador-header') || fila.cells.length === 1) {
            // Evaluar el header anterior: si no tuvo apuestas visibles, lo ocultamos
            if (headerActual) {
                headerActual.style.display = (apuestasVisiblesEnHeader > 0) ? '' : 'none';
            }
            
            // Iniciar nuevo bloque de jugador
            headerActual = fila;
            apuestasVisiblesEnHeader = 0;
            fila.style.display = ''; // Visible temporalmente
        } 
        // Es una fila de Apuesta / Jugada
        else {
            const contenidoFila = fila.textContent.toUpperCase();
            
            if (contenidoFila.includes(textoFiltro)) {
                fila.style.display = '';
                apuestasVisiblesEnHeader++;
            } else {
                fila.style.display = 'none';
            }
        }
    });

    // Evaluar el último header al finalizar el ciclo
    if (headerActual) {
        headerActual.style.display = (apuestasVisiblesEnHeader > 0) ? '' : 'none';
    }
}

async function guardarResultadosEnJSON() {
    const comboFecha = document.getElementById('fecha_consulta');
    const fechaSeleccionada = comboFecha ? comboFecha.value : 'ayer';

    // ⏳ Mostrar notificación de carga
    Swal.fire({
        title: 'Buscando marcadores...',
        text: 'Consultando la API oficial de la MLB',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });

    try {
        const respuesta = await fetch('/guardar_marcadores_api', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ fecha_consulta: fechaSeleccionada })
        });

        const data = await respuesta.json();

        if (data.success) {
            // 🎉 Modal de Éxito
            Swal.fire({
                icon: 'success',
                title: '¡Marcadores Guardados!',
                text: `${data.mensaje} (${data.total_equipos} equipos guardados en JSON)`,
                confirmButtonColor: '#3085d6',
                confirmButtonText: 'Aceptar'
            });
        } else {
            // ⚠️ Modal de Error desde Servidor
            Swal.fire({
                icon: 'error',
                title: 'Ocurrió un problema',
                text: data.mensaje,
                confirmButtonColor: '#d33'
            });
        }
    } catch (error) {
        console.error("Error en la petición:", error);
        // ❌ Modal de Error de Red/Servidor
        Swal.fire({
            icon: 'error',
            title: 'Error de conexión',
            text: 'No se pudo conectar con el servidor Flask.',
            confirmButtonColor: '#d33'
        });
    }
}
// Objeto global para llevar el control de los 3 requisitos
const estadoProcesos = {
    pikes: false,
    ml_rl: false,
    altas_bajas: false
};

async function pintarResultadosEnTabla() {
    const filasHTML = document.querySelectorAll('.table-estilo tbody tr') || document.querySelectorAll('table tbody tr');
    let filasData = [];

    if (filasHTML.length === 0) {
        Swal.fire({ icon: 'warning', title: 'Tabla vacía', text: 'No hay filas en la tabla.' });
        return;
    }

    // Extraer equipo (cells[1]) y línea/pike (cells[3])
    filasHTML.forEach((tr, index) => {
        const esEncabezado = tr.classList.contains('fila-jugador-celda') || tr.classList.contains('fila-encabezado');
        const equipo = tr.cells[1]?.innerText.trim() || "";
        const linea = tr.cells[3]?.innerText.trim() || "0.0"; // Columna de Línea/Pike

        if (!esEncabezado && equipo !== "") {
            filasData.push({
                index: index,
                jugada: equipo,
                linea: linea
            });
        }
    });

    try {
        const response = await fetch('/pintar_resultados_tabla', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filas: filasData })
        });

        const res = await response.json();

        if (res.success) {
            let actualizados = 0;

            res.filas.forEach((fila) => {
                if (filasHTML[fila.index]) {
                    const celdaResultado = filasHTML[fila.index].cells[5] || filasHTML[fila.index].querySelector('.celda-resultado');

                    if (celdaResultado) {
                        celdaResultado.innerText = fila.resultado;
                        
                        // Formato de colores automático
                        if (fila.resultado === 'G') {
                            celdaResultado.style.color = '#10b981'; // Verde
                            celdaResultado.style.fontWeight = 'bold';
                        } else if (fila.resultado === 'P') {
                            celdaResultado.style.color = '#ef4444'; // Rojo
                            celdaResultado.style.fontWeight = 'bold';
                        } else if (fila.resultado === 'T') {
                            celdaResultado.style.color = '#eab308'; // Amarillo
                            celdaResultado.style.fontWeight = 'bold';
                        }

                        actualizados++;
                    }
                }
            });

            Swal.fire({
                icon: 'success',
                title: 'Evaluación Completada',
                text: `Se evaluaron ${actualizados} jugadas en la tabla.`,
                timer: 2000,
                showConfirmButton: false
            });
        } else {
            Swal.fire({ icon: 'error', title: 'Atención', text: res.mensaje });
        }
    } catch (err) {
        console.error("❌ Error al procesar evaluación:", err);
        Swal.fire({ icon: 'error', title: 'Error', text: 'Ocurrió un error al conectar con el servidor.' });
    }
}
let miGraficoBalance = null;

// 1. Renderiza o actualiza el gráfico con animación fluida
function renderizarGraficoBalance(totalGanado, totalPerdido) {
    const ctx = document.getElementById('graficoBalance')?.getContext('2d');
    if (!ctx) return;

    // Si no hay datos (todo en 0), mostramos un aro gris neutro
    const sinDatos = totalGanado === 0 && totalPerdido === 0;
    const dataValores = sinDatos ? [1] : [totalGanado, totalPerdido];
    const dataColores = sinDatos ? ['#334155'] : ['#10b981', '#ef4444'];

    if (miGraficoBalance) {
        miGraficoBalance.data.datasets[0].data = dataValores;
        miGraficoBalance.data.datasets[0].backgroundColor = dataColores;
        miGraficoBalance.update();
    } else {
        miGraficoBalance = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Ganancias', 'Pérdidas'],
                datasets: [{
                    data: dataValores,
                    backgroundColor: dataColores,
                    borderColor: '#0f172a',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: !sinDatos }
                },
                cutout: '75%'
            }
        });
    }
}

// 2. Filtra filas y recalcula el gráfico en TIEMPO REAL
function filtrarTablaResultados() {
    const input = document.getElementById('filtro-tabla');
    if (!input) return;

    const query = input.value.toLowerCase().trim();
    const filas = document.querySelectorAll('#tabla-datos tbody tr');

    let totalGanado = 0;
    let totalPerdido = 0;

    filas.forEach(tr => {
        // Ignorar filas especiales o vacías si aplica
        if (tr.classList.contains('fila-jugador-celda')) {
            return;
        }

        const textoFila = tr.innerText.toLowerCase();
        
        // Si coincide con la búsqueda
        if (textoFila.includes(query)) {
            tr.style.display = ''; // Mostrar fila

            // Leer valores si la fila está visible y ya tiene balance calculado
            const resultado = tr.cells[5]?.innerText.trim().toUpperCase() || "";
            const montoTxt = tr.cells[2]?.innerText.trim() || "0";
            const logroTxt = tr.cells[4]?.innerText.trim() || "0";

            const monto = parseFloat(montoTxt.replace(/[^0-9.-]+/g, "")) || 0;
            const logro = parseFloat(logroTxt.replace(/[^0-9.-]+/g, "")) || 0;

            if (resultado === 'G') {
                totalGanado += (logro < 0) ? monto : monto * (logro / 100);
            } else if (resultado === 'P') {
                const perdida = (logro < 0) ? (monto * (Math.abs(logro) / 100)) : monto;
                totalPerdido += perdida;
            }
        } else {
            tr.style.display = 'none'; // Ocultar fila
        }
    });

    // Actualizar etiquetas numéricas
    const totalNeto = totalGanado - totalPerdido;
    
    document.getElementById('txt_total_ganado').innerText = `+$${totalGanado.toFixed(2)}`;
    document.getElementById('txt_total_perdido').innerText = `-$${totalPerdido.toFixed(2)}`;
    
    const elemNeto = document.getElementById('txt_total_neto');
    elemNeto.innerText = `${totalNeto >= 0 ? '+' : ''}$${totalNeto.toFixed(2)}`;
    elemNeto.style.color = totalNeto >= 0 ? '#10b981' : '#ef4444';

    // Actualizar el gráfico circular dinámicamente
    renderizarGraficoBalance(totalGanado, totalPerdido);
}

// 3. Modificamos calcularBalanceTabla para que al finalizar llame al filtro automáticamente
function calcularBalanceTabla() {
    const filas = document.querySelectorAll('#tabla-datos tbody tr');
    let procesados = 0;

    filas.forEach(tr => {
        if (tr.classList.contains('fila-jugador-celda')) return;

        const celdaResObj = tr.cells[5] || tr.querySelector('.celda-resultado');
        const resultado = celdaResObj ? celdaResObj.innerText.trim().toUpperCase() : "";

        if (resultado !== 'G' && resultado !== 'P' && resultado !== 'T') return;

        const montoTxt = tr.cells[2]?.innerText.trim() || "0";
        const logroTxt = tr.cells[4]?.innerText.trim() || "0";

        const monto = parseFloat(montoTxt.replace(/[^0-9.-]+/g, "")) || 0;
        const logro = parseFloat(logroTxt.replace(/[^0-9.-]+/g, "")) || 0;

        let balanceJugada = 0;

        if (resultado === 'G') {
            balanceJugada = (logro < 0) ? monto : monto * (logro / 100);
        } else if (resultado === 'P') {
            balanceJugada = (logro < 0) ? -1 * (monto * (Math.abs(logro) / 100)) : -1 * monto;
        } else if (resultado === 'T') {
            balanceJugada = 0;
        }

        let celdaBalance = tr.cells[6];
        if (!celdaBalance) celdaBalance = tr.insertCell(6);

        celdaBalance.innerText = (balanceJugada >= 0 ? "+" : "") + balanceJugada.toFixed(2);
        celdaBalance.style.fontWeight = 'bold';
        celdaBalance.style.color = balanceJugada > 0 ? '#10b981' : (balanceJugada < 0 ? '#ef4444' : '#9ca3af');
        
        procesados++;
    });

    // Actualizar vista filtrada y gráfico
    filtrarTablaResultados();

    if (procesados > 0) {
        Swal.fire({
            icon: 'success',
            title: 'Balance Calculado',
            text: `Se calcularon ${procesados} jugadas con éxito.`,
            timer: 1500,
            showConfirmButton: false
        });
    }
}
// Mostrar u ocultar el botón flotante según la posición del scroll
window.addEventListener('scroll', () => {
    const btnScroll = document.getElementById('btn-scroll-top');
    if (!btnScroll) return;

    // Se muestra si el usuario ha bajado más de 250px
    if (window.scrollY > 250) {
        btnScroll.classList.add('visible');
    } else {
        btnScroll.classList.remove('visible');
    }
});

// Función para volver arriba de forma fluida
function volverArriba() {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
}


//OCR
// Función para obtener las reglas del deporte activo
function getReglasActivas() {
    const deporte = document.getElementById('switchDeporte').checked ? 'FUTBOL' : 'MLB';
    const storageKey = deporte === 'FUTBOL' ? 'reglas_ocr_futbol' : 'reglas_ocr_mlb';
    return JSON.parse(localStorage.getItem(storageKey) || '{}');
}

// Función para guardar una nueva regla
function agregarRegla(textoErroneo, textoCorrecto) {
    const deporte = document.getElementById('switchDeporte').checked ? 'FUTBOL' : 'MLB';
    const storageKey = deporte === 'FUTBOL' ? 'reglas_ocr_futbol' : 'reglas_ocr_mlb';
    
    let reglas = JSON.parse(localStorage.getItem(storageKey) || '{}');
    reglas[textoErroneo] = textoCorrecto;
    
    localStorage.setItem(storageKey, JSON.stringify(reglas));
    renderizarTablaReglas(); // Recarga la tabla visible
}

// Al cambiar el switch de deporte, refrescas la tabla visual
document.getElementById('switchDeporte').addEventListener('change', () => {
    renderizarTablaReglas();
});
async function procesarImagen(file) {
    const deporte = document.getElementById('switchDeporte').checked ? 'FUTBOL' : 'MLB';
    const reglas = getReglasActivas(); // Carga solo reglas de Fútbol o solo de MLB

    const formData = new FormData();
    formData.append('file', file);
    formData.append('deporte', deporte);
    formData.append('reglas', JSON.stringify(reglas));

    const response = await fetch('/api/procesar-ocr', {
        method: 'POST',
        body: formData
    });
    
    const data = await response.json();
    // Renderizar resultado...
}
//PINTANDO PIKES RL DE FUTBOL
async function cargarPikesRLFutbol() {
    console.log("🚀 [MAIN.JS] Ejecutando cargarPikesRLFutbol...");

    const filasHTML = document.querySelectorAll('#tabla-datos tbody tr, table tbody tr');
    let filasData = [];

    filasHTML.forEach((tr, index) => {
        if (tr.classList.contains('fila-jugador-celda')) return;

        const celdaJugada = tr.querySelector('.celda-jugada') || tr.cells[1];
        const equipo = celdaJugada ? celdaJugada.innerText.trim() : "";

        if (equipo !== "") {
            filasData.push({
                index: index,
                jugada: equipo
            });
        }
    });

    console.log(`📊 [MAIN.JS] ${filasData.length} filas capturadas:`, filasData);

    if (filasData.length === 0) {
        alert("⚠️ No se encontraron jugadas en la tabla.");
        return;
    }

    try {
        console.log("📡 [MAIN.JS] Enviando petición POST a /procesar_pikes_rl_futbol...");

        const response = await fetch('/procesar_pikes_rl_futbol', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filas: filasData })
        });

        if (!response.ok) {
            console.error(`❌ Error HTTP ${response.status}`);
            alert(`❌ Error HTTP ${response.status} en la petición.`);
            return;
        }

        const res = await response.json();
        console.log("📥 [MAIN.JS] Respuesta recibida:", res);

        if (res.success) {
            let actualizados = 0;

            res.filas.forEach((fila) => {
                if (filasHTML[fila.index]) {
                    const celdaLinea = filasHTML[fila.index].cells[3];
                    const celdaLogro = filasHTML[fila.index].cells[4];

                    if (celdaLinea && fila.linea_rl) celdaLinea.innerText = fila.linea_rl;
                    if (celdaLogro && fila.cuota_rl) celdaLogro.innerText = fila.cuota_rl;

                    if (fila.linea_rl || fila.cuota_rl) actualizados++;
                }
            });

            alert(`✅ Se asignaron ${actualizados} pikes de RL Fútbol correctamente.`);
        } else {
            alert("❌ Error: " + res.mensaje);
        }
    } catch (err) {
        console.error("❌ Error JS:", err);
        alert("Ocurrió un error al procesar la petición.");
    }
}
//ALTAS Y BAJAS FUTBOL
async function cargarPikesOUFutbol() {
    console.log("🚀 [MAIN.JS] Ejecutando cargarPikesOUFutbol...");

    const filasHTML = document.querySelectorAll('#tabla-datos tbody tr, table tbody tr');
    let filasData = [];

    filasHTML.forEach((tr, index) => {
        if (tr.classList.contains('fila-jugador-celda')) return;

        const celdaJugada = tr.querySelector('.celda-jugada') || tr.cells[1];
        const jugadaTexto = celdaJugada ? celdaJugada.innerText.trim() : "";

        if (jugadaTexto !== "") {
            filasData.push({
                index: index,
                jugada: jugadaTexto
            });
        }
    });

    console.log(`📊 [MAIN.JS] ${filasData.length} filas capturadas para Altas/Bajas:`, filasData);

    if (filasData.length === 0) {
        alert("⚠️ No se encontraron jugadas en la tabla.");
        return;
    }

    try {
        console.log("📡 [MAIN.JS] Enviando petición POST a /procesar_pikes_ou_futbol...");

        const response = await fetch('/procesar_pikes_ou_futbol', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filas: filasData })
        });

        if (!response.ok) {
            console.error(`❌ Error HTTP ${response.status}`);
            alert(`❌ Error HTTP ${response.status} en la petición.`);
            return;
        }

        const res = await response.json();
        console.log("📥 [MAIN.JS] Respuesta recibida:", res);

        if (res.success) {
            let actualizados = 0;

            res.filas.forEach((fila) => {
                if (filasHTML[fila.index]) {
                    const celdaLinea = filasHTML[fila.index].cells[3]; // Columna Línea
                    const celdaLogro = filasHTML[fila.index].cells[4]; // Columna Logro

                    if (celdaLinea && fila.linea_ou) celdaLinea.innerText = fila.linea_ou;
                    if (celdaLogro && fila.cuota_ou) celdaLogro.innerText = fila.cuota_ou;

                    if (fila.linea_ou || fila.cuota_ou) actualizados++;
                }
            });

            alert(`✅ Se asignaron ${actualizados} pikes de Altas/Bajas Fútbol correctamente.`);
        } else {
            alert(`❌ Error: ${res.mensaje}`);
        }
    } catch (err) {
        console.error("❌ Error JS:", err);
        alert("Ocurrió un error al procesar las Altas/Bajas.");
    }
}

// Función auxiliar para limpiar tildes y mayúsculas
function limpiarNombreEquipo(texto) {
    if (!texto) return '';
    return texto.toLowerCase()
        .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
        .trim();
}

//PARLEY


function calcularParleysEnTabla() {
    const filas = document.querySelectorAll("#tabla-datos tbody tr");
    
    let i = 0;
    while (i < filas.length) {
        const filaActual = filas[i];
        const celdasActuales = filaActual.cells;
        
        let textoFila = filaActual.innerText.toUpperCase();

        if (textoFila.includes("PARLEY")) {
            // 1. Extraer el monto apostado directamente de la fila PARLEY
            let montoApostado = 0;
            for (let c = 0; c < celdasActuales.length; c++) {
                let txtVal = celdasActuales[c].innerText.trim();
                if (txtVal && !isNaN(parseFloat(txtVal)) && parseFloat(txtVal) > 0 && !txtVal.includes("+") && !txtVal.includes("-")) {
                    montoApostado = parseFloat(txtVal);
                    break;
                }
            }

            let multiplicadorAcumulado = 1.0;
            let parleyGanado = true;
            let jugadasEvaluadas = 0;

            let j = i + 1;

            // 2. Recorrer las jugadas pertenecientes al Parley
            while (j < filas.length) {
                const filaJugada = filas[j];
                
                // Si llegamos a una nueva cabecera o fila divisora, cortamos
                if (filaJugada.classList.contains("fila-jugador-celda") || filaJugada.innerText.toUpperCase().includes("PARLEY")) {
                    break;
                }

                const celdas = filaJugada.cells;
                if (celdas.length >= 6) {
                    const logroText = celdas[4] ? celdas[4].innerText.trim() : "";
                    const resultadoText = celdas[5] ? celdas[5].innerText.trim().toUpperCase() : "";

                    const logroNum = parseFloat(logroText);

                    if (resultadoText === "P" || resultadoText.includes("PERDIDO")) {
                        parleyGanado = false;
                        jugadasEvaluadas++;
                        break; // Se perdió una jugada, se pierde el parley completo
                    } 
                    else if (resultadoText === "G" || resultadoText.includes("GANADO")) {
                        jugadasEvaluadas++;
                        
                        let factor = 1.0;
                        if (!isNaN(logroNum)) {
                            if (logroNum < 0) {
                                factor = 1.0 + (100.0 / Math.abs(logroNum));
                            } else {
                                factor = 1.0 + (logroNum / 100.0);
                            }
                        }
                        multiplicadorAcumulado *= factor;
                    } 
                    // CASOS TABLA / EMPATE / ANULADO / PUSH / SUSPENDIDO
                    else if (resultadoText === "T" || resultadoText === "E" || resultadoText.includes("PUSH") || resultadoText === "-") {
                        jugadasEvaluadas++;
                        multiplicadorAcumulado *= 1.0; // Factor 1.0 (se elimina del cálculo, mantiene lo ganado en los otros)
                    } 
                    else {
                        // Pendiente o sin evaluar todavía
                        parleyGanado = false;
                        break;
                    }
                }
                j++;
            }

            // 3. Escribir la Ganancia Neta en la celda Balance (sin decimales)
            const celdaBalance = celdasActuales[celdasActuales.length - 1];

            if (parleyGanado && jugadasEvaluadas > 0) {
                const gananciaNeta = montoApostado * (multiplicadorAcumulado - 1.0);
                
                // Math.floor quita los decimales dejando solo la parte entera
                const gananciaEntera = Math.floor(gananciaNeta);
                
                celdaBalance.innerText = "+" + gananciaEntera;
                celdaBalance.style.color = "#10b981"; // Verde
                celdaBalance.style.fontWeight = "bold";
            } else if (!parleyGanado && jugadasEvaluadas > 0) {
                const montoEntero = Math.floor(montoApostado);
                
                celdaBalance.innerText = "-" + montoEntero;
                celdaBalance.style.color = "#ef4444"; // Rojo
                celdaBalance.style.fontWeight = "bold";
            }

            i = j;
        } else {
            i++;
        }
    }

    if (typeof calcularBalanceTabla === 'function') {
        calcularBalanceTabla();
    }
}