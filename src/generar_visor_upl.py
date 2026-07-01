"""Genera el visor Folium con indicadores agregados por UPL.

El script descarga automaticamente la capa UPL desde ArcGIS REST, calcula
indicadores territoriales y guarda un nuevo HTML del visor.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from map_visualization import (
    cargar_datos,
    construir_mapa,
    guardar_mapa,
    preparar_capas,
)
from spatial_analysis import (
    construir_upl_enriquecida_desde_servicio,
    crear_estudiantes_gdf_desde_panel,
    exportar_upl_enriquecida,
    filtrar_panel_para_upl,
)


DATA_DIR = Path("../data")
PANEL_PATH = Path("panel_insumo_refactorizado.xlsx")
OUTPUTS_DIR = Path("../outputs")
VISOR_SALIDA = Path("visor_bogota_upl.html")
UPL_GEOJSON_SALIDA = OUTPUTS_DIR / "upl_enriquecida.geojson"

INDICADOR_UPL = "distancia_ies_promedio"
CORTE_DISTANCIA_M = 5000
RADIO_CERCANIA_M = 800
SEMILLA = 42

MUESTRA_POR_ESTADO = {
    "MATRICULADO": 50,
    "ABANDONO DE FORMACION": 50,
}


def main() -> None:
    """Ejecuta el flujo completo de generacion del visor UPL."""

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    df_info_ies, df_maestra, df_paraderos_sitp, estaciones_tm = cargar_datos(DATA_DIR)
    capas = preparar_capas(
        df_maestra=df_maestra,
        df_info_ies=df_info_ies,
        df_paraderos_sitp=df_paraderos_sitp,
        estaciones_tm=estaciones_tm,
        radio_cercania_m=RADIO_CERCANIA_M,
    )

    panel = pd.read_excel(PANEL_PATH)
    panel_upl = filtrar_panel_para_upl(panel)
    estudiantes_upl = crear_estudiantes_gdf_desde_panel(panel_upl)
    upl_enriquecida = construir_upl_enriquecida_desde_servicio(
        estudiantes_gdf=estudiantes_upl,
        corte_distancia_m=CORTE_DISTANCIA_M,
        id_estudiante_col="ID_PERSONA",
        usar_ultima_observacion=True,
        periodo_col="periodo_orden",
    )
    exportar_upl_enriquecida(upl_enriquecida, UPL_GEOJSON_SALIDA, driver="GeoJSON")

    mapa = construir_mapa(
        capas=capas,
        muestra_por_estado=MUESTRA_POR_ESTADO,
        upl_gdf=upl_enriquecida,
        indicador_upl=INDICADOR_UPL,
        semilla=SEMILLA,
        aplicar_jitter=True,
    )
    guardar_mapa(mapa, VISOR_SALIDA)


if __name__ == "__main__":
    main()
