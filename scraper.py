"""
Facebook Marketplace iPhone Scraper — Bogotá y ciudades aledañas
Extracción robusta con múltiples estrategias para el DOM de Facebook.
"""

import asyncio
import json
import logging
import random
import re
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

import sys

sys.stdout.reconfigure(encoding='utf-8')

from database import Database
from notifier import TelegramNotifier
from config import CIUDADES, PRECIOS_REFERENCIA, TELEGRAM_TOKEN, CHAT_ID, UMBRAL_DESCUENTO

# ─── FILTROS ────────────────────────────────────────────────────────────────

PALABRAS_DESCARTE = [
    "icloud",
    "bloqueado",
    "repuesto",
    "para partes",
    "display",
    "pantalla",
    "cuota",
    "inicial",
    "solo caja",
    "cambio",
    "permuto",
    "sin face id",
    "sin true tone",
    "detalle",
    "estrellado",
    "dañado",
]

ALMACENAMIENTOS_VALIDOS = [
    "64gb",
    "128gb",
    "256gb",
    "512gb",
    "1tb",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(
            "scraper.log",
            encoding="utf-8"
        ),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)


# ─── UTILIDADES ──────────────────────────────────────────────────────────────

async def human_delay(min_s=1.5, max_s=4.0):
    await asyncio.sleep(random.uniform(min_s, max_s))

async def scroll_suave(page, pasos=5):
    for _ in range(pasos):
        await page.mouse.wheel(0, random.randint(300, 700))
        await asyncio.sleep(random.uniform(0.5, 1.2))

def detectar_almacenamiento(titulo: str) -> str | None:

    t = titulo.lower().replace(" ", "")

    for gb in ALMACENAMIENTOS_VALIDOS:
        if gb in t:
            return gb

    return None

def calcular_score_confianza(
    titulo: str,
    precio: int,
    estrategia: str,
    img_url: str
) -> int:

    score = 0

    titulo_l = titulo.lower()

    # Modelo detectado
    if "iphone" in titulo_l:
        score += 30

    # Precio válido
    if 200_000 <= precio <= 20_000_000:
        score += 25

    # Tiene imagen
    if img_url:
        score += 10

    # Estrategia robusta
    if estrategia == "A":
        score += 25
    elif estrategia == "B":
        score += 15
    elif estrategia == "C":
        score += 5

    # Tiene almacenamiento
    if detectar_almacenamiento(titulo_l):
        score += 10

    # Penalización
    if any(p in titulo_l for p in PALABRAS_DESCARTE):
        score -= 50

    return score

# ─── PARSING ─────────────────────────────────────────────────────────────────

def extraer_modelo_iphone(titulo: str) -> str | None:
    """
    Detecta el modelo de iPhone en títulos variados incluyendo series 16 y 17.
    ip 13, i phone 13, apple 14, iphone trece, ip14 pro max, iphone 17 air, etc.
    """
    t = titulo.lower()
    t = re.sub(r'\bi\s*p(?:hone)?\b', 'iphone', t)
    t = re.sub(r'\bapple\b', 'iphone', t)
    t = re.sub(r'[-_]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    palabras = {
        'once': '11', 'doce': '12', 'trece': '13', 'catorce': '14',
        'quince': '15', 'diez': '10', 'nueve': '9', 'ocho': '8',
    }
    for palabra, num in palabras.items():
        t = t.replace(palabra, num)
    if 'iphone' not in t:
        return None
    if any(p in t for p in PALABRAS_DESCARTE):
        return None

    # iPhone Air (ej: iphone 17 air)
    match = re.search(r'iphone\s*(\d{2})\s*air', t)
    if match:
        numero = match.group(1)
        if 10 <= int(numero) <= 20:
            return f"iphone {numero} air"

    # Patrón principal: iphone + número + sufijo (pro max, pro, plus, mini, e)
    patron = r'iphone\s*(\d{2})\s*(pro\s*max|pro|plus|mini|e)?'
    match = re.search(patron, t)
    if match:
        numero = match.group(1)
        sufijo = (match.group(2) or '').strip()
        # Normalizar "e" sin espacio: "iphone 16 e" → "iphone 16e"
        if sufijo == 'e':
            sufijo = 'e'
            if 10 <= int(numero) <= 20:
                return f"iphone {numero}e"
        if 10 <= int(numero) <= 20:
            modelo = f"iphone {numero}" + (f" {sufijo}" if sufijo else "")

            storage = detectar_almacenamiento(t)

            if storage:
                modelo += f" {storage}"

            return modelo

    # X, XS, XR
    match = re.search(r'iphone\s*(xs\s*max|xs|xr|x\b)', t)
    if match:
        modelo = f"iphone {match.group(1).strip()}"

        storage = detectar_almacenamiento(t)

        if storage:
            modelo += f" {storage}"

        return modelo

    # SE
    match = re.search(r'iphone\s*se\s*([23])?', t)
    if match:
        gen = match.group(1)
        modelo = f"iphone se {gen}" if gen else "iphone se"

        storage = detectar_almacenamiento(t)

        if storage:
            modelo += f" {storage}"

        return modelo   

    return None
