"""Analisis territorial por UPL para estudiantes en Bogota.

Este modulo descarga la capa UPL desde ArcGIS REST, asigna estudiantes a
poligonos mediante spatial join y calcula indicadores agregados listos para
visualizacion en Folium.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence
from urllib.parse import urlencode

import geopandas as gpd
import numpy as np
import pandas as pd


CRS_ANALISIS = "EPSG:3116"
CRS_VISUALIZACION = "EPSG:4326"

UPL_SERVICE_URL = (
    "https://serviciosgis.catastrobogota.gov.co/arcgis/rest/services/"
    "Mapa_Referencia/Mapa_Referencia/MapServer/44"
)

NOMBRES_UPL_CANDIDATOS = (
    "NOMBRE",
    "NOMBRE_UPL",
    "NOM_UPL",
    "UPL",
    "nombre",
    "nombre_upl",
)

CODIGOS_UPL_CANDIDATOS = (
    "CODIGO",
    "CODIGO_UPL",
    "COD_UPL",
    "OBJECTID",
    "objectid",
)


def construir_url_geojson_arcgis(
    service_url: str = UPL_SERVICE_URL,
    where: str = "1=1",
    out_fields: str = "*",
) -> str:
    """Construye la URL de consulta GeoJSON para un servicio ArcGIS REST.

    Parameters
    ----------
    service_url : str, default=UPL_SERVICE_URL
        URL base del layer ArcGIS REST.
    where : str, default="1=1"
        Filtro SQL del servicio.
    out_fields : str, default="*"
        Campos a descargar.

    Returns
    -------
    str
        URL lista para ``geopandas.read_file``.
    """

    query = urlencode(
        {
            "where": where,
            "outFields": out_fields,
            "returnGeometry": "true",
            "f": "geojson",
        }
    )
    return f"{service_url.rstrip('/')}/query?{query}"


def descargar_upl(
    service_url: str = UPL_SERVICE_URL,
    crs_objetivo: str = CRS_ANALISIS,
) -> gpd.GeoDataFrame:
    """Descarga la capa UPL desde ArcGIS REST y la reproyecta.

    Parameters
    ----------
    service_url : str, default=UPL_SERVICE_URL
        URL base del layer UPL.
    crs_objetivo : str, default=CRS_ANALISIS
        CRS final para analisis espacial.

    Returns
    -------
    geopandas.GeoDataFrame
        Capa UPL en el CRS objetivo.
    """

    url_geojson = construir_url_geojson_arcgis(service_url)
    upl = gpd.read_file(url_geojson)
    upl = _normalizar_geometria(upl)
    return asegurar_crs(upl, crs_objetivo=crs_objetivo)


def asegurar_crs(
    gdf: gpd.GeoDataFrame,
    crs_objetivo: str = CRS_ANALISIS,
    crs_origen: str = CRS_VISUALIZACION,
) -> gpd.GeoDataFrame:
    """Verifica y reproyecta un GeoDataFrame al CRS objetivo.

    Parameters
    ----------
    gdf : geopandas.GeoDataFrame
        Capa geográfica de entrada.
    crs_objetivo : str, default=CRS_ANALISIS
        CRS final esperado.
    crs_origen : str, default=CRS_VISUALIZACION
        CRS asumido cuando la capa no declara CRS.

    Returns
    -------
    geopandas.GeoDataFrame
        Copia de la capa en el CRS objetivo.
    """

    resultado = _normalizar_geometria(gdf).copy()
    if resultado.crs is None:
        resultado = resultado.set_crs(crs_origen)
    if str(resultado.crs).upper() != crs_objetivo:
        resultado = resultado.to_crs(crs_objetivo)
    return resultado


def crear_estudiantes_gdf_desde_panel(
    panel_df: pd.DataFrame,
    lon_col: str = "LONG_IDECA",
    lat_col: str = "LAT_IDECA",
    crs_origen: str = CRS_VISUALIZACION,
    crs_destino: str = CRS_ANALISIS,
) -> gpd.GeoDataFrame:
    """Crea un GeoDataFrame de estudiantes desde columnas de coordenadas.

    Parameters
    ----------
    panel_df : pandas.DataFrame
        Panel con coordenadas de domicilio.
    lon_col : str, default="LONG_IDECA"
        Columna de longitud.
    lat_col : str, default="LAT_IDECA"
        Columna de latitud.
    crs_origen : str, default=CRS_VISUALIZACION
        CRS de las coordenadas originales.
    crs_destino : str, default=CRS_ANALISIS
        CRS final para analisis espacial.

    Returns
    -------
    geopandas.GeoDataFrame
        Estudiantes en el CRS destino.
    """

    requeridas = {lon_col, lat_col}
    faltantes = sorted(requeridas - set(panel_df.columns))
    if faltantes:
        raise ValueError(f"Faltan columnas de coordenadas: {faltantes}")

    datos = panel_df.dropna(subset=[lon_col, lat_col]).copy()
    estudiantes = gpd.GeoDataFrame(
        datos,
        geometry=gpd.points_from_xy(datos[lon_col], datos[lat_col]),
        crs=crs_origen,
    )
    return estudiantes.to_crs(crs_destino)


def filtrar_panel_para_upl(
    panel_df: pd.DataFrame,
    convocatorias: Sequence[str] = ("JU3", "JU4"),
    nivel_formacion: str | None = "UNIVERSITARIO",
    modalidad: str | None = "PRESENCIAL",
    periodo_maximo: int | None = 4,
    estados: Sequence[str] = ("Matriculado", "Abandono"),
) -> pd.DataFrame:
    """Filtra el panel antes del analisis territorial por UPL.

    Parameters
    ----------
    panel_df : pandas.DataFrame
        Panel de estudiantes.
    convocatorias : sequence of str, default=("JU3", "JU4")
        Convocatorias a conservar.
    nivel_formacion : str, optional, default="UNIVERSITARIO"
        Nivel de formacion requerido. Si es ``None`` no filtra.
    modalidad : str, optional, default="PRESENCIAL"
        Modalidad requerida. Si es ``None`` no filtra.
    periodo_maximo : int, optional, default=4
        Periodo maximo a conservar. Si es ``None`` no filtra.
    estados : sequence of str, default=("Matriculado", "Abandono")
        Estados a conservar.

    Returns
    -------
    pandas.DataFrame
        Panel filtrado con ``acceso_transporte``.
    """

    panel = panel_df.copy()
    if "acceso_transporte" not in panel.columns:
        panel["acceso_transporte"] = panel["sitp_cercanos"] + panel["tm_cercanos"]

    mascara = panel["CONVOCATORIA"].isin(convocatorias) & panel["estado"].isin(estados)
    if nivel_formacion is not None:
        mascara &= panel["NIVEL_FORMACION"].eq(nivel_formacion)
    if modalidad is not None:
        mascara &= panel["TIPO_MODALIDAD"].eq(modalidad)
    if periodo_maximo is not None:
        mascara &= panel["periodo_orden"].le(periodo_maximo)
    return panel.loc[mascara].copy()


def asignar_estudiantes_a_upl(
    estudiantes_gdf: gpd.GeoDataFrame,
    upl_gdf: gpd.GeoDataFrame,
    columnas_upl: Sequence[str] | None = None,
    predicate: str = "within",
) -> gpd.GeoDataFrame:
    """Asocia cada estudiante con el poligono UPL que contiene su domicilio.

    Parameters
    ----------
    estudiantes_gdf : geopandas.GeoDataFrame
        Capa de estudiantes con geometria puntual.
    upl_gdf : geopandas.GeoDataFrame
        Capa de UPL con geometria poligonal.
    columnas_upl : sequence of str, optional
        Columnas UPL a transferir. Si es ``None`` usa identificador y nombre
        detectados automaticamente.
    predicate : str, default="within"
        Predicado espacial para ``geopandas.sjoin``.

    Returns
    -------
    geopandas.GeoDataFrame
        Estudiantes con atributos UPL agregados.
    """

    estudiantes = asegurar_crs(estudiantes_gdf, CRS_ANALISIS)
    upl = preparar_upl_para_join(upl_gdf)

    if columnas_upl is None:
        columnas_upl = _columnas_upl_base(upl)
    columnas_join = list(dict.fromkeys([*columnas_upl, "geometry"]))

    asignados = gpd.sjoin(
        estudiantes,
        upl[columnas_join],
        how="left",
        predicate=predicate,
    )
    return asignados.drop(columns=["index_right"], errors="ignore")


def preparar_upl_para_join(upl_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Normaliza nombres base de UPL y garantiza EPSG:3116.

    Parameters
    ----------
    upl_gdf : geopandas.GeoDataFrame
        Capa UPL original.

    Returns
    -------
    geopandas.GeoDataFrame
        Capa con columnas ``upl_id`` y ``upl_nombre``.
    """

    upl = asegurar_crs(upl_gdf, CRS_ANALISIS).copy()
    id_col = _detectar_columna(upl, CODIGOS_UPL_CANDIDATOS)
    nombre_col = _detectar_columna(upl, NOMBRES_UPL_CANDIDATOS)

    upl["upl_id"] = upl[id_col].astype(str) if id_col else upl.index.astype(str)
    upl["upl_nombre"] = upl[nombre_col].astype(str) if nombre_col else upl["upl_id"]
    return upl


