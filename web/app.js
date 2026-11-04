"use strict";

/* ------------------------------------------------------------------ */
/* Utilidades                                                          */
/* ------------------------------------------------------------------ */

const $ = (selector, raiz = document) => raiz.querySelector(selector);
const $$ = (selector, raiz = document) => Array.from(raiz.querySelectorAll(selector));

const formatoNumero = new Intl.NumberFormat("es-PE");
const formatoDecimal = new Intl.NumberFormat("es-PE", { maximumFractionDigits: 2 });

const estado = {
  vista: "consulta",
  consulta: { pagina: 1, paginas: 0, tamano: 50 },
  vinculacion: { pagina: 1, paginas: 0, tamano: 50, a: "", b: "" },
  resumen: null,
};

function crear(etiqueta, opciones = {}, hijos = []) {
  const elemento = document.createElement(etiqueta);
  if (opciones.clase) elemento.className = opciones.clase;
  if (opciones.texto !== undefined && opciones.texto !== null) {
    elemento.textContent = String(opciones.texto);
  }
  if (opciones.atributos) {
    Object.entries(opciones.atributos).forEach(([clave, valor]) => {
      elemento.setAttribute(clave, String(valor));
    });
  }
  hijos.forEach((hijo) => elemento.append(hijo));
  return elemento;
}

function celda(texto, clase = "") {
  return crear("td", { clase, texto: texto ?? "—" });
}

function celdaInsignia(valor, tipo) {
  if (!valor) return celda("—");
  const base = String(valor).toLowerCase();
  const clase = tipo === "sentido"
    ? (base === "entrante" ? "insignia insignia-entrante" : "insignia insignia-saliente")
    : (base === "voz" ? "insignia insignia-voz" : base === "sms" ? "insignia insignia-sms" : "insignia");
  const td = crear("td");
  td.append(crear("span", { clase, texto: valor }));
  return td;
}

function formatearFecha(valor) {
  if (!valor) return "—";
  const soloFecha = String(valor).slice(0, 10);
  const partes = soloFecha.split("-");
  if (partes.length !== 3) return soloFecha;
  return `${partes[2]}/${partes[1]}/${partes[0]}`;
}

