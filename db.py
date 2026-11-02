import mysql.connector
from mysql.connector import Error
from config import DB_CONFIG

ER_CHECK_CONSTRAINT_VIOLATED = 3819


def procesar_transaccion_venta(conexion, empleado, subtotal, iva, total, renglones_grid):
    cursor = conexion.cursor()
    try:
        # 1. Iniciar transaccion explicita
        conexion.start_transaction()

        # 2. Insertar la venta en VENTAS
        sql_venta = """
            INSERT INTO ventas (empleado, subtotal, iva, total)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(sql_venta, (empleado, subtotal, iva, total))
        folio_generado = cursor.lastrowid

        # 3. Actualizar stock en PRODUCTOS e insertar en DETALLES_VENTA
        for clave, descripcion, precio, cantidad, importe in renglones_grid:
            sql_stock = "UPDATE productos SET stock = stock - %s WHERE clave = %s"
            cursor.execute(sql_stock, (cantidad, clave))

            sql_detalle = """
                INSERT INTO detalles_venta (folio_venta, clave_producto, cantidad, precio, importe)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(sql_detalle, (folio_generado, clave, cantidad, precio, importe))

        # 4. Guardar datos del QR en la venta
        datos_qr = f"FOLIO:{folio_generado}|EMPLEADO:{empleado}|TOTAL:${total:.2f}"
        cursor.execute("UPDATE ventas SET cadena_qr = %s WHERE folio = %s",
                       (datos_qr, folio_generado))

        # 5. Confirmar transaccion (COMMIT)
        conexion.commit()

        # 6. Consultar total acumulado y promedio de ticket
        cursor.execute("""
            SELECT COUNT(folio), COALESCE(SUM(total), 0),
                   COALESCE(ROUND(AVG(total), 2), 0)
            FROM ventas
        """)
        num_compras, total_acumulado, promedio_ticket = cursor.fetchone()
        return True, folio_generado, datos_qr, num_compras, total_acumulado, promedio_ticket

    except Exception as error_sql:
        # Si algo falla se deshacen los cambios en las 3 tablas
        conexion.rollback()
        return False, None, str(error_sql), 0, 0.0, 0.0
    finally:
        cursor.close()


class BaseDatosPOS:
    def __init__(self):
        self.conexion = None

    def conectar(self):
        self.cerrar()
        self.conexion = mysql.connector.connect(**DB_CONFIG)
        self.conexion.autocommit = True

    def esta_conectado(self):
        try:
            return self.conexion is not None and self.conexion.is_connected()
        except Error:
            return False

    def cerrar(self):
        if self.conexion is not None:
            try:
                self.conexion.close()
            except Error:
                pass
            self.conexion = None

    # Busca un producto por su codigo de barras
    def buscar_producto(self, clave):
        cur = self.conexion.cursor(dictionary=True)
        try:
            cur.execute(
                "SELECT clave, descripcion, precio, stock FROM productos WHERE clave = %s",
                (clave,),
            )
            return cur.fetchone()
        finally:
            cur.close()

    # Obtiene el total de ventas, promedio y numero de tickets
    def obtener_kpis(self):
        cur = self.conexion.cursor()
        try:
            cur.execute("SELECT COALESCE(SUM(total), 0), COALESCE(ROUND(AVG(total), 2), 0), "
                        "COUNT(*) FROM ventas")
            return cur.fetchone()
        finally:
            cur.close()

    # Calcula el siguiente folio a mostrar en pantalla
    def siguiente_folio(self):
        cur = self.conexion.cursor()
        try:
            cur.execute("SELECT COALESCE(MAX(folio), 0) + 1 FROM ventas")
            return int(cur.fetchone()[0])
        finally:
            cur.close()

    def registrar_venta(self, empleado, renglones_grid, subtotal, iva, total):
        return procesar_transaccion_venta(self.conexion, empleado, subtotal, iva,
                                          total, renglones_grid)
