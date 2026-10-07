# Bot de precios de iPhones usados

Proyecto personal **en desarrollo** para practicar extracción, almacenamiento y análisis de datos con Python.

El bot busca anuncios de iPhones usados en Facebook Marketplace, guarda los precios en una base de datos, calcula el precio promedio de cada modelo y avisa por Telegram cuando encuentra uno por debajo del mercado.

## Cómo funciona

1. **Recolección:** un scraper hecho con Playwright recorre los anuncios y extrae título, precio, enlace e imagen.
2. **Limpieza:** con expresiones regulares saca el modelo y el almacenamiento de cada título, y descarta anuncios dañados, bloqueados o con datos incompletos.
3. **Almacenamiento:** cada precio visto se guarda en SQLite.
4. **Análisis:** para cada modelo calcula un promedio recortado de los últimos 60 días (sin el 10 % más alto y el 10 % más bajo, para reducir el efecto de valores extremos). Mientras hay pocas muestras, usa precios de referencia definidos en la configuración.
5. **Alerta:** si un anuncio está por debajo del precio de mercado según el umbral configurado, el bot envía el enlace por Telegram con el precio, el descuento y la foto. Los anuncios ya avisados no se repiten.

## Tecnologías

Python · Playwright · aiohttp · SQLite · Telegram Bot API · Expresiones regulares

## Estructura

```
├── scraper.py          # Recolección, filtrado y lógica principal
├── scheduler.py        # Repite el proceso en ciclos
├── database.py         # Base de datos SQLite y cálculo de promedios
├── notifier.py         # Envío de alertas por Telegram
├── login.py            # Guarda la sesión del navegador (una sola vez)
├── debug.py            # Muestra qué extrae el scraper, para depurar
├── requirements.txt
└── config.example.py   # Plantilla de configuración
```

## Instalación

```bash
pip install -r requirements.txt
playwright install chromium
```

## Configuración

1. Crea un bot de Telegram con **@BotFather** y copia el token.
2. Copia la plantilla y completa tus datos:
   ```bash
   cp config.example.py config.py
   ```
3. Edita `config.py`: token, chat id, zonas, precios de referencia y umbral de descuento.
4. Inicia sesión una vez (se crea `session.json`):
   ```bash
   python login.py
   ```

## Uso

```bash
# Una sola pasada (para probar)
python scraper.py

# En ciclos
python scheduler.py
```

## Próximos pasos

- Limpieza y análisis de la variación de precios por modelo
- Dashboard para visualizar la evolución de los precios

## Aviso

Es un proyecto educativo. Los archivos `config.py` (token de Telegram) y `session.json` (sesión del navegador) **no se suben al repositorio** porque contienen datos privados. Si lo usas, revisa los términos de uso de la plataforma que consultes.
