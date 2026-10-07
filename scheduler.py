"""
Scheduler — corre el scraper cada 30 minutos indefinidamente.
Uso: python scheduler.py
"""

import asyncio
import logging
import time
from datetime import datetime

log = logging.getLogger(__name__)


async def loop_principal():
    from scraper import main as scraper_main

    INTERVALO_MINUTOS = 30

    print("=" * 50)
    print("  SCRAPER IPHONES — BOGOTÁ Y ALREDEDORES")
    print(f"  Ciclo cada {INTERVALO_MINUTOS} minutos")
    print("  Ctrl+C para detener")
    print("=" * 50)
    print()

    ciclo = 0
    while True:
        ciclo += 1
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{'─'*40}")
        print(f"  Ciclo #{ciclo} — {ahora}")
        print(f"{'─'*40}")

        try:
            await scraper_main()
        except Exception as e:
            log.error(f"Error en ciclo #{ciclo}: {e}", exc_info=True)

        proximo = datetime.now()
        segundos = INTERVALO_MINUTOS * 60
        print(f"\n⏳ Próximo ciclo en {INTERVALO_MINUTOS} min...")

        await asyncio.sleep(segundos)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("scraper.log"),
            logging.StreamHandler()
        ]
    )
    try:
        asyncio.run(loop_principal())
    except KeyboardInterrupt:
        print("\n\n🛑 Scraper detenido.")
