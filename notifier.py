"""
Módulo de notificaciones por Telegram.
Envía alertas con foto, precio y link cuando encuentra una ganga.
"""
import logging
import aiohttp

log = logging.getLogger(__name__)


class TelegramNotifier:
    BASE_URL = "https://api.telegram.org/bot{token}/{method}"

    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id

    def _url(self, method: str) -> str:
        return self.BASE_URL.format(token=self.token, method=method)

    def _estrellas_descuento(self, pct: float) -> str:
        if pct >= 50:
            return "🔥🔥🔥"
        if pct >= 40:
            return "🔥🔥"
        return "🔥"

    def _formatear_precio(self, precio: int) -> str:
        return f"${precio:,.0f}".replace(",", ".")

    def _make_session(self):
        """Crea sesión aiohttp sin verificación SSL (solo para entorno local; en producción debe verificarse)."""
        tcp = aiohttp.TCPConnector(ssl=False)
        return aiohttp.ClientSession(connector=tcp)

    async def enviar_alerta(
        self,
        titulo: str,
        precio: int,
        precio_ref: int,
        descuento_pct: float,
        ciudad: str,
        link: str,
        img_url: str = "",
        fuente_precio: str = "referencia",
    ):
        estrellas = self._estrellas_descuento(descuento_pct)
        precio_fmt = self._formatear_precio(precio)
        ref_fmt = self._formatear_precio(precio_ref)
        fuente_label = "📈 Promedio real del mercado" if "mercado" in fuente_precio else "📋 Precio de referencia"

        texto = (
            f"{estrellas} *GANGA DETECTADA* {estrellas}\n\n"
            f"📱 *{titulo}*\n\n"
            f"💰 Precio: *{precio_fmt} COP*\n"
            f"📊 Mercado: ~{ref_fmt} COP\n"
            f"💸 Descuento: *{descuento_pct}% menos*\n"
            f"📍 Ciudad: {ciudad}\n"
            f"🔎 {fuente_label}\n\n"
            f"🔗 [Ver anuncio]({link})"
        )

        async with self._make_session() as session:
            if img_url and img_url.startswith("http"):
                await self._enviar_con_foto(session, texto, img_url)
            else:
                await self._enviar_texto(session, texto)

    async def _enviar_con_foto(self, session, texto: str, img_url: str):
        payload = {
            "chat_id": self.chat_id,
            "photo": img_url,
            "caption": texto,
            "parse_mode": "Markdown",
        }
        try:
            async with session.post(self._url("sendPhoto"), json=payload, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 200:
                    log.info("📨 Alerta enviada con foto")
                else:
                    data = await r.json()
                    log.warning(f"Foto falló ({data.get('description')}), enviando texto...")
                    await self._enviar_texto(session, texto)
        except Exception as e:
            log.error(f"Error enviando foto: {e}")
            await self._enviar_texto(session, texto)

    async def _enviar_texto(self, session, texto: str):
        payload = {
            "chat_id": self.chat_id,
            "text": texto,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        }
        try:
            async with session.post(self._url("sendMessage"), json=payload, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 200:
                    log.info("📨 Alerta enviada (texto)")
                else:
                    data = await r.json()
                    log.error(f"Error Telegram: {data}")
        except Exception as e:
            log.error(f"Error enviando mensaje: {e}")

    async def enviar_resumen(self, total_hoy: int, total_historico: int):
        texto = (
            f"📈 *Resumen del día*\n\n"
            f"Gangas encontradas hoy: *{total_hoy}*\n"
            f"Total histórico: {total_historico}"
        )
        async with self._make_session() as session:
            await self._enviar_texto(session, texto)