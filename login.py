import asyncio
import json
from playwright.async_api import async_playwright

async def login():
    print("=" * 50)
    print("  LOGIN DE FACEBOOK")
    print("=" * 50)
    print()
    print("Se abrirá un navegador. Inicia sesión en Facebook.")
    print("Cuando estés en el feed principal, regresa aquí y presiona Enter.")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--start-maximized"]
        )

        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        page = await context.new_page()
        await page.goto("https://www.facebook.com/login")

        print("👉 Inicia sesión en el navegador que se abrió...")
        input("   Cuando estés dentro de Facebook, presiona ENTER aquí: ")

        cookies = await context.cookies()
        with open("session.json", "w") as f:
            json.dump(cookies, f, indent=2)

        print()
        print("✅ Sesión guardada en session.json")
        print("   Ahora corre: python scheduler.py")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(login())