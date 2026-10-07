"""
Base de datos SQLite — guarda items notificados y aprende precios del mercado.
"""

import sqlite3
import logging

log = logging.getLogger(__name__)
DB_FILE = "iphones.db"


class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self._crear_tablas()
        log.info(f"📦 Base de datos lista: {DB_FILE}")

    def _crear_tablas(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS items_notificados (
                id              TEXT PRIMARY KEY,
                titulo          TEXT,
                precio          INTEGER,
                ciudad          TEXT,
                link            TEXT,
                notificado_en   DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS precios_mercado (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                modelo          TEXT NOT NULL,
                precio          INTEGER NOT NULL,
                ciudad          TEXT,
                item_id         TEXT,
                visto_en        DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS precios_promedio (
                modelo          TEXT PRIMARY KEY,
                promedio        INTEGER NOT NULL,
                minimo          INTEGER NOT NULL,
                maximo          INTEGER NOT NULL,
                total_muestras  INTEGER NOT NULL,
                actualizado_en  DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.conn.commit()

    # ── Items notificados ─────────────────────────────────────────────────────

    def ya_notificado(self, item_id: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM items_notificados WHERE id = ?", (item_id,)
        )
        return cur.fetchone() is not None

    def guardar_item(self, item_id: str, titulo: str, precio: int, ciudad: str, link: str):
        try:
            self.conn.execute(
                """INSERT OR IGNORE INTO items_notificados
                   (id, titulo, precio, ciudad, link) VALUES (?, ?, ?, ?, ?)""",
                (item_id, titulo, precio, ciudad, link),
            )
            self.conn.commit()
        except Exception as e:
            log.error(f"Error guardando item: {e}")

    # ── Precios de mercado ────────────────────────────────────────────────────

    def registrar_precio(self, modelo: str, precio: int, ciudad: str, item_id: str):
        """Guarda cada precio visto para aprender el mercado."""
        try:
            self.conn.execute(
                """INSERT INTO precios_mercado (modelo, precio, ciudad, item_id)
                   VALUES (?, ?, ?, ?)""",
                (modelo, precio, ciudad, item_id),
            )
            self.conn.commit()
            self._recalcular_promedio(modelo)
        except Exception as e:
            log.error(f"Error registrando precio: {e}")

    def _recalcular_promedio(self, modelo: str):
        """Recalcula el promedio de mercado para un modelo usando los ultimos 60 dias."""
        cur = self.conn.execute("""
            SELECT precio FROM precios_mercado
            WHERE modelo = ?
              AND visto_en >= datetime('now', '-60 days')
            ORDER BY precio
        """, (modelo,))
        precios = [r[0] for r in cur.fetchall()]

        if len(precios) < 3:
            return  # Necesitamos al menos 3 muestras para ser confiables

        # Eliminar el 10% mas alto y 10% mas bajo para quitar outliers
        n = len(precios)
        corte = max(1, n // 10)
        precios_limpios = precios[corte:-corte] if n > 10 else precios

        promedio = int(sum(precios_limpios) / len(precios_limpios))
        minimo = min(precios_limpios)
        maximo = max(precios_limpios)

        self.conn.execute("""
            INSERT INTO precios_promedio (modelo, promedio, minimo, maximo, total_muestras, actualizado_en)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(modelo) DO UPDATE SET
                promedio = excluded.promedio,
                minimo = excluded.minimo,
                maximo = excluded.maximo,
                total_muestras = excluded.total_muestras,
                actualizado_en = excluded.actualizado_en
        """, (modelo, promedio, minimo, maximo, len(precios_limpios)))
        self.conn.commit()

        log.info(f"   📊 {modelo}: promedio ${promedio:,} "
                 f"(min ${minimo:,} / max ${maximo:,} / {len(precios_limpios)} muestras)")

    def obtener_precio_mercado(self, modelo: str) -> dict | None:
        """Retorna el precio de mercado aprendido. None si no hay suficientes datos."""
        cur = self.conn.execute(
            """SELECT promedio, minimo, maximo, total_muestras
               FROM precios_promedio WHERE modelo = ?""",
            (modelo,)
        )
        row = cur.fetchone()
        if row:
            return {"promedio": row[0], "minimo": row[1], "maximo": row[2], "muestras": row[3]}
        return None

    def obtener_todos_promedios(self) -> list:
        cur = self.conn.execute("""
            SELECT modelo, promedio, minimo, maximo, total_muestras, actualizado_en
            FROM precios_promedio ORDER BY modelo
        """)
        return [
            {"modelo": r[0], "promedio": r[1], "minimo": r[2],
             "maximo": r[3], "muestras": r[4], "actualizado": r[5]}
            for r in cur.fetchall()
        ]

    def estadisticas(self) -> dict:
        cur = self.conn.execute("SELECT COUNT(*) FROM items_notificados")
        total = cur.fetchone()[0]
        cur = self.conn.execute(
            "SELECT COUNT(*) FROM items_notificados WHERE date(notificado_en) = date('now')"
        )
        hoy = cur.fetchone()[0]
        cur = self.conn.execute("SELECT COUNT(*) FROM precios_mercado")
        muestras = cur.fetchone()[0]
        return {"total_alertas": total, "alertas_hoy": hoy, "muestras_precio": muestras}

    def close(self):
        self.conn.close()
