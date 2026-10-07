"""
Plantilla de configuración.
Copia este archivo como config.py y completa tus datos.
config.py NO se sube a GitHub (está en .gitignore).
"""

# ─── TELEGRAM ────────────────────────────────────────────────────────────────
# Crea un bot con @BotFather en Telegram y pega aquí su token y tu chat id.
TELEGRAM_TOKEN = "TU_TOKEN_AQUI"
CHAT_ID        = "TU_CHAT_ID_AQUI"

# ─── ZONAS ───────────────────────────────────────────────────────────────────
# id: identificador de Facebook Marketplace para esa zona.
# Entra a facebook.com/marketplace, elige la zona y copia el id de la URL.
CIUDADES = [
    {"nombre": "Zona 1", "id": "id_zona_1"},
    {"nombre": "Zona 2", "id": "id_zona_2"},
]

# ─── PRECIOS DE REFERENCIA (COP) ─────────────────────────────────────────────
# Precio promedio aproximado por modelo. Se usa mientras la base de datos
# todavía no tiene suficientes muestras. Ajusta los valores al mercado.
PRECIOS_REFERENCIA = {
    "iphone 14 pro": 1_800_000,
    "iphone 14":     1_400_000,
    "iphone 13":     1_200_000,
    "iphone":          200_000,   # valor de respaldo
}

# ─── UMBRAL DE DESCUENTO ─────────────────────────────────────────────────────
# 1.0  = alerta si está por debajo del promedio del mercado (más alertas)
# 0.90 = alerta si está 10 % o más barato
# 0.80 = alerta si está 20 % o más barato (más estricto)
UMBRAL_DESCUENTO = 0.90