def parsear_precio(texto: str) -> int | None:
    if not texto:
        return None
    limpio = (texto
              .replace("\xa0", "").replace("\u202f", "")
              .replace(".", "").replace(",", "")
              .replace(" ", "").replace("$", "").replace("COP", "").strip())
    match = re.search(r"\d{4,}", limpio)
    if match:
        val = int(match.group())
        if val < 200_000:
            return None
        if val > 100_000_000:
            return None
        return val
    return None


def precio_es_ganga(modelo: str, precio: int, db: Database) -> tuple:
    fuente = "config"
    precio_ref = None
    mercado = db.obtener_precio_mercado(modelo)
    if mercado and mercado["muestras"] >= 5:
        precio_ref = mercado["promedio"]
        fuente = f"mercado ({mercado['muestras']} muestras)"
    else:
        for key in sorted(PRECIOS_REFERENCIA.keys(), key=len, reverse=True):
            if key in modelo or modelo in key:
                precio_ref = PRECIOS_REFERENCIA[key]
                break
        if precio_ref is None:
            precio_ref = PRECIOS_REFERENCIA.get("iphone", 1_500_000)
    if not precio_ref:
        return False, 0, 0, fuente
    descuento = (precio_ref - precio) / precio_ref
    es_ganga = precio <= precio_ref * UMBRAL_DESCUENTO
    return es_ganga, precio_ref, round(descuento * 100, 1), fuente


# ─── JAVASCRIPT ROBUSTO: 3 ESTRATEGIAS DE EXTRACCIÓN ─────────────────────────

