"""
Sistema de Consulta de Vinculaciones Telefónicas - DIVIAC
Versión optimizada con sistema de autenticación
"""
import psycopg2
from psycopg2 import pool
from datetime import datetime
import getpass
import os
from contextlib import contextmanager
import logging
import hashlib
import time

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('vinculaciones.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuración de base de datos
# NOTA: la contraseña original se eliminó de este repositorio por seguridad.
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'comunicaciones'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', ''),
    'port': os.getenv('DB_PORT', '5432')
}

# Usuarios autorizados
# NOTA: los hashes de contraseñas se eliminaron del repositorio público.
# En el script original había tres usuarios: admin, analista1 e investigador.
USUARIOS_AUTORIZADOS = {}

# Pool de conexiones
connection_pool = None

# Campos a mostrar
CAMPOS_MOSTRAR = ['titular', 'imei', 'destino_cod', 'fecha_txt', 'hora_txt', 
                'duracion_seg', 'tipo', 'entrante_saliente']

# Configuración de tabla
ANCHOS_COLUMNA = {
    '#': 5,
    'titular': 15,
    'imei': 18,
    'destino_cod': 15,
    'fecha_txt': 12,
    'hora_txt': 10,
    'duracion_seg': 12,
    'tipo': 8,
    'entrante_saliente': 18
}

# Variable global para usuario actual
usuario_actual = None
intentos_fallidos = 0
MAX_INTENTOS = 3

def mostrar_banner_login():
    """Muestra el banner de inicio de sesión"""
    os.system('clear' if os.name == 'posix' else 'cls')
    print("\n")
    print("╔" + "═"*78 + "╗")
    print("║" + " "*78 + "║")
    print("║" + "SISTEMA DE CONSULTA DE VINCULACIONES TELEFÓNICAS".center(78) + "║")
    print("║" + "DIVISIÓN DE INVESTIGACIÓN DE ALTA COMPLEJIDAD - DIVIAC".center(78) + "║")
    print("║" + "DEPARTAMENTO DE SOPORTE TECNOLÓGICO - DEPSOTEC".center(78) + "║")
    print("║" + " "*78 + "║")
    print("╚" + "═"*78 + "╝")
    print("\n" + "⚠️  ACCESO RESTRINGIDO - SOLO PERSONAL AUTORIZADO".center(80))
    print("─"*80 + "\n")

def autenticar_usuario():
    """Sistema de autenticación de usuarios"""
    global usuario_actual, intentos_fallidos
    
    mostrar_banner_login()
    
    while intentos_fallidos < MAX_INTENTOS:
        print(f"\n[INICIO DE SESIÓN] - Intento {intentos_fallidos + 1}/{MAX_INTENTOS}")
        print("-" * 50)
        
        usuario = input("👤 Usuario: ").strip()
        
        if not usuario:
            print("⚠️  El nombre de usuario no puede estar vacío.")
            continue
        
        # Usar getpass para ocultar la contraseña
        password = getpass.getpass("🔑 Contraseña: ")
        
        # Validar credenciales
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        if usuario in USUARIOS_AUTORIZADOS and USUARIOS_AUTORIZADOS[usuario] == password_hash:
            usuario_actual = usuario
            print("\n✓ Autenticación exitosa")
            print(f"✓ Bienvenido/a: {usuario.upper()}")
            logger.info(f"Inicio de sesión exitoso - Usuario: {usuario}")
            time.sleep(1)
            return True
        else:
            intentos_fallidos += 1
            print(f"\n❌ Credenciales incorrectas")
            logger.warning(f"Intento de inicio de sesión fallido - Usuario: {usuario}")
            
            if intentos_fallidos < MAX_INTENTOS:
                print(f"⚠️  Le quedan {MAX_INTENTOS - intentos_fallidos} intentos")
                time.sleep(1)
    
    print("\n🚫 Número máximo de intentos alcanzado")
    print("   El sistema se cerrará por seguridad")
    logger.error(f"Bloqueo por múltiples intentos fallidos")
    time.sleep(2)
    return False

def inicializar_pool():
    """Inicializa el pool de conexiones a la base de datos"""
    global connection_pool
    try:
        connection_pool = psycopg2.pool.SimpleConnectionPool(
            1, 10,
            **DB_CONFIG
        )
        logger.info("Pool de conexiones inicializado correctamente")
        return True
    except psycopg2.Error as e:
        logger.error(f"Error al crear pool de conexiones: {e}")
        return False