def construir_upl_enriquecida(
    estudiantes_gdf: gpd.GeoDataFrame,
    upl_gdf: gpd.GeoDataFrame,
    corte_distancia_m: float = 5000,
    id_estudiante_col: str = "ID_PERSONA",
    usar_ultima_observacion: bool = True,
    periodo_col: str = "periodo_orden",
) -> gpd.GeoDataFrame:
    """Calcula indicadores por UPL y los incorpora a la geometria UPL.

    Parameters
    ----------
    estudiantes_gdf : geopandas.GeoDataFrame
        Estudiantes con geometria y variables de movilidad/desempeno.
    upl_gdf : geopandas.GeoDataFrame
        Poligonos UPL.
    corte_distancia_m : float, default=5000
        Punto de corte para clasificar estudiantes cercanos/lejanos.
    id_estudiante_col : str, default="ID_PERSONA"
        Columna identificadora. Si no existe, se usa ``DOCUMENTO`` o el indice.
    usar_ultima_observacion : bool, default=True
        Si es ``True``, conserva la ultima observacion disponible por
        estudiante antes de agregar. Recomendado para paneles estudiante-periodo.
    periodo_col : str, default="periodo_orden"
        Columna usada para ordenar observaciones del panel.

    Returns
    -------
    geopandas.GeoDataFrame
        UPL enriquecida con indicadores agregados.
    """

    upl = preparar_upl_para_join(upl_gdf)
    estudiantes = _preparar_estudiantes_para_agregacion(
        estudiantes_gdf,
        corte_distancia_m=corte_distancia_m,
        id_estudiante_col=id_estudiante_col,
        usar_ultima_observacion=usar_ultima_observacion,
        periodo_col=periodo_col,
    )
    asignados = asignar_estudiantes_a_upl(estudiantes, upl)
    indicadores = _agregar_indicadores_upl(asignados)

    columnas_base = ["upl_id", "upl_nombre", "geometry"]
    upl_enriquecida = upl[columnas_base].merge(indicadores, on=["upl_id", "upl_nombre"], how="left")
    columnas_indicadores = [col for col in upl_enriquecida.columns if col not in columnas_base]
    upl_enriquecida[columnas_indicadores] = upl_enriquecida[columnas_indicadores].fillna(0)
    return gpd.GeoDataFrame(upl_enriquecida, geometry="geometry", crs=upl.crs)