JS_EXTRAER_ITEMS = """
() => {
    const results = [];
    const vistos = new Set();

    // ── Estrategia A: links a /marketplace/item/ con detección de contenedor ──
    const links = document.querySelectorAll('a[href*="/marketplace/item/"]');
    links.forEach(link => {
        try {
            const itemId = link.href.match(/item\\/([0-9]+)/)?.[1];
            if (!itemId || vistos.has(itemId)) return;
            vistos.add(itemId);

            // Subir en el DOM buscando contenedor con precio
            let container = link;
            for (let i = 0; i < 8; i++) {
                if (!container.parentElement) break;
                container = container.parentElement;
                const text = container.innerText || '';
                if (text.match(/[\\d.]{5,}|\\$\\s*[\\d]/)) break;
            }

            // Extraer textos directos de nodos hoja (más precisos)
            const textos = [];
            const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
            let node;
            while ((node = walker.nextNode())) {
                const t = node.textContent.trim();
                if (t.length > 1) textos.push(t);
            }

            // También tomar spans y divs con un solo texto directo
            Array.from(container.querySelectorAll('span, div')).forEach(el => {
                if (el.childNodes.length === 1 && el.childNodes[0].nodeType === 3) {
                    const t = el.textContent.trim();
                    if (t.length > 1 && !textos.includes(t)) textos.push(t);
                }
            });

            const precioTexto = textos.find(t =>
                t.match(/\\$[\\s\\d.,]+/) ||
                t.match(/^[\\d.,]{4,}$/) ||
                t.match(/\\d+[.,]\\d{3}/) ||
                t.match(/COP/)
            ) || '';

            const titulo = textos
                .filter(t => t.length > 5 && !t.match(/^\\$/) && !t.match(/^[\\d.,\\s]+$/) && !t.match(/COP/))
                .sort((a, b) => b.length - a.length)[0] || '';

            const img = container.querySelector('img[src*="http"]');
            results.push({ id: itemId, titulo, precioTexto, imgUrl: img?.src || '', estrategia: 'A' });
        } catch(e) {}
    });

    // ── Estrategia B: JSON-LD estructurado ────────────────────────────────────
    try {
        document.querySelectorAll('script[type="application/ld+json"]').forEach(s => {
            try {
                const data = JSON.parse(s.textContent);
                const items = Array.isArray(data) ? data : [data];
                items.forEach(item => {
                    if (item['@type'] === 'Product' && item.name) {
                        const urlMatch = (item.url || '').match(/item\\/([0-9]+)/);
                        if (urlMatch && !vistos.has(urlMatch[1])) {
                            vistos.add(urlMatch[1]);
                            results.push({
                                id: urlMatch[1],
                                titulo: item.name,
                                precioTexto: String(item.offers?.price || ''),
                                imgUrl: item.image || '',
                                estrategia: 'B'
                            });
                        }
                    }
                });
            } catch(e) {}
        });
    } catch(e) {}

    // ── Estrategia C: innerText completo de la página ────────────────────────
    // Solo si las anteriores devolvieron muy poco
    if (results.filter(r => r.titulo && r.precioTexto).length < 3) {
        try {
            const lineas = document.body.innerText.split('\\n').map(l => l.trim()).filter(l => l.length > 2);
            for (let i = 0; i < lineas.length; i++) {
                const linea = lineas[i];
                if (linea.match(/iphone|ip\\s*1[0-9]|apple.*1[0-9]/i)) {
                    const ventana = lineas.slice(Math.max(0, i-2), i+5).join(' ');
                    const precioMatch = ventana.match(/\\$[\\s\\d.,]+|\\d{1,2}[.,]\\d{3}[.,]\\d{3}/);
                    if (precioMatch) {
                        const fakeId = 'text_' + i + '_' + linea.slice(0,10).replace(/\\W/g,'');
                        if (!vistos.has(fakeId)) {
                            vistos.add(fakeId);
                            results.push({ id: fakeId, titulo: linea, precioTexto: precioMatch[0], imgUrl: '', estrategia: 'C' });
                        }
                    }
                }
            }
        } catch(e) {}
    }

    return results;
}
"""


# ─── SCRAPING POR CIUDAD ──────────────────────────────────────────────────────

async def scrape_ciudad(page, ciudad: dict, db: Database, notifier: TelegramNotifier):
    url = (
        f"https://www.facebook.com/marketplace/{ciudad['id']}/search"
        f"?query=iphone&sortBy=creation_time_descend&exact=false"
    )
    log.info(f"🔍 {ciudad['nombre']}...")

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=35_000)
        await human_delay(3, 5)