function formatearFechaHora(valor) {
  if (!valor) return "—";
  const fecha = new Date(valor);
  if (Number.isNaN(fecha.getTime())) return String(valor);
  return fecha.toLocaleString("es-PE", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

function formatearDuracion(segundos) {
  const total = Number(segundos) || 0;
  if (total < 60) return `${total} s`;
  const minutos = Math.floor(total / 60);
  const resto = total % 60;
  if (minutos < 60) return `${minutos} min ${resto} s`;
  const horas = Math.floor(minutos / 60);
  return `${horas} h ${minutos % 60} min`;
}

function aviso(mensaje, tipo = "info") {
  const contenedor = $("#avisos");
  const elemento = crear("div", { clase: `aviso aviso-${tipo}`, texto: mensaje });
  contenedor.append(elemento);
  window.setTimeout(() => elemento.remove(), 5000);
}

async function api(ruta, opciones = {}) {
  const respuesta = await fetch(ruta, {
    headers: { Accept: "application/json" },
    ...opciones,
  });
  if (!respuesta.ok) {
    let detalle = `Error ${respuesta.status}`;
    try {
      const datos = await respuesta.json();
      detalle = datos.detalle || datos.detail || detalle;
    } catch (error) {
      /* respuesta sin JSON */
    }
    throw new Error(detalle);
  }
  return respuesta.json();
}

function parametros(valores) {
  const busqueda = new URLSearchParams();
  Object.entries(valores).forEach(([clave, valor]) => {
    if (valor !== "" && valor !== null && valor !== undefined) {
      busqueda.set(clave, String(valor));
    }
  });
  return busqueda.toString();
}

/* ------------------------------------------------------------------ */
/* Navegación                                                          */
/* ------------------------------------------------------------------ */

const TITULOS = {
  consulta: ["Consulta", "Busca, filtra y compara comunicaciones."],
  vinculacion: ["Vinculación", "Comunicaciones cruzadas entre dos líneas."],
  estadisticas: ["Estadísticas", "Volumen, duración y distribución de las comunicaciones."],
  cargas: ["Cargas", "Importa archivos y revisa el historial de procesos."],
};

function cambiarVista(nombre) {
  estado.vista = nombre;
  $$(".nav-item").forEach((boton) => {
    boton.classList.toggle("activo", boton.dataset.vista === nombre);
  });
  $$(".vista").forEach((seccion) => {
    seccion.classList.toggle("activa", seccion.id === `vista-${nombre}`);
  });
  const [titulo, subtitulo] = TITULOS[nombre] || ["", ""];
  $("#titulo-vista").textContent = titulo;
  $("#subtitulo-vista").textContent = subtitulo;

  if (nombre === "estadisticas") {
    cargarEstadisticas().catch((error) => aviso(error.message, "error"));
  }
  if (nombre === "cargas") {
    cargarCargas().catch((error) => aviso(error.message, "error"));
  }
}

/* ------------------------------------------------------------------ */
/* Estado general                                                      */
/* ------------------------------------------------------------------ */

async function verificarSalud() {
  const punto = $("#estado-punto");
  const texto = $("#estado-texto");
  try {
    const datos = await api("/api/salud");
    if (datos.base_de_datos) {
      punto.className = "punto punto-ok";
      texto.textContent = "PostgreSQL conectado";
    } else {
      punto.className = "punto punto-error";
      texto.textContent = "Sin base de datos";
    }
  } catch (error) {
    punto.className = "punto punto-error";
    texto.textContent = "Servidor no disponible";
  }
}

async function cargarResumen() {
  try {
    const datos = await api("/api/resumen");
    estado.resumen = datos;
    $("#kpi-total").textContent = formatoNumero.format(datos.total || 0);
    $("#kpi-lineas").textContent = formatoNumero.format(datos.lineas || 0);
    $("#kpi-rango").textContent = datos.primera_fecha
      ? `${formatearFecha(datos.primera_fecha)} – ${formatearFecha(datos.ultima_fecha)}`
      : "—";
  } catch (error) {
    aviso(`No se pudo cargar el resumen: ${error.message}`, "error");
  }
}

/* ------------------------------------------------------------------ */
/* Consulta                                                            */
/* ------------------------------------------------------------------ */

function filtrosConsulta() {
  return {
    numero: $("#c-numero").value.trim(),
    desde: $("#c-desde").value,
    hasta: $("#c-hasta").value,
    tipo: $("#c-tipo").value,
    sentido: $("#c-sentido").value,
    parcial: $("#c-parcial").checked ? "true" : "",
  };
}

function pintarFilas(tbody, filas, desplazamiento) {
  tbody.textContent = "";
  const fragmento = document.createDocumentFragment();
  filas.forEach((fila, indice) => {
    const tr = crear("tr");
    tr.append(
      celda(desplazamiento + indice + 1),
      celda(fila.titular),
      celda(fila.origen || "—"),
      celda(fila.destino || "—"),
      celda(formatearFecha(fila.fecha)),
      celda(fila.hora || "—"),
      celda(formatearDuracion(fila.duracion_seg), "numero"),
      celdaInsignia(fila.tipo, "tipo"),
      celdaInsignia(fila.sentido, "sentido"),
    );
    fragmento.append(tr);
  });
  tbody.append(fragmento);
}

function actualizarPaginacion(prefijo, pagina, paginas, total, tamano) {
  $(`#${prefijo}-pagina`).textContent = paginas
    ? `Página ${pagina} de ${paginas} · ${formatoNumero.format(total)} registros`
    : "Página 0 de 0";
  $(`#${prefijo}-anterior`).disabled = pagina <= 1;
  $(`#${prefijo}-siguiente`).disabled = pagina >= paginas;
}

async function buscarConsulta(pagina = 1) {
  const filtros = filtrosConsulta();
  const consulta = parametros({ ...filtros, pagina, tamano: estado.consulta.tamano });
  const boton = $("#form-consulta button[type='submit']");
  boton.disabled = true;
  boton.textContent = "Buscando…";
  try {
    const datos = await api(`/api/llamadas?${consulta}`);
    estado.consulta.pagina = datos.pagina;
    estado.consulta.paginas = datos.paginas;
    estado.consulta.tamano = datos.tamano;

    pintarFilas($("#c-tabla"), datos.filas, (datos.pagina - 1) * datos.tamano);
    $("#c-vacio").classList.toggle("oculto", datos.total > 0);
    $("#c-resumen").textContent = `${formatoNumero.format(datos.total)} resultados`;
    actualizarPaginacion("c", datos.pagina, datos.paginas, datos.total, datos.tamano);
  } catch (error) {
    aviso(error.message, "error");
  } finally {
    boton.disabled = false;
    boton.textContent = "Buscar";
  }
}

function exportarConsulta() {
  const consulta = parametros(filtrosConsulta());
  const enlace = document.createElement("a");
  enlace.href = `/api/exportar.csv?${consulta}`;
  enlace.download = "llamadas.csv";
  document.body.append(enlace);
  enlace.click();
  enlace.remove();
}

/* ------------------------------------------------------------------ */
/* Vinculación                                                         */
/* ------------------------------------------------------------------ */

function pintarKpis(contenedor, tarjetas) {
  contenedor.textContent = "";
  tarjetas.forEach(([valor, etiqueta]) => {
    const kpi = crear("div", { clase: "kpi" });
    kpi.append(
      crear("span", { texto: valor }),
      crear("small", { texto: etiqueta }),
    );
    contenedor.append(kpi);
  });
  contenedor.classList.toggle("oculto", tarjetas.length === 0);
}

async function buscarVinculacion(pagina = 1) {
  const a = $("#v-a").value.trim();
  const b = $("#v-b").value.trim();
  if (a.length < 8 || b.length < 8) {
    aviso("Ingresa dos números de al menos 8 dígitos.", "error");
    return;
  }
  if (a === b) {
    aviso("Los números A y B deben ser distintos.", "error");
    return;
  }

  estado.vinculacion.a = a;
  estado.vinculacion.b = b;
  const consulta = parametros({ a, b, pagina, tamano: estado.vinculacion.tamano });
  const boton = $("#form-vinculacion button[type='submit']");
  boton.disabled = true;
  boton.textContent = "Buscando…";
  try {
    const datos = await api(`/api/vinculaciones?${consulta}`);
    const resumen = datos.resumen;
    estado.vinculacion.pagina = datos.pagina;
    estado.vinculacion.paginas = datos.paginas;

    pintarKpis($("#v-kpis"), [
      [formatoNumero.format(resumen.total), "comunicaciones"],
      [formatearDuracion(resumen.duracion_total), "duración total"],
      [formatearDuracion(resumen.duracion_promedio), "duración promedio"],
      [formatoNumero.format(resumen.dias), "días con contacto"],
      [formatoNumero.format(resumen.entrantes), "entrantes"],
      [formatoNumero.format(resumen.salientes), "salientes"],
    ]);

    pintarFilas($("#v-tabla"), datos.filas, (datos.pagina - 1) * datos.tamano);
    $("#v-vacio").classList.toggle("oculto", datos.total > 0);
    $("#v-resumen").textContent = `${formatoNumero.format(datos.total)} resultados`;
    actualizarPaginacion("v", datos.pagina, datos.paginas, datos.total, datos.tamano);

    const avisoOrigen = $("#v-aviso-origen");
    const sinOrigen = Number(estado.resumen?.sin_origen || 0);
    if (datos.total === 0 && sinOrigen > 0) {
      avisoOrigen.textContent =
        `Hay ${formatoNumero.format(sinOrigen)} registros sin número de origen ` +
        "que no pueden cruzarse. Carga un archivo que incluya esa columna.";
      avisoOrigen.classList.remove("oculto");
    } else {
      avisoOrigen.classList.add("oculto");
    }
  } catch (error) {
    aviso(error.message, "error");
  } finally {
    boton.disabled = false;
    boton.textContent = "Buscar vinculación";
  }
}

/* ------------------------------------------------------------------ */
/* Estadísticas                                                        */
/* ------------------------------------------------------------------ */

function pintarBarras(contenedor, filas, etiqueta) {
  contenedor.textContent = "";
  if (!filas.length) {
    contenedor.append(crear("p", { clase: "nota", texto: "Sin datos." }));
    return;
  }
  const maximo = Math.max(...filas.map((fila) => Number(fila.total) || 0), 1);
  filas.forEach((fila) => {
    const pista = crear("div", { clase: "barra-pista" });
    const barra = crear("div", { clase: "barra-valor" });
    barra.style.width = `${((Number(fila.total) || 0) / maximo) * 100}%`;
    pista.append(barra);

    contenedor.append(
      crear("div", { clase: "barra-fila" }, [
        crear("span", { clase: "barra-nombre", texto: etiqueta(fila) || "—" }),
        pista,
        crear("span", { clase: "barra-cifra", texto: formatoNumero.format(fila.total) }),
      ]),
    );
  });
}

async function cargarEstadisticas() {
  const filtros = {
    numero: $("#e-numero").value.trim(),
    desde: $("#e-desde").value,
    hasta: $("#e-hasta").value,
    tipo: $("#e-tipo").value,
  };
  const consulta = parametros(filtros);
  const [datos, destinos, tipos, dias] = await Promise.all([
    api(`/api/estadisticas?${consulta}`),
    api(`/api/agregados?${parametros({ ...filtros, por: "destino", limite: 10 })}`),
    api(`/api/agregados?${parametros({ ...filtros, por: "tipo" })}`),
    api(`/api/agregados?${parametros({ ...filtros, por: "dia" })}`),
  ]);

  pintarKpis($("#e-kpis"), [
    [formatoNumero.format(datos.total), "comunicaciones"],
    [formatearDuracion(datos.duracion_total), "duración total"],
    [formatearDuracion(datos.duracion_promedio), "duración promedio"],
    [formatoNumero.format(datos.voz), "llamadas de voz"],
    [formatoNumero.format(datos.sms), "SMS"],
    [formatoNumero.format(datos.dias), "días"],
    [formatoNumero.format(datos.lineas), "líneas"],
  ]);

  pintarBarras($("#e-destinos"), destinos, (fila) => fila.clave);
  pintarBarras($("#e-tipos"), tipos, (fila) => fila.clave);

  const tbody = $("#e-dias");
  tbody.textContent = "";
  const fragmento = document.createDocumentFragment();
  dias.slice().reverse().forEach((fila) => {
    const tr = crear("tr");
    tr.append(
      celda(formatearFecha(fila.clave)),
      celda(formatoNumero.format(fila.total), "numero"),
      celda(formatearDuracion(fila.duracion), "numero"),
    );
    fragmento.append(tr);
  });
  tbody.append(fragmento);
  $("#e-vacio").classList.toggle("oculto", dias.length > 0);
}

/* ------------------------------------------------------------------ */
/* Cargas                                                              */
/* ------------------------------------------------------------------ */

async function cargarCargas() {
  const datos = await api("/api/cargas?limite=25");
  const tbody = $("#cargas-tabla");
  tbody.textContent = "";
  const fragmento = document.createDocumentFragment();

  datos.forEach((carga) => {
    const tr = crear("tr");
    const estadoClase = carga.estado === "ok"
      ? "insignia insignia-ok"
      : carga.estado === "error"
        ? "insignia insignia-error"
        : "insignia";
    const tdEstado = crear("td");
    tdEstado.append(crear("span", {
      clase: estadoClase,
      texto: carga.estado,
      atributos: carga.mensaje_error ? { title: carga.mensaje_error } : {},
    }));

    tr.append(
      celda(carga.id),
      celda(carga.archivo),
      celda(carga.formato),
      celda(formatoNumero.format(carga.filas_leidas), "numero"),
      celda(formatoNumero.format(carga.filas_insertadas), "numero"),
      celda(formatoNumero.format(carga.filas_rechazadas), "numero"),
      tdEstado,
      celda(formatearFechaHora(carga.iniciado_en)),
    );
    fragmento.append(tr);
  });

  if (!datos.length) {
    const tr = crear("tr");
    const td = crear("td", { texto: "Todavía no se ha cargado ningún archivo." });
    td.colSpan = 8;
    tr.append(td);
    fragmento.append(tr);
  }
  tbody.append(fragmento);
}

function pintarResultadoCarga(resultado) {
  const contenedor = $("#carga-resultado");
  contenedor.textContent = "";
  contenedor.append(
    crear("strong", { texto: `Carga completada: ${resultado.archivo}` }),
    crear("div", {
      texto: `Formato ${resultado.formato} · ${formatoNumero.format(resultado.filas_leidas)} leídas · ` +
        `${formatoNumero.format(resultado.filas_insertadas)} insertadas · ` +
        `${formatoNumero.format(resultado.filas_duplicadas)} duplicadas · ` +
        `${formatoNumero.format(resultado.filas_rechazadas)} rechazadas · ` +
        `${formatoDecimal.format(resultado.segundos)} s`,
    }),
  );
  if (resultado.motivos && resultado.motivos.length) {
    const lista = crear("ul");
    resultado.motivos.forEach((motivo) => lista.append(crear("li", { texto: motivo })));
    contenedor.append(lista);
  }
  contenedor.classList.remove("oculto");
}

async function subirArchivo(evento) {
  evento.preventDefault();
  const entrada = $("#archivo");
  if (!entrada.files.length) return;

  const boton = $("#form-carga button[type='submit']");
  boton.disabled = true;
  boton.textContent = "Cargando…";
  const datos = new FormData();
  datos.append("archivo", entrada.files[0]);

  try {
    const resultado = await api("/api/cargar", { method: "POST", body: datos });
    pintarResultadoCarga(resultado);
    aviso("Archivo cargado correctamente.", "ok");
    entrada.value = "";
    await Promise.all([cargarResumen(), cargarCargas(), buscarConsulta(1)]);
  } catch (error) {
    aviso(error.message, "error");
  } finally {
    boton.disabled = false;
    boton.textContent = "Cargar en PostgreSQL";
  }
}

/* ------------------------------------------------------------------ */
/* Arranque                                                            */
/* ------------------------------------------------------------------ */

function conectarEventos() {
  $$(".nav-item").forEach((boton) => {
    boton.addEventListener("click", () => cambiarVista(boton.dataset.vista));
  });

  $("#form-consulta").addEventListener("submit", (evento) => {
    evento.preventDefault();
    buscarConsulta(1);
  });
  $("#c-limpiar").addEventListener("click", () => {
    $("#form-consulta").reset();
    buscarConsulta(1);
  });
  $("#c-exportar").addEventListener("click", exportarConsulta);
  $("#c-anterior").addEventListener("click", () => buscarConsulta(estado.consulta.pagina - 1));
  $("#c-siguiente").addEventListener("click", () => buscarConsulta(estado.consulta.pagina + 1));

  $("#form-vinculacion").addEventListener("submit", (evento) => {
    evento.preventDefault();
    buscarVinculacion(1);
  });
  $("#v-anterior").addEventListener("click", () => buscarVinculacion(estado.vinculacion.pagina - 1));
  $("#v-siguiente").addEventListener("click", () => buscarVinculacion(estado.vinculacion.pagina + 1));

  $("#form-estadisticas").addEventListener("submit", (evento) => {
    evento.preventDefault();
    cargarEstadisticas().catch((error) => aviso(error.message, "error"));
  });

  $("#form-carga").addEventListener("submit", subirArchivo);
  $("#recargar-cargas").addEventListener("click", () => {
    cargarCargas().catch((error) => aviso(error.message, "error"));
  });
}

async function iniciar() {
  conectarEventos();
  await verificarSalud();
  await cargarResumen();
  await buscarConsulta(1);
}

document.addEventListener("DOMContentLoaded", iniciar);