def construir_upl_enriquecida_desde_servicio(
    estudiantes_gdf: gpd.GeoDataFrame,
    service_url: str = UPL_SERVICE_URL,
    corte_distancia_m: float = 5000,
    id_estudiante_col: str = "ID_PERSONA",
    usar_ultima_observacion: bool = True,
    periodo_col: str = "periodo_orden",
) -> gpd.GeoDataFrame:
    """Descarga UPL y retorna un GeoDataFrame enriquecido.

    Parameters
    ----------
    estudiantes_gdf : geopandas.GeoDataFrame
        Estudiantes con geometria y variables de analisis.
    service_url : str, default=UPL_SERVICE_URL
        Servicio ArcGIS REST de UPL.
    corte_distancia_m : float, default=5000
        Corte cercano/lejano en metros.
    id_estudiante_col : str, default="ID_PERSONA"
        Identificador de estudiante.
    usar_ultima_observacion : bool, default=True
        Si es ``True``, conserva una observacion por estudiante.
    periodo_col : str, default="periodo_orden"
        Columna temporal para seleccionar ultima observacion.

    Returns
    -------
    geopandas.GeoDataFrame
        UPL enriquecida en ``EPSG:3116``.
    """

    upl = descargar_upl(service_url=service_url, crs_objetivo=CRS_ANALISIS)
    return construir_upl_enriquecida(
        estudiantes_gdf=estudiantes_gdf,
        upl_gdf=upl,
        corte_distancia_m=corte_distancia_m,
        id_estudiante_col=id_estudiante_col,
        usar_ultima_observacion=usar_ultima_observacion,
        periodo_col=periodo_col,
    )