@contextmanager
def obtener_conexion():
    """Context manager para manejar conexiones del pool de forma segura"""
    conn = None
    try:
        conn = connection_pool.getconn()
        yield conn
    except psycopg2.Error as e:
        logger.error(f"Error en la conexión a la base de datos: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            connection_pool.putconn(conn)

def validar_numero_telefono(numero):
    """Valida que el número telefónico tenga formato correcto"""
    numero_limpio = ''.join(c for c in numero if c.isdigit() or c == '+')
    
    if len(numero_limpio) < 8 or len(numero_limpio) > 15:
        return None, "El número debe tener entre 8 y 15 dígitos"
    
    return numero_limpio, None

def formatear_valor(valor):
    """Formatea valores para mostrar en tabla"""
    if isinstance(valor, datetime):
        return valor.strftime('%Y-%m-%d %H:%M:%S')
    elif valor is None:
        return 'N/A'
    elif isinstance(valor, (int, float)):
        return str(valor)
    return str(valor)[:30]

def calcular_estadisticas(resultados, columnas, titular, destino_cod):
    """Calcula estadísticas de las llamadas"""
    if not resultados:
        return None
    
    idx_titular = columnas.index('titular')
    idx_duracion = columnas.index('duracion_seg')
    idx_tipo = columnas.index('tipo')
    
    stats = {
        'total': len(resultados),
        'a_destino': sum(1 for r in resultados if r[idx_titular] == titular),
        'desde_destino': sum(1 for r in resultados if r[idx_titular] != titular),
        'duracion_total': sum(int(r[idx_duracion]) for r in resultados if r[idx_duracion]),
        'voz': sum(1 for r in resultados if r[idx_tipo] and 'voz' in str(r[idx_tipo]).lower()),
        'sms': sum(1 for r in resultados if r[idx_tipo] and 'sms' in str(r[idx_tipo]).lower())
    }
    
    stats['duracion_promedio'] = stats['duracion_total'] // stats['total'] if stats['total'] > 0 else 0
    
    return stats

def mostrar_resultados(resultados, columnas, titular, destino_cod):
    """Muestra los resultados de la consulta de forma optimizada y segura"""
    ancho_total = sum(ANCHOS_COLUMNA.values())
    
    print("\n" + "="*ancho_total)
    print("DIVIAC --- REPORTE DE VINCULACIONES TELEFÓNICAS --- DEPSOTEC".center(ancho_total))
    print("="*ancho_total)
    print(f"TITULAR: {titular}")
    print(f"DESTINO: {destino_cod}")
    print(f"FECHA CONSULTA: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"CONSULTA REALIZADA POR: {usuario_actual.upper()}")
    print("="*ancho_total)
    
    if not resultados:
        print("\n⚠️  No se encontraron llamadas entre estos números.\n")
        logger.info(f"Sin resultados - Usuario: {usuario_actual} | {titular} -> {destino_cod}")
        return
    
    # Calcular y mostrar estadísticas
    stats = calcular_estadisticas(resultados, columnas, titular, destino_cod)
    
    print(f"\n📊 ESTADÍSTICAS:")
    print(f"├─ Total de comunicaciones: {stats['total']}")
    print(f"├─ Llamadas de {titular} → {destino_cod}: {stats['a_destino']}")
    print(f"├─ Llamadas de {destino_cod} → {titular}: {stats['desde_destino']}")
    print(f"├─ Duración total: {stats['duracion_total']} segundos ({stats['duracion_total']//60} minutos)")
    print(f"├─ Duración promedio: {stats['duracion_promedio']} segundos")
    print(f"├─ Llamadas de voz: {stats['voz']}")
    print(f"└─ Mensajes SMS: {stats['sms']}")
    
    print("\n" + "-"*ancho_total)
    
    # Encabezados
    print(f"{'#':<{ANCHOS_COLUMNA['#']}}", end="")
    for campo in CAMPOS_MOSTRAR:
        print(f"{campo.upper():<{ANCHOS_COLUMNA[campo]}}", end="")
    print("\n" + "-"*ancho_total)
    
    # Datos
    indices = [columnas.index(campo) for campo in CAMPOS_MOSTRAR]
    
    for num, fila in enumerate(resultados, 1):
        print(f"{num:<{ANCHOS_COLUMNA['#']}}", end="")
        for i, idx in enumerate(indices):
            campo = CAMPOS_MOSTRAR[i]
            valor = formatear_valor(fila[idx])
            print(f"{valor:<{ANCHOS_COLUMNA[campo]}}", end="")
        print()
    
    print("-"*ancho_total + "\n")
    logger.info(f"Consulta exitosa - Usuario: {usuario_actual} | Registros: {stats['total']} | {titular} -> {destino_cod}")

def consultar_vinculaciones(titular, destino_cod):
    """Consulta las llamadas entre dos números usando prepared statements"""
    try:
        with obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                query = """
                    SELECT titular, imei, destino_cod, fecha_txt, hora_txt, 
                        duracion_seg, tipo, entrante_saliente
                    FROM llamadas
                    WHERE (titular = %s AND destino_cod = %s)
                    OR (titular = %s AND destino_cod = %s)
                    ORDER BY fecha_txt DESC, hora_txt DESC
                """
                
                cursor.execute(query, (titular, destino_cod, destino_cod, titular))
                resultados = cursor.fetchall()
                
                mostrar_resultados(resultados, CAMPOS_MOSTRAR, titular, destino_cod)
                
    except psycopg2.Error as e:
        logger.error(f"Error DB - Usuario: {usuario_actual} | {e}")
        print(f"\n❌ Error al consultar la base de datos.")
        print(f"   Detalles técnicos registrados en el log.")
    except Exception as e:
        logger.error(f"Error inesperado - Usuario: {usuario_actual} | {e}")
        print(f"\n❌ Error inesperado al procesar la consulta.")

def solicitar_numero(mensaje):
    """Solicita y valida un número telefónico"""
    while True:
        numero = input(mensaje).strip()
        
        if not numero:
            print("⚠️  El número no puede estar vacío.")
            continue
        
        numero_limpio, error = validar_numero_telefono(numero)
        
        if error:
            print(f"⚠️  {error}")
            continue
        
        confirmar = input(f"   Confirmar número '{numero_limpio}'? (S/N): ").strip().upper()
        if confirmar == 'S':
            return numero_limpio
        else:
            print("   Reingrese el número.")

def mostrar_menu_principal():
    """Muestra el menú principal"""
    print("\n" + "="*120)
    print(f"SISTEMA DE VINCULACIONES TELEFÓNICAS - Usuario: {usuario_actual.upper()}".center(120))
    print("="*120)
    print("\n[OPCIONES]")
    print("1. Consultar vinculaciones")
    print("2. Ver información del sistema")
    print("3. Cerrar sesión")
    print("-" * 50)

def verificar_conexion_db():
    """Verifica que la conexión a la base de datos esté disponible"""
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                return True
    except Exception as e:
        logger.error(f"Error de conexión: {e}")
        return False

def main():
    """Función principal del programa con sistema de autenticación"""
    
    # Sistema de autenticación
    if not autenticar_usuario():
        return
    
    # Limpiar pantalla después del login
    os.system('clear' if os.name == 'posix' else 'cls')
    
    # Inicializar pool de conexiones
    print("\n🔄 Inicializando sistema...")
    if not inicializar_pool():
        print("\n❌ No se pudo conectar a la base de datos.")
        print("   Verifique la configuración.")
        return
    
    # Verificar conexión
    if not verificar_conexion_db():
        print("\n❌ No se pudo establecer conexión con la base de datos.")
        return
    
    print("✓ Conexión a base de datos establecida")
    print("✓ Sistema listo para operar\n")
    logger.info(f"Sistema inicializado - Usuario: {usuario_actual}")
    time.sleep(1)
    
    while True:
        try:
            mostrar_menu_principal()
            opcion = input("Seleccione una opción: ").strip()
            
            if opcion == '1':
                print("\n[INGRESO DE DATOS]")
                print("-" * 50)
                
                linea_titular = solicitar_numero("Ingrese número TITULAR (origen): ")
                numero_destino = solicitar_numero("Ingrese número DESTINO: ")
                
                print("\n🔍 Buscando vinculaciones...")
                consultar_vinculaciones(linea_titular, numero_destino)
                
                input("\n[Presione ENTER para continuar]")
                
            elif opcion == '2':
                print("\n[INFORMACIÓN DEL SISTEMA]")
                print(f"Usuario activo: {usuario_actual}")
                print(f"Host BD: {DB_CONFIG['host']}")
                print(f"Base de datos: {DB_CONFIG['database']}")
                print(f"Usuario BD: {DB_CONFIG['user']}")
                print(f"Puerto: {DB_CONFIG['port']}")
                print(f"Fecha/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                input("\n[Presione ENTER para continuar]")
                
            elif opcion == '3':
                print("\n✓ Cerrando sesión...")
                logger.info(f"Cierre de sesión - Usuario: {usuario_actual}")
                break
                
            else:
                print("\n⚠️  Opción inválida. Intente nuevamente.")
                
        except KeyboardInterrupt:
            print("\n\n⚠️  Operación cancelada por el usuario.")
            continuar = input("¿Desea cerrar sesión? (S/N): ").strip().upper()
            if continuar == 'S':
                break
    
    # Cerrar pool de conexiones
    if connection_pool:
        connection_pool.closeall()
        logger.info("Pool de conexiones cerrado")
    
    print("\n✓ Sesión finalizada. ¡Hasta pronto!\n")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Error crítico en el sistema: {e}")
        print(f"\n❌ Error crítico del sistema. Consulte el log para más detalles.\n")