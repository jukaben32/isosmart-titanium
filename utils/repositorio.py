# -*- coding: utf-8 -*-
"""
utils/repositorio.py
--------------------
Capa de persistencia para leads y proyectos.

PROBLEMA QUE RESUELVE
=====================
`ProjectManager` escribía `data/leads_db.json` y `data/projects_db.json` en el
sistema de archivos local. En Streamlit Community Cloud el contenedor se
reinicia y el disco NO persiste: cada redeploy o hibernación **borraba todos los
leads capturados**. La app prometía un CRM y entregaba una caché.

Además el `.gitignore` no excluía esos archivos, así que un `git add .` desde la
máquina de pruebas publicaba datos personales de clientes en un repo público.

DISEÑO
======
Interfaz única (`RepositorioLeads`) con dos implementaciones:

  * `RepositorioSQLite`   — por defecto, cero configuración, un archivo.
  * `RepositorioSupabase` — producción; se activa solo si hay credenciales.

La selección es automática vía `obtener_repositorio()`. El resto de la app no
sabe cuál está usando.

CONFIGURACIÓN DE SUPABASE
=========================
En `.streamlit/secrets.toml` (o variables de entorno):

    [supabase]
    url = "https://<proyecto>.supabase.co"
    anon_key = "<anon key del proyecto>"

⚠️ Usar la **anon key** del proyecto, no un *personal access token* de la cuenta.
Son cosas distintas: el PAT (`sbp_...`) administra TODA tu cuenta de Supabase y
nunca debe salir de tu gestor de contraseñas ni aparecer en una app cliente.

Tabla esperada (ejecutar en el SQL editor de Supabase):

    create table if not exists leads (
        id          text primary key,
        fecha       timestamptz not null default now(),
        nombre      text,
        email       text,
        telefono    text,
        ubicacion   text,
        tipo_proyecto text,
        area_estimada numeric,
        mensaje     text
    );
    alter table leads enable row level security;
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from abc import ABC, abstractmethod
from contextlib import closing
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

RUTA_SQLITE_DEFECTO = os.path.join("data", "isosmart.sqlite3")

_CAMPOS = (
    "nombre", "email", "telefono", "ubicacion",
    "tipo_proyecto", "area_estimada", "mensaje",
)


def _ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RepositorioLeads(ABC):
    """Contrato mínimo que la app necesita para gestionar leads."""

    @abstractmethod
    def guardar(self, lead: Dict[str, Any]) -> Dict[str, Any]: ...

    @abstractmethod
    def listar(self) -> List[Dict[str, Any]]: ...

    @property
    def descripcion(self) -> str:
        return self.__class__.__name__


# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------

class RepositorioSQLite(RepositorioLeads):
    """
    Persistencia local en un único archivo SQLite.

    Frente al JSON anterior: escrituras transaccionales (no se corrompe si el
    proceso muere a mitad), consultas sin cargar todo en memoria, y un formato
    que aguanta miles de registros.
    """

    def __init__(self, ruta: str = RUTA_SQLITE_DEFECTO):
        self.ruta = ruta
        carpeta = os.path.dirname(os.path.abspath(ruta))
        if carpeta:
            os.makedirs(carpeta, exist_ok=True)
        self._crear_esquema()

    def _conectar(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.ruta)
        con.row_factory = sqlite3.Row
        return con

    def _crear_esquema(self) -> None:
        with closing(self._conectar()) as con, con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS leads (
                    id            TEXT PRIMARY KEY,
                    fecha         TEXT NOT NULL,
                    nombre        TEXT,
                    email         TEXT,
                    telefono      TEXT,
                    ubicacion     TEXT,
                    tipo_proyecto TEXT,
                    area_estimada REAL,
                    mensaje       TEXT
                )
                """
            )
            con.execute("CREATE INDEX IF NOT EXISTS idx_leads_fecha ON leads(fecha DESC)")
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS proyectos (
                    id         TEXT PRIMARY KEY,
                    updated_at TEXT NOT NULL,
                    datos      TEXT NOT NULL
                )
                """
            )

    def guardar(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        registro = {
            "id": lead.get("id") or uuid.uuid4().hex[:12],
            "fecha": lead.get("fecha") or _ahora_iso(),
            **{campo: lead.get(campo) for campo in _CAMPOS},
        }
        with closing(self._conectar()) as con, con:
            con.execute(
                "INSERT OR REPLACE INTO leads "
                "(id, fecha, nombre, email, telefono, ubicacion, tipo_proyecto, area_estimada, mensaje) "
                "VALUES (:id, :fecha, :nombre, :email, :telefono, :ubicacion, :tipo_proyecto, "
                ":area_estimada, :mensaje)",
                registro,
            )
        return registro

    def listar(self) -> List[Dict[str, Any]]:
        with closing(self._conectar()) as con:
            filas = con.execute("SELECT * FROM leads ORDER BY fecha DESC").fetchall()
        return [dict(f) for f in filas]

    # -- proyectos -------------------------------------------------------
    def guardar_proyecto(self, proyecto_id: str, datos: Dict[str, Any]) -> None:
        with closing(self._conectar()) as con, con:
            con.execute(
                "INSERT OR REPLACE INTO proyectos (id, updated_at, datos) VALUES (?, ?, ?)",
                (proyecto_id, _ahora_iso(), json.dumps(datos, ensure_ascii=False)),
            )

    def obtener_proyecto(self, proyecto_id: str) -> Optional[Dict[str, Any]]:
        with closing(self._conectar()) as con:
            fila = con.execute("SELECT * FROM proyectos WHERE id = ?", (proyecto_id,)).fetchone()
        if not fila:
            return None
        return {"id": fila["id"], "updated_at": fila["updated_at"], **json.loads(fila["datos"])}

    def listar_proyectos(self) -> List[Dict[str, Any]]:
        with closing(self._conectar()) as con:
            filas = con.execute("SELECT * FROM proyectos ORDER BY updated_at DESC").fetchall()
        return [
            {"id": f["id"], "updated_at": f["updated_at"], **json.loads(f["datos"])}
            for f in filas
        ]

    def eliminar_proyecto(self, proyecto_id: str) -> None:
        with closing(self._conectar()) as con, con:
            con.execute("DELETE FROM proyectos WHERE id = ?", (proyecto_id,))


# ---------------------------------------------------------------------------
# Supabase (PostgREST)
# ---------------------------------------------------------------------------

class RepositorioSupabase(RepositorioLeads):
    """
    Persistencia en Supabase vía su API REST. Sin SDK adicional: solo `requests`,
    que ya está en requirements.txt.
    """

    def __init__(self, url: str, anon_key: str, tabla: str = "leads", timeout: int = 10):
        self.url = url.rstrip("/")
        self.anon_key = anon_key
        self.tabla = tabla
        self.timeout = timeout

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "apikey": self.anon_key,
            "Authorization": f"Bearer {self.anon_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def guardar(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        import requests

        registro = {
            "id": lead.get("id") or uuid.uuid4().hex[:12],
            "fecha": lead.get("fecha") or _ahora_iso(),
            **{campo: lead.get(campo) for campo in _CAMPOS},
        }
        resp = requests.post(
            f"{self.url}/rest/v1/{self.tabla}",
            headers=self._headers, json=registro, timeout=self.timeout,
        )
        resp.raise_for_status()
        return registro

    def listar(self) -> List[Dict[str, Any]]:
        import requests

        resp = requests.get(
            f"{self.url}/rest/v1/{self.tabla}",
            headers=self._headers,
            params={"select": "*", "order": "fecha.desc"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Selección automática
# ---------------------------------------------------------------------------

def _leer_config_supabase() -> Optional[Dict[str, str]]:
    url = key = ""
    try:
        import streamlit as st

        seccion = st.secrets.get("supabase", {})
        url = str(seccion.get("url", "") or "")
        key = str(seccion.get("anon_key", "") or "")
    except Exception:
        pass

    url = url or os.getenv("SUPABASE_URL", "")
    key = key or os.getenv("SUPABASE_ANON_KEY", "")

    if url and key:
        return {"url": url, "anon_key": key}
    return None


def obtener_repositorio() -> RepositorioLeads:
    """
    Supabase si hay credenciales configuradas; SQLite en caso contrario.

    Nunca lanza por falta de configuración: la app debe seguir funcionando en
    local sin ninguna credencial.
    """
    config = _leer_config_supabase()
    if config:
        return RepositorioSupabase(**config)
    return RepositorioSQLite()
