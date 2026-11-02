from decimal import Decimal, ROUND_HALF_UP
import config

TASA_IVA = Decimal(config.TASA_IVA)
CENTAVOS = Decimal("0.01")


# Redondeo a 2 decimales
def redondear(valor):
    return Decimal(valor).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


# Importe por renglon (precio * cantidad)
def calcular_importe(precio, cantidad):
    return redondear(Decimal(precio) * int(cantidad))


# Calcula subtotal, iva (16%) y total del ticket
def calcular_totales(importes):
    total = redondear(sum((Decimal(i) for i in importes), Decimal("0")))
    iva = redondear(total * TASA_IVA)
    subtotal = redondear(total - iva)
    return subtotal, iva, total


# Formato de moneda ($0.00)
def moneda(valor):
    return f"${redondear(valor):,.2f}"