# Scroll progresivo para cargar más anuncios
        for ronda in range(10):
            await scroll_suave(page, pasos=6)
            await human_delay(2, 3)  # esperar que Facebook cargue más items
            log.info(f"   Scroll ronda {ronda+1}/10...")
    except PlaywrightTimeout:
        log.warning(f"   ⚠️  Timeout en {ciudad['nombre']}, saltando...")
        return

    try:
        await page.wait_for_selector('a[href*="/marketplace/item/"]', timeout=12_000)
    except PlaywrightTimeout:
        log.warning(f"   ⚠️  Sin listings en {ciudad['nombre']}")
        try:
            await page.screenshot(path=f"debug_{ciudad['nombre']}.png")
        except Exception:
            pass
        return

    items = await page.evaluate(JS_EXTRAER_ITEMS)
    por_estrategia = {s: sum(1 for i in items if i.get('estrategia') == s) for s in ['A','B','C']}
    log.info(f"   Encontrados {len(items)} anuncios (A:{por_estrategia['A']} B:{por_estrategia['B']} C:{por_estrategia['C']})")

    if items:
        m = items[0]
        log.info(f"   Muestra → titulo={m['titulo']!r:.50} | precio={m['precioTexto']!r}")

    precios_registrados = 0
    gangas = 0
    sin_precio = 0
    sin_modelo = 0

    for item in items:
        titulo = (item.get("titulo") or "").strip()
        precio_txt = (item.get("precioTexto") or "").strip()

        precio_num = parsear_precio(precio_txt)
        if precio_num is None:
            sin_precio += 1
            continue
        if precio_num < 200_000 or precio_num > 20_000_000:
            continue

        modelo = extraer_modelo_iphone(titulo)
        score = calcular_score_confianza(
            titulo=titulo,
            precio=precio_num,
            estrategia=item.get("estrategia", "C"),
            img_url=item.get("imgUrl", "")
        )

        if score < 60:
            continue
        if not modelo:
            sin_modelo += 1
            continue

        item_id = item["id"]

        # Estrategia C no tiene item_id real, solo loguear
        if item_id.startswith("text_"):
            log.info(f"   ℹ️  [C] {titulo!r} — ${precio_num:,} (sin link directo)")
            continue

        db.registrar_precio(modelo, precio_num, ciudad["nombre"], item_id)
        precios_registrados += 1

        if db.ya_notificado(item_id):
            continue

        es_ganga, precio_ref, descuento_pct, fuente = precio_es_ganga(modelo, precio_num, db)
        if not es_ganga:
            continue

        link = f"https://www.facebook.com/marketplace/item/{item_id}/"
        await notifier.enviar_alerta(
            titulo=titulo,
            precio=precio_num,
            precio_ref=precio_ref,
            descuento_pct=descuento_pct,
            ciudad=ciudad["nombre"],
            link=link,
            img_url=item.get("imgUrl", ""),
            fuente_precio=fuente,
        )
        db.guardar_item(item_id, titulo, precio_num, ciudad["nombre"], link)
        gangas += 1
        log.info(f"   ✅ GANGA: {titulo} — ${precio_num:,} ({descuento_pct}% off) [{fuente}]")
        await human_delay(1, 2)

    log.info(
        f"   📦 {precios_registrados} precios aprendidos | "
        f"🔥 {gangas} gangas | "
        f"⚠️  {sin_precio} sin precio | {sin_modelo} sin modelo"
    )


# ─── SESIÓN ───────────────────────────────────────────────────────────────────

async def cargar_sesion(context, session_file="session.json"):
    try:
        with open(session_file, "r") as f:
            cookies = json.load(f)
        await context.add_cookies(cookies)
        log.info("✅ Sesión de Facebook cargada")
        return True
    except FileNotFoundError:
        log.error("❌ No se encontró session.json — corre: python login.py")
        return False


# ─── MAIN ─────────────────────────────────────────────────────────────────────

async def main():
    db = Database()
    notifier = TelegramNotifier(TELEGRAM_TOKEN, CHAT_ID)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="es-CO",
        )

        if not await cargar_sesion(context):
            await browser.close()
            db.close()
            return

        page = await context.new_page()
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3] });
        """)

        inicio = datetime.now()
        log.info(f"🚀 Iniciando ciclo — {inicio.strftime('%H:%M:%S')}")

        for ciudad in CIUDADES:
            try:
                await scrape_ciudad(page, ciudad, db, notifier)
                await human_delay(4, 8)
            except Exception as e:
                log.error(f"Error en {ciudad['nombre']}: {e}", exc_info=True)

        promedios = db.obtener_todos_promedios()
        if promedios:
            log.info("📊 Precios de mercado aprendidos:")
            for p in promedios:
                log.info(f"   {p['modelo']:30} ${p['promedio']:>12,.0f}  ({p['muestras']} muestras)")
        else:
            log.info("📊 Aún no hay suficientes muestras para promedios (mínimo 5 por modelo)")

        stats = db.estadisticas()
        duracion = (datetime.now() - inicio).seconds
        log.info(
            f"✅ Ciclo completado en {duracion}s | "
            f"Alertas hoy: {stats['alertas_hoy']} | "
            f"Histórico: {stats['total_alertas']} | "
            f"Muestras precio: {stats['muestras_precio']}"
        )

        await browser.close()
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