def exportar_upl_enriquecida(
    upl_gdf: gpd.GeoDataFrame,
    ruta_salida: str | Path,
    driver: str | None = None,
) -> Path:
    """Exporta la capa UPL enriquecida.

    Parameters
    ----------
    upl_gdf : geopandas.GeoDataFrame
        Capa UPL enriquecida.
    ruta_salida : str or pathlib.Path
        Ruta de salida. Use ``.geojson`` para conservar geometria.
    driver : str, optional
        Driver de salida de GeoPandas.

    Returns
    -------
    pathlib.Path
        Ruta guardada.
    """

    salida = Path(ruta_salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    if driver:
        upl_gdf.to_file(salida, driver=driver)
    else:
        upl_gdf.to_file(salida)
    return salida


def _preparar_estudiantes_para_agregacion(
    estudiantes_gdf: gpd.GeoDataFrame,
    corte_distancia_m: float,
    id_estudiante_col: str,
    usar_ultima_observacion: bool,
    periodo_col: str,
) -> gpd.GeoDataFrame:
    estudiantes = asegurar_crs(estudiantes_gdf, CRS_ANALISIS).copy()
    id_col = _resolver_id_estudiante(estudiantes, id_estudiante_col)
    estado_col = _resolver_estado(estudiantes)

    if usar_ultima_observacion and periodo_col in estudiantes.columns:
        estudiantes = (
            estudiantes.sort_values([id_col, periodo_col])
            .groupby(id_col, as_index=False)
            .tail(1)
            .copy()
        )

    if "acceso_transporte" not in estudiantes.columns:
        estudiantes["acceso_transporte"] = estudiantes["sitp_cercanos"] + estudiantes["tm_cercanos"]

    if "pct_aprob_acum" not in estudiantes.columns:
        estudiantes["pct_aprob_acum"] = np.nan

    estudiantes["estudiante_id_upl"] = estudiantes[id_col]
    estudiantes["estado_upl"] = estudiantes[estado_col].map(_normalizar_estado)
    estudiantes["grupo_distancia"] = np.where(
        estudiantes["distancia_ies"] < corte_distancia_m,
        "cercano",
        "lejano",
    )
    return estudiantes


def _agregar_indicadores_upl(estudiantes_upl: gpd.GeoDataFrame) -> pd.DataFrame:
    datos = estudiantes_upl.dropna(subset=["upl_id", "upl_nombre"]).copy()
    if datos.empty:
        return pd.DataFrame(columns=["upl_id", "upl_nombre"])

    agregado = (
        datos.groupby(["upl_id", "upl_nombre"], observed=True)
        .agg(
            n_estudiantes=("estudiante_id_upl", "nunique"),
            distancia_ies_promedio=("distancia_ies", "mean"),
            distancia_ies_mediana=("distancia_ies", "median"),
            distancia_ies_desv_est=("distancia_ies", "std"),
            sitp_cercanos_promedio=("sitp_cercanos", "mean"),
            tm_cercanos_promedio=("tm_cercanos", "mean"),
            acceso_transporte_promedio=("acceso_transporte", "mean"),
            pct_abandono=("estado_upl", lambda s: (s == "Abandono").mean()),
            pct_matriculados=("estado_upl", lambda s: (s == "Matriculado").mean()),
            pct_aprob_acum_promedio=("pct_aprob_acum", "mean"),
        )
        .reset_index()
    )

    grupos = (
        datos.groupby(["upl_id", "upl_nombre", "grupo_distancia"], observed=True)
        .agg(
            n_grupo=("estudiante_id_upl", "nunique"),
            tasa_abandono=("estado_upl", lambda s: (s == "Abandono").mean()),
            pct_aprob_acum_promedio=("pct_aprob_acum", "mean"),
        )
        .reset_index()
    )
    grupos = _pivotar_indicadores_grupo(grupos)

    resultado = agregado.merge(grupos, on=["upl_id", "upl_nombre"], how="left")
    resultado["distancia_ies_desv_est"] = resultado["distancia_ies_desv_est"].fillna(0)
    for grupo in ("cercano", "lejano"):
        n_col = f"n_{grupo}"
        resultado[f"pct_estudiantes_{grupo}s"] = resultado[n_col].fillna(0) / resultado["n_estudiantes"]
        resultado[f"tasa_abandono_{grupo}s"] = resultado[f"tasa_abandono_{grupo}"].fillna(0)
        resultado[f"pct_aprob_acum_promedio_{grupo}s"] = resultado[
            f"pct_aprob_acum_promedio_{grupo}"
        ]

    return resultado.drop(
        columns=[
            "n_cercano",
            "n_lejano",
            "tasa_abandono_cercano",
            "tasa_abandono_lejano",
            "pct_aprob_acum_promedio_cercano",
            "pct_aprob_acum_promedio_lejano",
        ],
        errors="ignore",
    )


def _pivotar_indicadores_grupo(grupos: pd.DataFrame) -> pd.DataFrame:
    pivotes = []
    for variable in ("n_grupo", "tasa_abandono", "pct_aprob_acum_promedio"):
        pivote = grupos.pivot(
            index=["upl_id", "upl_nombre"],
            columns="grupo_distancia",
            values=variable,
        ).reset_index()
        pivote = pivote.rename(
            columns={
                "cercano": f"{variable}_cercano",
                "lejano": f"{variable}_lejano",
            }
        )
        pivotes.append(pivote)

    resultado = pivotes[0]
    for pivote in pivotes[1:]:
        resultado = resultado.merge(pivote, on=["upl_id", "upl_nombre"], how="outer")
    return resultado.rename(
        columns={
            "n_grupo_cercano": "n_cercano",
            "n_grupo_lejano": "n_lejano",
        }
    )


def _normalizar_geometria(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    resultado = gdf.copy()
    if "SHAPE" in resultado.columns and resultado.geometry.name != "SHAPE":
        try:
            resultado = resultado.set_geometry("SHAPE")
        except (TypeError, ValueError):
            pass
    return resultado


def _columnas_upl_base(upl_gdf: gpd.GeoDataFrame) -> list[str]:
    columnas = ["upl_id", "upl_nombre"]
    return [col for col in columnas if col in upl_gdf.columns]


def _detectar_columna(df: pd.DataFrame, candidatos: Sequence[str]) -> str | None:
    columnas_lower = {col.lower(): col for col in df.columns}
    for candidato in candidatos:
        if candidato in df.columns:
            return candidato
        if candidato.lower() in columnas_lower:
            return columnas_lower[candidato.lower()]
    return None


def _resolver_id_estudiante(df: pd.DataFrame, id_estudiante_col: str) -> str:
    for candidato in (id_estudiante_col, "ID_PERSONA", "DOCUMENTO"):
        if candidato in df.columns:
            return candidato
    df["__id_estudiante_index"] = df.index
    return "__id_estudiante_index"


def _resolver_estado(df: pd.DataFrame) -> str:
    for candidato in ("estado", "ULTIMO_ESTADO"):
        if candidato in df.columns:
            return candidato
    raise ValueError("No se encontro columna de estado: use 'estado' o 'ULTIMO_ESTADO'.")


def _normalizar_estado(valor: object) -> str:
    texto = str(valor).strip().upper()
    if texto in {"ABANDONO", "ABANDONO DE FORMACION"}:
        return "Abandono"
    if texto == "MATRICULADO":
        return "Matriculado"
    return str(valor)
