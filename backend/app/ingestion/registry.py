"""Connector registry: name -> connector class + metadata for the API."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.ingestion.base import Connector, IngestionError
from app.ingestion.connectors.manual_import import CSV_COLUMNS, ManualImportConnector
from app.ingestion.connectors.osm import OSMConnector


class UnknownConnectorError(ValueError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Conector no encontrado: {name}")
        self.name = name


CONNECTORS: dict[str, type] = {
    "manual_import": ManualImportConnector,
    "osm": OSMConnector,
}

CONNECTOR_METADATA: list[dict[str, Any]] = [
    {
        "name": "manual_import",
        "description": "Importación manual desde CSV (columnas: "
        + ", ".join(CSV_COLUMNS)
        + ")",
        "params": {
            "csv_content": "str — contenido completo del CSV (obligatorio)"
        },
    },
    {
        "name": "osm",
        "description": (
            "Restaurantes de OpenStreetMap vía Overpass API "
            "(pública, gratuita y legal)"
        ),
        "params": {"bbox": "str — 'south,west,north,east' (obligatorio)"},
    },
]


def build_connector(name: str, params: Mapping[str, Any]) -> Connector:
    """Instantiate a connector; raises UnknownConnectorError/IngestionError."""
    connector_class = CONNECTORS.get(name)
    if connector_class is None:
        raise UnknownConnectorError(name)
    try:
        instance = connector_class(**dict(params))
    except TypeError as exc:
        raise IngestionError(
            f"Parámetros inválidos para el conector '{name}': {exc}"
        ) from exc
    return instance
