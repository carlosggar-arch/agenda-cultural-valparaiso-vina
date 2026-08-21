from __future__ import annotations

import re
import unicodedata
from typing import Any

CATEGORY = {
    "exposiciones": {"id": "exposiciones", "label": "Exposiciones"},
    "cine": {"id": "cine", "label": "Cine"},
    "musica": {"id": "musica", "label": "Música"},
    "teatro": {"id": "teatro", "label": "Teatro"},
    "talleres": {"id": "cursos-talleres-campus", "label": "Cursos, talleres y campus"},
    "ferias": {"id": "ferias-gastronomia", "label": "Ferias y gastronomía"},
    "naturaleza": {"id": "naturaleza-deportes", "label": "Naturaleza y deportes"},
    "otros": {"id": "otros", "label": "Otros panoramas"},
}

TRAINING_CATEGORY_IDS = {
    "formacion",
    "formacion-taller",
    "cursos-talleres",
    "cursos-talleres-campus",
    "talleres-cursos",
    "cursos",
    "talleres",
}


def fold(value: Any) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def source_category(event: dict[str, Any]) -> dict[str, str]:
    source = event.get("primary_category") or (event.get("categories") or [None])[0] or {}
    label = str(source.get("label") or "").strip()
    category_id = str(source.get("id") or re.sub(r"\s+", "-", fold(label))).strip().casefold()
    return {"id": category_id, "label": label}


def evidence_text(event: dict[str, Any]) -> str:
    values = [
        event.get("title"),
        event.get("description"),
        event.get("organizer"),
        event.get("source_name"),
        *(event.get("tags") or []),
    ]
    return fold(" ".join(str(value) for value in values if value))


def is_training_source(source: dict[str, str]) -> bool:
    if source.get("id") in TRAINING_CATEGORY_IDS:
        return True
    return bool(re.search(r"\b(?:formacion|curso|cursos|taller|talleres|campus)\b", fold(source.get("label"))))


def is_summer_program(event: dict[str, Any]) -> bool:
    if str(event.get("event_type") or "") not in {"program", "registration_period"}:
        return False
    title = fold(event.get("title"))
    return bool(
        re.search(r"\b(?:campus|campamento|escuela de verano)\b", title)
        or (re.search(r"\bverano\b", title) and re.search(r"\binscripciones?\b", title))
    )


def explicit_title_category(event: dict[str, Any]) -> dict[str, str] | None:
    title = fold(event.get("title"))
    if not title:
        return None
    if re.search(r"\b(?:campus|campamento|escuela de verano)\b", title) or is_summer_program(event):
        return CATEGORY["talleres"]
    if re.search(r"\b(exposicion|exposiciones|muestra|muestras|visita guiada exposicion|visita guiada muestra)\b", title):
        return CATEGORY["exposiciones"]
    if re.search(r"\b(cine|pelicula|film|filme|documental|cortometraje|largometraje|proyeccion)\b", title):
        return CATEGORY["cine"]
    if re.search(r"\b(concierto|recital|jazz|coro|coral|orquesta|musica)\b", title):
        return CATEGORY["musica"]
    if re.search(r"\b(teatro|danza|ballet|circo|performance|funcion|espectaculo)\b", title):
        return CATEGORY["teatro"]
    if re.search(r"\b(taller|curso|clase|seminario|laboratorio|workshop|capacitacion|formacion)\b", title):
        return CATEGORY["talleres"]
    if re.search(r"\b(presentacion de?l? libro|presentacion libro|lanzamiento de?l? libro|lectura|poesia|encuentro literario|conversatorio literario)\b", title):
        return CATEGORY["otros"]
    return None


def infer_culture_category(event: dict[str, Any]) -> dict[str, str]:
    explicit = explicit_title_category(event)
    if explicit:
        return explicit

    text = evidence_text(event)
    if re.search(r"\b(exposicion|exposiciones|muestra|muestras|museo|museos|galeria|fotografia|artes visuales|arte contemporaneo|instalacion artistica)\b", text):
        return CATEGORY["exposiciones"]
    if re.search(r"\b(cine|pelicula|peliculas|film|filme|audiovisual|documental|documentales|cortometraje|cortometrajes|largometraje|proyeccion)\b", text):
        return CATEGORY["cine"]
    if re.search(r"\b(musica|musical|concierto|conciertos|recital|recitales|jazz|coro|coral|orquesta|cantautor|cantautora|dj|sonidos)\b", text):
        return CATEGORY["musica"]
    if re.search(r"\b(teatro|teatral|obra|obras|danza|ballet|circo|escenicas|escenico|performance|funcion|espectaculo)\b", text):
        return CATEGORY["teatro"]
    if re.search(r"\b(taller|talleres|curso|cursos|clase|clases|formacion|seminario|laboratorio|workshop|capacitacion|campus|campamento|escuela de verano)\b", text):
        return CATEGORY["talleres"]
    if re.search(r"\b(feria|ferias|mercado|mercados|gastronomia|gastronomico|gastronomica|cocina|culinario|culinaria|comida|cerveza|vino|degustacion)\b", text):
        return CATEGORY["ferias"]
    if re.search(r"\b(naturaleza|natural|senderismo|trekking|excursion|excursiones|deporte|deportes|ciclismo|running|kayak|bicicleta|caminata|caminatas|aire libre)\b", text):
        return CATEGORY["naturaleza"]
    return CATEGORY["otros"]


def resolve_public_category(event: dict[str, Any]) -> dict[str, str]:
    source = source_category(event)
    if is_training_source(source):
        return dict(CATEGORY["talleres"])
    if is_summer_program(event):
        return dict(CATEGORY["talleres"])
    if source.get("id") in {"museos", "exposiciones"}:
        return dict(CATEGORY["exposiciones"])
    if source.get("id") == "cultura" or fold(source.get("label")) == "cultura":
        return dict(infer_culture_category(event))
    if not source.get("id"):
        return dict(explicit_title_category(event) or CATEGORY["otros"])
    return {"id": source["id"], "label": source.get("label") or "Otros panoramas"}


def public_category_text(event: dict[str, Any]) -> str:
    return resolve_public_category(event)["label"]
