"""
debug.py — Abre el navegador y muestra exactamente qué ve el scraper.
Corre esto si el scraper encuentra 0 precios aprendidos.

Uso: python debug.py
"""

import asyncio
import json
import sys
from playwright.async_api import async_playwright

# Importar el mismo JS del scraper para probar idéntica lógica
from scraper import JS_EXTRAER_ITEMS, extraer_modelo_iphone, parsear_precio

CIUDAD_ID = "bogota"   # Cambia esto para depurar otra ciudad
HEADLESS   = False     # True para correr sin ventana (en servidor)


async def debug():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=HEADLESS,
            args=["--start-maximized"]
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

        try:
            with open("session.json") as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
            print("✅ Sesión cargada")
        except FileNotFoundError:
            print("❌ session.json no encontrado — corre: python login.py")
            await browser.close()
            return

        page = await context.new_page()
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)

        url = f"https://www.facebook.com/marketplace/{CIUDAD_ID}/search?query=iphone&sortBy=creation_time_descend"
        print(f"\n🌐 Cargando: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=35_000)
        await asyncio.sleep(4)

        # Scroll para cargar más items
        for _ in range(5):
            await page.mouse.wheel(0, 500)
            await asyncio.sleep(0.8)
        await asyncio.sleep(2)

        print("\n🔎 Ejecutando extracción JS...")
        items = await page.evaluate(JS_EXTRAER_ITEMS)

        print(f"\n{'='*60}")
        print(f"  TOTAL ENCONTRADOS: {len(items)}")
        print(f"{'='*60}")

        validos = 0
        for i, item in enumerate(items[:20]):   # mostrar primeros 20
            titulo    = (item.get('titulo') or '').strip()
            precio_txt = (item.get('precioTexto') or '').strip()
            estrategia = item.get('estrategia', '?')
            item_id   = item.get('id', '')

            precio_num = parsear_precio(precio_txt)
            modelo     = extraer_modelo_iphone(titulo) if titulo else None

            estado = "✅" if (titulo and precio_num and modelo) else "⚠️ "
            if titulo and precio_num and modelo:
                validos += 1

            print(f"\n{estado} Item {i+1} [{estrategia}] — ID: {item_id}")
            print(f"   Título:  {titulo!r:.80}")
            print(f"   Precio:  {precio_txt!r} → {precio_num:,}" if precio_num else f"   Precio:  {precio_txt!r} → ❌ no parseable")
            print(f"   Modelo:  {modelo or '❌ no detectado'}")

        print(f"\n{'='*60}")
        print(f"  VÁLIDOS (título + precio + modelo): {validos}/{len(items)}")

        if validos == 0:
            print("\n⚠️  DIAGNÓSTICO:")
            print("  El scraper no puede extraer datos del DOM.")
            print("  Posibles causas:")
            print("  1. Sesión expirada → corre: python login.py")
            print("  2. Facebook cambió su HTML → revisar selectores en JS_EXTRAER_ITEMS")
            print("  3. Bloqueo temporal por bot detection → esperar 24h")
            print("\n  Guardando screenshot para inspección visual...")
            await page.screenshot(path="debug_screenshot.png", full_page=True)
            print("  📸 debug_screenshot.png guardado")

            # También volcar el HTML para inspección manual
            html = await page.content()
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("  📄 debug_page.html guardado (abre en navegador para inspeccionar)")
        print(f"{'='*60}\n")

        if not HEADLESS:
            input("Presiona ENTER para cerrar el navegador...")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(debug())
