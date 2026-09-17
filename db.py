"""Conexión a Postgres (Supabase durante el piloto -- cualquier Postgres
después, AWS RDS/Cloud SQL incluidos, sin cambiar una sola línea de los
*_store.py) -- reemplaza a sheet_cache.py/gspread como capa de acceso a
datos de toda la app.

Google Sheets tenía una cuota de lecturas por minuto que la app entera
terminó chocando varias veces en producción (ver el historial de
sheet_cache.py/token_store.py) -- Postgres no tiene ese límite, así que
aquí ya no hace falta ningún caché manual con TTL: un solo Engine de
SQLAlchemy, reutilizado durante toda la vida del proceso, con su propio
pool de conexiones que ya se encarga de reciclarlas.

La cadena de conexión vive en el Secret/variable de entorno DATABASE_URL
(formato estándar: postgresql://usuario:clave@host:puerto/basededatos --
Supabase la da lista en Settings -> Database -> Connection string, modo
"Session pooler" para el uso normal de la app). Nunca se pega esa cadena
en el código ni en el chat -- vive solo en los Secrets de Streamlit
Cloud / variables de entorno de GitHub Actions, igual que antes vivía
GOOGLE_CREDENTIALS_JSON."""

import os

import sqlalchemy


def crear_engine(database_url: str) -> sqlalchemy.engine.Engine:
    """Para sync_diario.py y cualquier script que corra fuera de
    Streamlit -- ellos mismos leen DATABASE_URL de su propia variable de
    entorno y llaman esta función directo, sin pasar por engine()."""
    return sqlalchemy.create_engine(database_url, pool_pre_ping=True)


try:
    import streamlit as st

    @st.cache_resource
    def engine() -> sqlalchemy.engine.Engine:
        """El Engine de toda la app mientras Streamlit esté corriendo --
        se crea una sola vez por proceso, no por rerun."""
        return crear_engine(st.secrets["DATABASE_URL"])

except ModuleNotFoundError:
    def engine() -> sqlalchemy.engine.Engine:
        return crear_engine(os.environ["DATABASE_URL"])
