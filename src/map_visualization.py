"""Construccion de capas geograficas y visor Folium para estudiantes en Bogota.

El modulo separa explicitamente dos etapas:

* Analisis espacial en EPSG:3116, un CRS proyectado en metros adecuado para
  Bogota.
* Visualizacion en EPSG:4326, requerida por Folium/Leaflet.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Mapping

import folium
import geopandas as gpd
import numpy as np
import pandas as pd
from folium.plugins import MarkerCluster
from shapely.geometry import Point


CRS_ANALISIS = "EPSG:3116"
CRS_VISUALIZACION = "EPSG:4326"

ESTADO_MATRICULADO = "MATRICULADO"
ESTADO_ABANDONO = "ABANDONO DE FORMACION"
ESTADOS_VISUALIZACION = (ESTADO_MATRICULADO, ESTADO_ABANDONO)

COLUMNAS_TM = [
    "objectid",
    "nombre_estacion",
    "latitud_estacion",
    "longitud_estacion",
]

COLUMNAS_SITP = [
    "GLOBALID",
    "NTRNOMBRE",
    "coordinates",
]

COLUMNAS_REQUERIDAS_ESTUDIANTES = [
    "DOCUMENTO",
    "latitud_ies",
    "longitud_ies",
    "LONG_IDECA",
    "LAT_IDECA",
    "CODUPZ_IDECA",
    "PROGRAMA",
    "CONVOCATORIA",
]

URL_ESTACIONES_TM = (
    "https://gis.transmilenio.gov.co/arcgis/rest/services/"
    "Troncal/consulta_estaciones_troncales/MapServer/0/query"
    "?where=1=1"
    "&outFields=*"
    "&returnGeometry=true"
    "&f=geojson"
)


def cargar_datos(
    data_dir: str | Path = "../data",
    archivo_ies: str = "info_ies.xlsx",
    archivo_maestra: str = "clasificacion-estados_processed_BASE_MAESTRA_AJUSTADA_BDM20260521.xlsx",
    archivo_sitp: str = "Paraderos_SITP_Bogotá_D_C.xlsx",
    estaciones_tm_url: str = URL_ESTACIONES_TM,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, gpd.GeoDataFrame]:
    """Carga los insumos usados por el visor.

    Parameters
    ----------
    data_dir : str or pathlib.Path, default="../data"
        Carpeta donde se encuentran los archivos de entrada.
    archivo_ies : str, default="info_ies.xlsx"
        Archivo con coordenadas y metadatos de IES.
    archivo_maestra : str, default=...
        Archivo de base maestra de estudiantes.
    archivo_sitp : str, default="Paraderos_SITP_Bogotá_D_C.xlsx"
        Archivo de paraderos SITP.
    estaciones_tm_url : str, default=URL_ESTACIONES_TM
        Servicio GeoJSON de estaciones troncales de TransMilenio.

    Returns
    -------
    tuple
        ``(df_info_ies, df_maestra, df_paraderos_sitp, estaciones_tm)``.
    """

    data_path = Path(data_dir)
    df_info_ies = pd.read_excel(
        data_path / archivo_ies,
        usecols=["latitud_ies", "longitud_ies", "codigo_ies", "nombre"],
    )
    df_maestra = pd.read_excel(data_path / archivo_maestra, sheet_name="subset")
    df_paraderos_sitp = pd.read_excel(
        data_path / archivo_sitp,
        usecols=lambda col: col in COLUMNAS_SITP,
    )
    
    estaciones_tm = gpd.read_file(estaciones_tm_url, columns=COLUMNAS_TM)

    return df_info_ies, df_maestra, df_paraderos_sitp, estaciones_tm


def asegurar_crs(
    gdf: gpd.GeoDataFrame,
    crs_objetivo: str = CRS_ANALISIS,
    crs_origen: str = CRS_VISUALIZACION,
) -> gpd.GeoDataFrame:
    """Verifica y reproyecta un GeoDataFrame al CRS objetivo.

    Si el GeoDataFrame no tiene CRS, se asume ``crs_origen``. Si ya tiene CRS
    pero no coincide con ``crs_objetivo``, se reproyecta.

    Parameters
    ----------
    gdf : geopandas.GeoDataFrame
        Capa de entrada.
    crs_objetivo : str, default=CRS_ANALISIS
        CRS final esperado.
    crs_origen : str, default=CRS_VISUALIZACION
        CRS que se asigna cuando la capa no declara CRS.

    Returns
    -------
    geopandas.GeoDataFrame
        Copia de la capa en el CRS objetivo.
    """

    resultado = gdf.copy()
    if resultado.crs is None:
        resultado = resultado.set_crs(crs_origen)
    if str(resultado.crs).upper() != crs_objetivo:
        resultado = resultado.to_crs(crs_objetivo)
    return resultado


def preparar_capas(
    df_maestra: pd.DataFrame,
    df_info_ies: pd.DataFrame,
    df_paraderos_sitp: pd.DataFrame,
    estaciones_tm: gpd.GeoDataFrame,
    convocatorias: tuple[str, ...] = ("JU3", "JU4"),
    radio_cercania_m: float = 800,
) -> dict[str, gpd.GeoDataFrame]:
    """Prepara capas geograficas en EPSG:3116 y calcula metricas espaciales.

    Todas las operaciones geometricas se realizan en ``EPSG:3116``. Las
    coordenadas originales de estudiantes, IES, SITP y TransMilenio vienen en
    longitud/latitud, por lo que primero se crean como ``EPSG:4326`` y luego se
    reproyectan a ``EPSG:3116``.

    Parameters
    ----------
    df_maestra : pandas.DataFrame
        Base maestra de estudiantes.
    df_info_ies : pandas.DataFrame
        Tabla de IES con columnas ``codigo_ies``, ``latitud_ies`` y
        ``longitud_ies``.
    df_paraderos_sitp : pandas.DataFrame
        Tabla de paraderos SITP.
    estaciones_tm : geopandas.GeoDataFrame
        Capa de estaciones de TransMilenio.
    convocatorias : tuple of str, default=("JU3", "JU4")
        Convocatorias usadas para filtrar estudiantes.
    radio_cercania_m : float, default=800
        Radio, en metros, para contar paraderos/estaciones cercanas.

    Returns
    -------
    dict[str, geopandas.GeoDataFrame]
        Diccionario con las capas ``estudiantes``, ``sitp``, ``tm`` e ``ies``.
        Todas quedan en ``EPSG:3116``.
    """

    data = df_maestra.merge(
        df_info_ies,
        how="left",
        left_on="SNIES_IES",
        right_on="codigo_ies",
        suffixes=("", "_ies_info"),
    )
    data = (
        data[data["CONVOCATORIA"].isin(convocatorias)]
        .dropna(subset=COLUMNAS_REQUERIDAS_ESTUDIANTES)
        .copy()
    )

    estudiantes = _crear_puntos(
        data,
        x_col="LONG_IDECA",
        y_col="LAT_IDECA",
        crs_origen=CRS_VISUALIZACION,
        crs_destino=CRS_ANALISIS,
    )

    ies = (
        data[
            [
                "codigo_ies",
                "nombre",
                "latitud_ies",
                "longitud_ies",
            ]
        ]
        .drop_duplicates(subset=["codigo_ies", "latitud_ies", "longitud_ies"])
        .dropna(subset=["latitud_ies", "longitud_ies"])
        .copy()
    )
    ies_gdf = _crear_puntos(
        ies,
        x_col="longitud_ies",
        y_col="latitud_ies",
        crs_origen=CRS_VISUALIZACION,
        crs_destino=CRS_ANALISIS,
    )

    geometria_ies_wgs84 = gpd.GeoSeries(
        gpd.points_from_xy(data["longitud_ies"], data["latitud_ies"]),
        crs=CRS_VISUALIZACION,
        index=data.index,
    )
    estudiantes["geometry_ies"] = geometria_ies_wgs84.to_crs(CRS_ANALISIS)
    estudiantes["distancia_ies"] = estudiantes.geometry.distance(
        estudiantes["geometry_ies"]
    )

    sitp_df = df_paraderos_sitp.copy()
    sitp_df[["longitud_sitp", "latitud_sitp"]] = sitp_df["coordinates"].apply(
        lambda value: pd.Series(_parsear_coordenadas(value))
    )
    sitp = _crear_puntos(
        sitp_df,
        x_col="longitud_sitp",
        y_col="latitud_sitp",
        crs_origen=CRS_VISUALIZACION,
        crs_destino=CRS_ANALISIS,
    )

    tm_base = estaciones_tm.copy()
    if "longitud_estacion" in tm_base and "latitud_estacion" in tm_base:
        tm = _crear_puntos(
            tm_base,
            x_col="longitud_estacion",
            y_col="latitud_estacion",
            crs_origen=CRS_VISUALIZACION,
            crs_destino=CRS_ANALISIS,
        )
    else:
        tm = asegurar_crs(tm_base, crs_objetivo=CRS_ANALISIS)

    estudiantes = contar_puntos_cercanos(
        estudiantes,
        sitp,
        radio_m=radio_cercania_m,
        nombre_columna="sitp_cercanos",
    )
    estudiantes = contar_puntos_cercanos(
        estudiantes,
        tm,
        radio_m=radio_cercania_m,
        nombre_columna="tm_cercanos",
    )

    return {
        "estudiantes": estudiantes,
        "sitp": sitp,
        "tm": tm,
        "ies": ies_gdf,
    }


def contar_puntos_cercanos(
    estudiantes_gdf: gpd.GeoDataFrame,
    puntos_gdf: gpd.GeoDataFrame,
    radio_m: float,
    id_estudiante: str = "DOCUMENTO",
    nombre_columna: str = "puntos_cercanos",
) -> gpd.GeoDataFrame:
    """Cuenta puntos ubicados dentro de un radio alrededor de cada estudiante.

    Parameters
    ----------
    estudiantes_gdf : geopandas.GeoDataFrame
        Capa de estudiantes en ``EPSG:3116``.
    puntos_gdf : geopandas.GeoDataFrame
        Capa de puntos de interes en ``EPSG:3116``.
    radio_m : float
        Radio de busqueda en metros.
    id_estudiante : str, default="DOCUMENTO"
        Columna identificadora de estudiante.
    nombre_columna : str, default="puntos_cercanos"
        Nombre de la columna de salida.

    Returns
    -------
    geopandas.GeoDataFrame
        Copia de estudiantes con el conteo agregado.
    """

    estudiantes = asegurar_crs(estudiantes_gdf, CRS_ANALISIS)
    puntos = asegurar_crs(puntos_gdf, CRS_ANALISIS)

    buffers = estudiantes[[id_estudiante, "geometry"]].copy()
    buffers["geometry"] = buffers.geometry.buffer(radio_m)

    join = gpd.sjoin(buffers, puntos[["geometry"]], how="left", predicate="contains")
    conteo = (
        join.dropna(subset=["index_right"])
        .groupby(id_estudiante)
        .size()
        .rename(nombre_columna)
    )

    resultado = estudiantes.merge(conteo, on=id_estudiante, how="left")
    resultado[nombre_columna] = resultado[nombre_columna].fillna(0).astype(int)
    return resultado


def muestrear_estudiantes_por_estado(
    estudiantes_gdf: gpd.GeoDataFrame,
    tamanos_muestra: Mapping[str, int] | None = None,
    semilla: int = 42,
    modalidad: str | None = "PRESENCIAL",
) -> gpd.GeoDataFrame:
    """Selecciona una muestra reproducible de estudiantes por estado.

    Parameters
    ----------
    estudiantes_gdf : geopandas.GeoDataFrame
        Capa de estudiantes en ``EPSG:3116``.
    tamanos_muestra : mapping, optional
        Numero de estudiantes por estado. Por defecto toma 50 matriculados y
        50 abandonos.
    semilla : int, default=42
        Semilla para muestreo reproducible.
    modalidad : str, optional, default="PRESENCIAL"
        Valor de ``TIPO_MODALIDAD`` a conservar. Si es ``None`` no filtra.

    Returns
    -------
    geopandas.GeoDataFrame
        Muestra de estudiantes en ``EPSG:3116``.
    """

    tamanos = tamanos_muestra or {
        ESTADO_MATRICULADO: 50,
        ESTADO_ABANDONO: 50,
    }

    estudiantes = estudiantes_gdf.copy()
    if modalidad and "TIPO_MODALIDAD" in estudiantes:
        estudiantes = estudiantes[estudiantes["TIPO_MODALIDAD"] == modalidad]

    muestras = []
    for estado, n in tamanos.items():
        grupo = estudiantes[estudiantes["ULTIMO_ESTADO"] == estado]
        if not grupo.empty:
            muestras.append(grupo.sample(n=min(n, len(grupo)), random_state=semilla))

    if not muestras:
        return estudiantes.iloc[0:0].copy()

    return gpd.GeoDataFrame(pd.concat(muestras), crs=estudiantes.crs)


def construir_mapa(
    capas: Mapping[str, gpd.GeoDataFrame],
    muestra_por_estado: Mapping[str, int] | None = None,
    upl_gdf: gpd.GeoDataFrame | None = None,
    indicador_upl: str = "distancia_ies_promedio",
    semilla: int = 42,
    aplicar_jitter: bool = True,
    jitter_m: float = 150,
    radio_estudiante_m: float = 750,
    centro: tuple[float, float] = (4.65, -74.10),
    zoom_start: int = 11,
) -> folium.Map:
    """Construye un visor Folium profesional a partir de capas preparadas.

    La entrada debe estar en ``EPSG:3116``. Internamente se crean copias en
    ``EPSG:4326`` solo para Leaflet/Folium. Si ``aplicar_jitter`` es ``True``,
    el desplazamiento aleatorio se calcula en metros antes de reproyectar.

    Parameters
    ----------
    capas : mapping
        Diccionario con ``estudiantes``, ``sitp``, ``tm`` e ``ies``.
    muestra_por_estado : mapping, optional
        Numero de estudiantes a visualizar por estado.
    upl_gdf : geopandas.GeoDataFrame, optional
        Capa UPL enriquecida en ``EPSG:3116``. Si se entrega, se agrega como
        capa coropletica al visor.
    indicador_upl : str, default="distancia_ies_promedio"
        Indicador usado para colorear las UPL.
    semilla : int, default=42
        Semilla reproducible para muestreo y jitter.
    aplicar_jitter : bool, default=True
        Si es ``True``, desplaza los centros visuales para proteger domicilios.
    jitter_m : float, default=150
        Desplazamiento maximo en metros.
    radio_estudiante_m : float, default=750
        Radio de la circunferencia que representa cada estudiante.
    centro : tuple[float, float], default=(4.65, -74.10)
        Centro del mapa en ``(latitud, longitud)``.
    zoom_start : int, default=11
        Nivel inicial de zoom.

    Returns
    -------
    folium.Map
        Mapa interactivo listo para guardar o mostrar en notebook.
    """

    mapa = folium.Map(
        location=list(centro),
        zoom_start=zoom_start,
        tiles="CartoDB positron",
        control_scale=True,
    )

    folium.TileLayer("CartoDB dark_matter", name="Base oscura", control=True).add_to(
        mapa
    )
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap", control=True).add_to(mapa)

    if upl_gdf is not None:
        agregar_upl(
            mapa,
            asegurar_crs(upl_gdf, CRS_ANALISIS).to_crs(CRS_VISUALIZACION),
            indicador=indicador_upl,
        )

    estudiantes = muestrear_estudiantes_por_estado(
        asegurar_crs(capas["estudiantes"], CRS_ANALISIS),
        tamanos_muestra=muestra_por_estado,
        semilla=semilla,
    )
    estudiantes_vis = preparar_estudiantes_visualizacion(
        estudiantes,
        aplicar_jitter=aplicar_jitter,
        jitter_m=jitter_m,
        semilla=semilla,
    )

    agregar_estudiantes(
        mapa,
        estudiantes_vis,
        radio_m=radio_estudiante_m,
    )
    agregar_paraderos(mapa, asegurar_crs(capas["sitp"], CRS_ANALISIS).to_crs(CRS_VISUALIZACION))
    agregar_estaciones(mapa, asegurar_crs(capas["tm"], CRS_ANALISIS).to_crs(CRS_VISUALIZACION))
    agregar_ies(mapa, asegurar_crs(capas["ies"], CRS_ANALISIS).to_crs(CRS_VISUALIZACION))
    agregar_leyenda(mapa)

    folium.LayerControl(collapsed=False).add_to(mapa)
    return mapa


def preparar_estudiantes_visualizacion(
    estudiantes_gdf: gpd.GeoDataFrame,
    aplicar_jitter: bool = True,
    jitter_m: float = 150,
    semilla: int = 42,
) -> gpd.GeoDataFrame:
    """Crea una copia de estudiantes en EPSG:4326 para visualizacion.

    Parameters
    ----------
    estudiantes_gdf : geopandas.GeoDataFrame
        Capa de estudiantes en ``EPSG:3116``.
    aplicar_jitter : bool, default=True
        Activa o desactiva el desplazamiento aleatorio visual.
    jitter_m : float, default=150
        Desplazamiento maximo en metros.
    semilla : int, default=42
        Semilla para jitter reproducible.

    Returns
    -------
    geopandas.GeoDataFrame
        Capa en ``EPSG:4326`` con columnas ``dist_norm`` y ``geometry`` visual.
    """

    estudiantes = asegurar_crs(estudiantes_gdf, CRS_ANALISIS)
    resultado = estudiantes.copy()

    if aplicar_jitter and not resultado.empty:
        rng = np.random.default_rng(semilla)
        angulos = rng.uniform(0, 2 * np.pi, len(resultado))
        radios = jitter_m * np.sqrt(rng.uniform(0, 1, len(resultado)))
        dx = radios * np.cos(angulos)
        dy = radios * np.sin(angulos)
        resultado["geometry"] = [
            Point(geom.x + offset_x, geom.y + offset_y)
            for geom, offset_x, offset_y in zip(resultado.geometry, dx, dy)
        ]

    resultado = resultado.to_crs(CRS_VISUALIZACION)
    resultado["dist_norm"] = _normalizar_serie(resultado["distancia_ies"])
    return resultado


def agregar_estudiantes(
    mapa: folium.Map,
    estudiantes_gdf: gpd.GeoDataFrame,
    radio_m: float = 750,
    nombre_capa: str = "Estudiantes (muestra)",
) -> folium.FeatureGroup:
    """Agrega estudiantes como circunferencias sin mostrar domicilio exacto.

    Parameters
    ----------
    mapa : folium.Map
        Mapa Folium.
    estudiantes_gdf : geopandas.GeoDataFrame
        Capa de estudiantes en ``EPSG:4326``.
    radio_m : float, default=750
        Radio de cada circunferencia en metros.
    nombre_capa : str, default="Estudiantes (muestra)"
        Nombre visible en el control de capas.

    Returns
    -------
    folium.FeatureGroup
        Capa agregada al mapa.
    """

    capa = folium.FeatureGroup(name=nombre_capa, show=True)

    for _, row in estudiantes_gdf.iterrows():
        dist_norm = float(row.get("dist_norm", 0))
        color = _color_estado(row["ULTIMO_ESTADO"], dist_norm)
        weight = 1.2 + 2.2 * dist_norm
        fill_opacity = 0.18 + 0.22 * dist_norm

        popup = folium.Popup(
            html=(
                f"<b>Estado:</b> {row['ULTIMO_ESTADO']}<br>"
                f"<b>Distancia a IES:</b> {row['distancia_ies']:,.0f} m<br>"
                f"<b>SITP cercanos:</b> {row.get('sitp_cercanos', 0)}<br>"
                f"<b>TM cercanas:</b> {row.get('tm_cercanos', 0)}"
            ),
            max_width=280,
        )

        folium.Circle(
            location=[row.geometry.y, row.geometry.x],
            radius=radio_m,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=fill_opacity,
            opacity=0.85,
            weight=weight,
            popup=popup,
        ).add_to(capa)

    capa.add_to(mapa)
    return capa


def agregar_paraderos(
    mapa: folium.Map,
    sitp_gdf: gpd.GeoDataFrame,
    nombre_capa: str = "Paraderos SITP",
) -> MarkerCluster:
    """Agrega paraderos SITP en una capa independiente.

    Parameters
    ----------
    mapa : folium.Map
        Mapa Folium.
    sitp_gdf : geopandas.GeoDataFrame
        Paraderos en ``EPSG:4326``.
    nombre_capa : str, default="Paraderos SITP"
        Nombre visible en LayerControl.

    Returns
    -------
    folium.plugins.MarkerCluster
        Cluster agregado al mapa.
    """

    cluster = MarkerCluster(name=nombre_capa, show=False)
    for _, row in sitp_gdf.iterrows():
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=2.2,
            color="#1b8a5a",
            fill=True,
            fill_color="#47b881",
            fill_opacity=0.72,
            weight=0.8,
            tooltip=row.get("NTRNOMBRE"),
        ).add_to(cluster)
    cluster.add_to(mapa)
    return cluster


def agregar_estaciones(
    mapa: folium.Map,
    tm_gdf: gpd.GeoDataFrame,
    nombre_capa: str = "Estaciones TransMilenio",
) -> MarkerCluster:
    """Agrega estaciones de TransMilenio en una capa independiente.

    Parameters
    ----------
    mapa : folium.Map
        Mapa Folium.
    tm_gdf : geopandas.GeoDataFrame
        Estaciones en ``EPSG:4326``.
    nombre_capa : str, default="Estaciones TransMilenio"
        Nombre visible en LayerControl.

    Returns
    -------
    folium.plugins.MarkerCluster
        Cluster agregado al mapa.
    """

    cluster = MarkerCluster(name=nombre_capa, show=False)
    for _, row in tm_gdf.iterrows():
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=4.5,
            color="#2f2f2f",
            fill=True,
            fill_color="#f2c94c",
            fill_opacity=0.92,
            weight=1.1,
            tooltip=row.get("nombre_estacion"),
        ).add_to(cluster)
    cluster.add_to(mapa)
    return cluster


def agregar_ies(
    mapa: folium.Map,
    ies_gdf: gpd.GeoDataFrame,
    nombre_capa: str = "IES",
) -> folium.FeatureGroup:
    """Agrega instituciones de educacion superior.

    Parameters
    ----------
    mapa : folium.Map
        Mapa Folium.
    ies_gdf : geopandas.GeoDataFrame
        IES en ``EPSG:4326``.
    nombre_capa : str, default="IES"
        Nombre visible en LayerControl.

    Returns
    -------
    folium.FeatureGroup
        Capa agregada al mapa.
    """

    capa = folium.FeatureGroup(name=nombre_capa, show=True)
    for _, row in ies_gdf.iterrows():
        folium.Marker(
            location=[row.geometry.y, row.geometry.x],
            icon=folium.Icon(color="purple", icon="graduation-cap", prefix="fa"),
            tooltip=row.get("nombre", "IES"),
        ).add_to(capa)
    capa.add_to(mapa)
    return capa


def agregar_upl(
    mapa: folium.Map,
    upl_gdf: gpd.GeoDataFrame,
    indicador: str = "distancia_ies_promedio",
    nombre_capa: str = "UPL - indicadores agregados",
    show: bool = True,
) -> folium.FeatureGroup:
    """Agrega UPL enriquecidas como capa coropletica.

    Parameters
    ----------
    mapa : folium.Map
        Mapa Folium.
    upl_gdf : geopandas.GeoDataFrame
        UPL enriquecidas en ``EPSG:4326``.
    indicador : str, default="distancia_ies_promedio"
        Variable usada para colorear los poligonos.
    nombre_capa : str, default="UPL - indicadores agregados"
        Nombre visible en LayerControl.
    show : bool, default=True
        Define si la capa aparece activa al cargar el mapa.

    Returns
    -------
    folium.FeatureGroup
        Capa agregada al mapa.
    """

    upl = upl_gdf.copy()
    if indicador not in upl.columns:
        raise ValueError(f"El indicador UPL '{indicador}' no existe en la capa.")

    upl = _preparar_upl_tooltip(upl)
    minimo, maximo = _rango_color(upl[indicador])
    capa = folium.FeatureGroup(name=nombre_capa, show=show)

    folium.GeoJson(
        upl,
        name=nombre_capa,
        style_function=lambda feature: _estilo_upl(
            feature,
            indicador=indicador,
            minimo=minimo,
            maximo=maximo,
        ),
        highlight_function=lambda feature: {
            "weight": 2.0,
            "color": "#4A4A4A",
            "fillOpacity": 0.58,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=[
                "upl_nombre",
                "n_estudiantes_fmt",
                "distancia_ies_promedio_fmt",
                "pct_estudiantes_cercanos_fmt",
                "pct_estudiantes_lejanos_fmt",
                "tasa_abandono_cercanos_fmt",
                "tasa_abandono_lejanos_fmt",
                "pct_aprob_acum_promedio_cercanos_fmt",
                "pct_aprob_acum_promedio_lejanos_fmt",
            ],
            aliases=[
                "UPL",
                "Estudiantes",
                "Distancia promedio a IES",
                "Estudiantes cercanos (<5 km)",
                "Estudiantes lejanos (>=5 km)",
                "Abandono grupo cercano",
                "Abandono grupo lejano",
                "Aprobacion promedio grupo cercano",
                "Aprobacion promedio grupo lejano",
            ],
            sticky=True,
            labels=True,
            localize=False,
            style=(
                "background-color: white; color: #2b2b2b; "
                "font-family: Arial, sans-serif; font-size: 12px; "
                "padding: 8px; border: 1px solid #d8d8d8;"
            ),
        ),
    ).add_to(capa)

    capa.add_to(mapa)
    agregar_leyenda_upl(mapa, indicador=indicador, minimo=minimo, maximo=maximo)
    return capa


def agregar_leyenda_upl(
    mapa: folium.Map,
    indicador: str,
    minimo: float,
    maximo: float,
) -> None:
    """Agrega una leyenda coropletica para UPL.

    Parameters
    ----------
    mapa : folium.Map
        Mapa Folium.
    indicador : str
        Indicador representado.
    minimo : float
        Valor minimo de la escala.
    maximo : float
        Valor maximo de la escala.
    """

    titulo = _etiqueta_indicador_upl(indicador)
    html = f"""
    <div style="
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 9999;
        background: rgba(255, 255, 255, 0.94);
        padding: 12px 14px;
        border: 1px solid #d9d9d9;
        border-radius: 6px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.12);
        font-family: Arial, sans-serif;
        font-size: 12px;
        color: #2b2b2b;">
        <div style="font-weight: 700; margin-bottom: 8px;">UPL: {titulo}</div>
        <div style="width: 190px; height: 10px; background: linear-gradient(90deg, #440154, #31688e, #35b779, #fde725);"></div>
        <div style="display: flex; justify-content: space-between; width: 190px; margin-top: 4px;">
            <span>{_formatear_valor_indicador(minimo, indicador)}</span>
            <span>{_formatear_valor_indicador(maximo, indicador)}</span>
        </div>
    </div>
    """
    mapa.get_root().html.add_child(folium.Element(html))


def agregar_leyenda(mapa: folium.Map) -> None:
    """Agrega leyendas de gradiente por estado.

    Parameters
    ----------
    mapa : folium.Map
        Mapa Folium.
    """

    html = """
    <div style="
        position: fixed;
        bottom: 24px;
        left: 24px;
        z-index: 9999;
        background: rgba(255, 255, 255, 0.94);
        padding: 12px 14px;
        border: 1px solid #d9d9d9;
        border-radius: 6px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.12);
        font-family: Arial, sans-serif;
        font-size: 12px;
        color: #2b2b2b;">
        <div style="font-weight: 700; margin-bottom: 8px;">Distancia a la IES</div>
        <div style="margin-bottom: 7px;">Matriculados</div>
        <div style="width: 170px; height: 9px; background: linear-gradient(90deg, #9fd3f2, #135ca5);"></div>
        <div style="display: flex; justify-content: space-between; width: 170px; margin: 3px 0 8px 0;">
            <span>Cerca</span><span>Lejos</span>
        </div>
        <div style="margin-bottom: 7px;">Abandono de formacion</div>
        <div style="width: 170px; height: 9px; background: linear-gradient(90deg, #f7a6a6, #9b1d2a);"></div>
        <div style="display: flex; justify-content: space-between; width: 170px; margin-top: 3px;">
            <span>Cerca</span><span>Lejos</span>
        </div>
    </div>
    """
    mapa.get_root().html.add_child(folium.Element(html))


def guardar_mapa(mapa: folium.Map, ruta_salida: str | Path = "visor_bogota.html") -> Path:
    """Guarda el mapa en un archivo HTML.

    Parameters
    ----------
    mapa : folium.Map
        Mapa Folium.
    ruta_salida : str or pathlib.Path, default="visor_bogota.html"
        Ruta del archivo HTML.

    Returns
    -------
    pathlib.Path
        Ruta del archivo guardado.
    """

    salida = Path(ruta_salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    mapa.save(str(salida))
    return salida


def exportar_panel_con_metricas(
    panel_df: pd.DataFrame,
    estudiantes_gdf: gpd.GeoDataFrame,
    ruta_salida: str | Path,
) -> Path:
    """Exporta panel con distancia a IES y conteos de transporte cercano.

    Parameters
    ----------
    panel_df : pandas.DataFrame
        Panel original de estudiantes.
    estudiantes_gdf : geopandas.GeoDataFrame
        Capa de estudiantes con metricas calculadas.
    ruta_salida : str or pathlib.Path
        Ruta del Excel de salida.

    Returns
    -------
    pathlib.Path
        Ruta del archivo exportado.
    """

    metricas = estudiantes_gdf[
        ["DOCUMENTO", "distancia_ies", "sitp_cercanos", "tm_cercanos"]
    ].copy()
    salida = Path(ruta_salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    panel_df.merge(metricas, on="DOCUMENTO", how="inner").to_excel(salida, index=False)
    return salida


def _crear_puntos(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    crs_origen: str,
    crs_destino: str,
) -> gpd.GeoDataFrame:
    gdf = gpd.GeoDataFrame(
        df.copy(),
        geometry=gpd.points_from_xy(df[x_col], df[y_col]),
        crs=crs_origen,
    )
    return gdf.to_crs(crs_destino)


def _parsear_coordenadas(value: object) -> tuple[float, float]:
    if isinstance(value, str):
        parsed = ast.literal_eval(value)
    else:
        parsed = value
    return float(parsed[0]), float(parsed[1])


def _normalizar_serie(serie: pd.Series) -> pd.Series:
    minimo = serie.min()
    maximo = serie.max()
    if pd.isna(minimo) or pd.isna(maximo) or maximo == minimo:
        return pd.Series(0.5, index=serie.index)
    return (serie - minimo) / (maximo - minimo)


def _preparar_upl_tooltip(upl_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    upl = upl_gdf.copy()
    columnas_default = {
        "upl_nombre": "Sin nombre",
        "n_estudiantes": 0,
        "distancia_ies_promedio": np.nan,
        "pct_estudiantes_cercanos": np.nan,
        "pct_estudiantes_lejanos": np.nan,
        "tasa_abandono_cercanos": np.nan,
        "tasa_abandono_lejanos": np.nan,
        "pct_aprob_acum_promedio_cercanos": np.nan,
        "pct_aprob_acum_promedio_lejanos": np.nan,
    }
    for columna, valor in columnas_default.items():
        if columna not in upl.columns:
            upl[columna] = valor

    upl["n_estudiantes_fmt"] = upl["n_estudiantes"].apply(lambda valor: f"{valor:,.0f}")
    upl["distancia_ies_promedio_fmt"] = upl["distancia_ies_promedio"].apply(
        lambda valor: _formatear_metros(valor)
    )
    for columna in (
        "pct_estudiantes_cercanos",
        "pct_estudiantes_lejanos",
        "tasa_abandono_cercanos",
        "tasa_abandono_lejanos",
        "pct_aprob_acum_promedio_cercanos",
        "pct_aprob_acum_promedio_lejanos",
    ):
        upl[f"{columna}_fmt"] = upl[columna].apply(_formatear_porcentaje)
    return upl


def _estilo_upl(
    feature: dict,
    indicador: str,
    minimo: float,
    maximo: float,
) -> dict:
    valor = feature["properties"].get(indicador)
    color = _color_viridis(valor, minimo, maximo)
    return {
        "fillColor": color,
        "color": "#C7C7C7",
        "weight": 0.9,
        "fillOpacity": 0.48,
        "opacity": 0.95,
    }


def _rango_color(serie: pd.Series) -> tuple[float, float]:
    valores = pd.to_numeric(serie, errors="coerce").replace([np.inf, -np.inf], np.nan)
    valores = valores.dropna()
    if valores.empty:
        return 0.0, 1.0
    minimo = float(valores.quantile(0.02))
    maximo = float(valores.quantile(0.98))
    if minimo == maximo:
        maximo = minimo + 1
    return minimo, maximo


def _color_viridis(valor: object, minimo: float, maximo: float) -> str:
    if pd.isna(valor):
        return "#F2F2F2"
    normalizado = (float(valor) - minimo) / (maximo - minimo)
    normalizado = min(max(normalizado, 0), 1)
    colores = ["#440154", "#31688e", "#35b779", "#fde725"]
    posicion = normalizado * (len(colores) - 1)
    idx = int(np.floor(posicion))
    if idx >= len(colores) - 1:
        return colores[-1]
    fraccion = posicion - idx
    return _interpolar_color(colores[idx], colores[idx + 1], fraccion)


def _etiqueta_indicador_upl(indicador: str) -> str:
    etiquetas = {
        "distancia_ies_promedio": "Distancia promedio a la IES",
        "pct_abandono": "Porcentaje de abandono",
        "pct_aprob_acum_promedio": "Aprobacion acumulada promedio",
        "pct_estudiantes_lejanos": "Porcentaje de estudiantes lejanos",
        "pct_estudiantes_cercanos": "Porcentaje de estudiantes cercanos",
        "acceso_transporte_promedio": "Acceso promedio al transporte",
    }
    return etiquetas.get(indicador, indicador.replace("_", " ").title())


def _formatear_valor_indicador(valor: float, indicador: str) -> str:
    if indicador.startswith("pct_") or indicador.startswith("tasa_"):
        return _formatear_porcentaje(valor)
    if "distancia" in indicador:
        return _formatear_metros(valor)
    if pd.isna(valor):
        return "Sin dato"
    return f"{valor:,.2f}"


def _formatear_metros(valor: object) -> str:
    if pd.isna(valor):
        return "Sin dato"
    valor_float = float(valor)
    if abs(valor_float) >= 1000:
        return f"{valor_float / 1000:,.1f} km"
    return f"{valor_float:,.0f} m"


def _formatear_porcentaje(valor: object) -> str:
    if pd.isna(valor):
        return "Sin dato"
    return f"{float(valor):.1%}"


def _color_estado(estado: str, dist_norm: float) -> str:
    if estado == ESTADO_ABANDONO:
        return _interpolar_color("#f7a6a6", "#9b1d2a", dist_norm)
    return _interpolar_color("#9fd3f2", "#135ca5", dist_norm)


def _interpolar_color(color_inicial: str, color_final: str, valor: float) -> str:
    valor = min(max(float(valor), 0), 1)
    inicio = np.array(_hex_a_rgb(color_inicial))
    fin = np.array(_hex_a_rgb(color_final))
    rgb = np.round(inicio + (fin - inicio) * valor).astype(int)
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def _hex_a_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))
