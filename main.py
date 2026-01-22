from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime

app = FastAPI(title="CoWork Manager API", version="1.0.0")

API_PREFIX = "/api/v1"

# -----------------------------
# Modelos
# -----------------------------
class SalaCreate(BaseModel):
    nombre: str = Field(..., min_length=1)
    capacidad: int = Field(..., ge=1)
    ubicacion: str = Field(..., min_length=1)

class SalaOut(BaseModel):
    id: int
    nombre: str
    capacidad: int
    ubicacion: str

class ReservaCreate(BaseModel):
    sala_id: int = Field(..., ge=1)
    nombre_solicitante: str = Field(..., min_length=1)
    fecha_inicio: str  # ISO string
    fecha_fin: str     # ISO string

class ReservaPatch(BaseModel):
    fecha_fin: str  # ISO string (solo esto)

class ReservaOut(BaseModel):
    id: int
    sala_id: int
    nombre_solicitante: str
    fecha_inicio: str
    fecha_fin: str

# -----------------------------
# "BD" en memoria
# -----------------------------
salas: Dict[int, SalaOut] = {}
reservas: Dict[int, ReservaOut] = {}
next_sala_id = 1
next_reserva_id = 1

def parse_iso(dt_str: str) -> datetime:
    """
    Valida formato ISO-8601.
    Ej: "2026-01-20T10:00:00"
    """
    try:
        return datetime.fromisoformat(dt_str)
    except ValueError:
        raise HTTPException(status_code=400, detail={"error": "Fecha inválida (use ISO-8601). Ej: 2026-01-20T10:00:00"})

# -----------------------------
# MÓDULO A: Gestión de Salas
# -----------------------------

# 1) Listar Salas
@app.get(f"{API_PREFIX}/salas", response_model=List[SalaOut], status_code=200)
def listar_salas():
    return list(salas.values())

# 2) Obtener detalle de Sala
@app.get(f"{API_PREFIX}/salas/{{sala_id}}", response_model=SalaOut, status_code=200)
def obtener_sala(sala_id: int):
    sala = salas.get(sala_id)
    if not sala:
        raise HTTPException(status_code=404, detail={"error": "Sala no encontrada"})
    return sala

# 3) Crear Sala (no duplicar nombre)
@app.post(f"{API_PREFIX}/salas", status_code=201)
def crear_sala(payload: SalaCreate):
    global next_sala_id

    # Validación: no duplicar nombre (case-insensitive)
    for s in salas.values():
        if s.nombre.strip().lower() == payload.nombre.strip().lower():
            raise HTTPException(status_code=400, detail={"error": "Nombre duplicado"})

    sala = SalaOut(
        id=next_sala_id,
        nombre=payload.nombre.strip(),
        capacidad=payload.capacidad,
        ubicacion=payload.ubicacion.strip(),
    )
    salas[next_sala_id] = sala
    next_sala_id += 1
    return {"id": sala.id, "mensaje": "Creado"}

# 4) Eliminar Sala
@app.delete(f"{API_PREFIX}/salas/{{sala_id}}", status_code=204)
def eliminar_sala(sala_id: int):
    if sala_id not in salas:
        raise HTTPException(status_code=404, detail={"error": "Sala no encontrada"})

    # Si quisieras, podrías bloquear borrado si hay reservas asociadas.
    # Como no lo piden, lo dejamos simple: borra sala y reservas relacionadas.
    del salas[sala_id]

    # Limpieza de reservas asociadas (opcional, pero ordenado)
    to_delete = [rid for rid, r in reservas.items() if r.sala_id == sala_id]
    for rid in to_delete:
        del reservas[rid]

    return None  # 204 No Content

# -----------------------------
# MÓDULO B: Gestión de Reservas
# -----------------------------

# 5) Crear Reserva (sala_id debe existir)
@app.post(f"{API_PREFIX}/reservas", status_code=201)
def crear_reserva(payload: ReservaCreate):
    global next_reserva_id

    # Validación: sala existe
    if payload.sala_id not in salas:
        raise HTTPException(status_code=400, detail={"error": "sala_id no existe"})

    # Validación fechas
    inicio = parse_iso(payload.fecha_inicio)
    fin = parse_iso(payload.fecha_fin)
    if fin <= inicio:
        raise HTTPException(status_code=400, detail={"error": "fecha_fin debe ser mayor a fecha_inicio"})

    reserva = ReservaOut(
        id=next_reserva_id,
        sala_id=payload.sala_id,
        nombre_solicitante=payload.nombre_solicitante.strip(),
        fecha_inicio=payload.fecha_inicio,
        fecha_fin=payload.fecha_fin,
    )
    reservas[next_reserva_id] = reserva
    next_reserva_id += 1
    return {"id": reserva.id, "mensaje": "Creado"}

# 6) Historial de Reservas (filtro ?sala_id=5)
@app.get(f"{API_PREFIX}/reservas", response_model=List[ReservaOut], status_code=200)
def historial_reservas(sala_id: Optional[int] = Query(default=None)):
    all_res = list(reservas.values())
    if sala_id is not None:
        all_res = [r for r in all_res if r.sala_id == sala_id]
    return all_res

# 7) Modificar Reserva (PATCH parcial: solo fecha_fin)
@app.patch(f"{API_PREFIX}/reservas/{{reserva_id}}", status_code=200)
def modificar_reserva(reserva_id: int, payload: ReservaPatch):
    reserva = reservas.get(reserva_id)
    if not reserva:
        raise HTTPException(status_code=404, detail={"error": "Reserva no encontrada"})

    # Validar fecha_fin nueva
    inicio = parse_iso(reserva.fecha_inicio)
    nueva_fin = parse_iso(payload.fecha_fin)
    if nueva_fin <= inicio:
        raise HTTPException(status_code=400, detail={"error": "fecha_fin debe ser mayor a fecha_inicio"})

    reserva.fecha_fin = payload.fecha_fin
    reservas[reserva_id] = reserva
    return {"id": reserva.id, "mensaje": "Actualizado", "fecha_fin": reserva.fecha_fin}

# 8) Cancelar Reserva
@app.delete(f"{API_PREFIX}/reservas/{{reserva_id}}", status_code=204)
def cancelar_reserva(reserva_id: int):
    if reserva_id not in reservas:
        raise HTTPException(status_code=404, detail={"error": "Reserva no encontrada"})
    del reservas[reserva_id]
    return None  # 204 No Content
