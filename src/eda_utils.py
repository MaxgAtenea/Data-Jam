"""Utilidades para el analisis exploratorio del panel de estudiantes.

El modulo concentra la logica reutilizable del EDA: carga, filtros, tablas,
visualizaciones y conclusiones descriptivas por convocatoria.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


PALETA_ESTADO: dict[str, str] = {
    "Matriculado": "#2F6B9A",
    "Abandono": "#B85C5C",
}

PALETA_CONTINUA: list[str] = ["#E8EEF3", "#AFC2D3", "#6E93B3", "#2F6B9A"]

PALETA_ANALOGA: list[str] = [
    "#2F6B9A",
    "#5A6AB7",
    "#8A62B5",
    "#BA5D86",
]

PALETA_COMPLEMENTARIOS: list[str] = [
    "#2E8B57",
    "#7FBF7B",
    "#B39DDB",
    "#F4A582",
    "#CA0020",
]

VARIABLES_MOVILIDAD: list[str] = [
    "distancia_ies",
    "sitp_cercanos",
    "tm_cercanos",
    "acceso_transporte",
]

VARIABLES_DESCRIPTIVAS: list[str] = [
    "distancia_ies",
    "sitp_cercanos",
    "tm_cercanos",
    "acceso_transporte",
    "pct_aprob_acum",
]

ESTADOS_ANALISIS: list[str] = ["Matriculado", "Abandono"]


def configurar_estilo() -> None:
    """Configura una estetica limpia y consistente para todo el notebook.

    Returns
    -------
    None
    """

    sns.set_theme(
        context="notebook",
        style="whitegrid",
        palette=list(PALETA_ESTADO.values()),
        font="Arial",
        rc={
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#D6D6D6",
            "axes.labelcolor": "#222222",
            "axes.titleweight": "bold",
            "axes.grid": True,
            "grid.color": "#EAEAEA",
            "grid.linewidth": 0.8,
            "legend.frameon": False,
            "xtick.color": "#333333",
            "ytick.color": "#333333",
        },
    )
    plt.rcParams["figure.dpi"] = 120
    plt.rcParams["savefig.dpi"] = 220
    plt.rcParams["axes.spines.top"] = False
    plt.rcParams["axes.spines.right"] = False


def crear_directorios(
    figures_dir: str | Path = "../figures",
    outputs_dir: str | Path = "../outputs",
) -> tuple[Path, Path]:
    """Crea los directorios de figuras y salidas tabulares.

    Parameters
    ----------
    figures_dir : str or pathlib.Path, default="../figures"
        Carpeta para guardar visualizaciones.
    outputs_dir : str or pathlib.Path, default="../outputs"
        Carpeta para guardar tablas y conclusiones.

    Returns
    -------
    tuple[pathlib.Path, pathlib.Path]
        Rutas normalizadas de figuras y outputs.
    """

    figures_path = Path(figures_dir)
    outputs_path = Path(outputs_dir)
    figures_path.mkdir(parents=True, exist_ok=True)
    outputs_path.mkdir(parents=True, exist_ok=True)
    return figures_path, outputs_path


def cargar_panel(ruta_archivo: str | Path) -> pd.DataFrame:
    """Carga el panel de estudiantes desde Excel.

    Parameters
    ----------
    ruta_archivo : str or pathlib.Path
        Ruta del archivo ``panel_insumo_refactorizado.xlsx``.

    Returns
    -------
    pandas.DataFrame
        Panel cargado.
    """

    return pd.read_excel(ruta_archivo)


def preparar_panel(
    df: pd.DataFrame,
    convocatorias: Sequence[str] = ("JU3", "JU4"),
    nivel_formacion: str = "UNIVERSITARIO",
    modalidad: str = "PRESENCIAL",
    periodo_maximo: int = 8,
    distancia_ies_maxima: float = 40000,
    estados: Sequence[str] = ("Matriculado", "Abandono"),
) -> pd.DataFrame:
    """Aplica filtros del estudio y crea la variable de acceso al transporte.

    Parameters
    ----------
    df : pandas.DataFrame
        Panel original.
    convocatorias : sequence of str, default=("JU3", "JU4")
        Convocatorias a conservar.
    nivel_formacion : str, default="UNIVERSITARIO"
        Nivel de formacion requerido.
    modalidad : str, default="PRESENCIAL"
        Modalidad requerida.
    periodo_maximo : int, default=4
        Periodo maximo a conservar.
    estados : sequence of str, default=("Matriculado", "Abandono")
        Estados academicos a conservar.

    Returns
    -------
    pandas.DataFrame
        Panel filtrado con ``acceso_transporte``.
    """

    columnas_requeridas = [
        "ID_PERSONA",
        "periodo_orden",
        "CONVOCATORIA",
        "distancia_ies",
        "sitp_cercanos",
        "tm_cercanos",
        "estado",
        "pct_aprob_acum",
        "NIVEL_FORMACION",
        "TIPO_MODALIDAD",
    ]
    faltantes = sorted(set(columnas_requeridas) - set(df.columns))
    if faltantes:
        raise ValueError(f"Faltan columnas requeridas: {faltantes}")

    panel = df.copy()
    panel["acceso_transporte"] = panel["sitp_cercanos"] + panel["tm_cercanos"]

    filtros = (
        panel["CONVOCATORIA"].isin(convocatorias)
        & panel["NIVEL_FORMACION"].eq(nivel_formacion)
        & panel["TIPO_MODALIDAD"].eq(modalidad)
        & panel["periodo_orden"].le(periodo_maximo)
        & panel["estado"].isin(estados)
    )
    panel = panel.loc[filtros].copy()

    numericas = [
        "periodo_orden",
        "distancia_ies",
        "sitp_cercanos",
        "tm_cercanos",
        "acceso_transporte",
        "pct_aprob_acum",
    ]
    for columna in numericas:
        panel[columna] = pd.to_numeric(panel[columna], errors="coerce")

    filtros = (
        panel["distancia_ies"].le(distancia_ies_maxima)
    )    

    panel = panel.loc[filtros].copy()
    
    return panel.dropna(subset=numericas + ["ID_PERSONA", "estado", "CONVOCATORIA"])


def filtrar_convocatoria(df: pd.DataFrame, convocatoria: str) -> pd.DataFrame:
    """Filtra el panel para una convocatoria especifica.

    Parameters
    ----------
    df : pandas.DataFrame
        Panel filtrado base.
    convocatoria : str
        Convocatoria a conservar.

    Returns
    -------
    pandas.DataFrame
        Subconjunto de la convocatoria.
    """

    return df.loc[df["CONVOCATORIA"].eq(convocatoria)].copy()


def ultima_observacion_por_estudiante(df: pd.DataFrame) -> pd.DataFrame:
    """Obtiene la ultima observacion disponible de cada estudiante.

    Parameters
    ----------
    df : pandas.DataFrame
        Panel filtrado de una convocatoria.

    Returns
    -------
    pandas.DataFrame
        Corte transversal a nivel estudiante.
    """

    ordenado = df.sort_values(["ID_PERSONA", "periodo_orden"])
    return ordenado.groupby("ID_PERSONA", as_index=False).tail(1).copy()


def resumen_general(df: pd.DataFrame) -> pd.DataFrame:
    """Construye un resumen general de estudiantes y estados.

    Parameters
    ----------
    df : pandas.DataFrame
        Panel filtrado de una convocatoria.

    Returns
    -------
    pandas.DataFrame
        Tabla con metricas generales.
    """

    ultimo = ultima_observacion_por_estudiante(df)
    registros = [
        ("Observaciones panel-periodo", len(df)),
        ("Estudiantes unicos", df["ID_PERSONA"].nunique()),
        ("Periodos observados", df["periodo_orden"].nunique()),
        ("Matriculados (ultimo periodo disponible)", (ultimo["estado"] == "Matriculado").sum()),
        ("Abandonos (ultimo periodo disponible)", (ultimo["estado"] == "Abandono").sum()),
    ]
    return pd.DataFrame(registros, columns=["indicador", "valor"])


def estudiantes_por_periodo(df: pd.DataFrame) -> pd.DataFrame:
    """Cuenta estudiantes y estados por periodo.

    Parameters
    ----------
    df : pandas.DataFrame
        Panel filtrado de una convocatoria.

    Returns
    -------
    pandas.DataFrame
        Tabla por periodo.
    """

    tabla = (
        df.pivot_table(
            index="periodo_orden",
            columns="estado",
            values="ID_PERSONA",
            aggfunc=pd.Series.nunique,
            fill_value=0,
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )
    tabla["total"] = tabla[[col for col in ESTADOS_ANALISIS if col in tabla]].sum(axis=1)
    return tabla


def estadisticos_descriptivos(
    df: pd.DataFrame,
    variables: Sequence[str] = tuple(VARIABLES_DESCRIPTIVAS),
) -> pd.DataFrame:
    """Calcula estadisticos descriptivos con percentiles relevantes.

    Parameters
    ----------
    df : pandas.DataFrame
        Datos de entrada.
    variables : sequence of str, default=VARIABLES_DESCRIPTIVAS
        Variables numericas a resumir.

    Returns
    -------
    pandas.DataFrame
        Tabla de estadisticos por variable.
    """

    percentiles = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
    resumen = (
        df[list(variables)]
        .describe(percentiles=percentiles)
        .T.rename(
            columns={
                "count": "n",
                "mean": "media",
                "50%": "mediana",
                "std": "desv_est",
                "min": "min",
                "max": "max",
            }
        )
    )
    columnas = [
        "n",
        "media",
        "mediana",
        "desv_est",
        "min",
        "1%",
        "5%",
        "10%",
        "25%",
        "75%",
        "90%",
        "95%",
        "99%",
        "max",
    ]
    return resumen[columnas].round(3)


def exportar_tabla(tabla: pd.DataFrame, ruta_salida: str | Path) -> Path:
    """Exporta una tabla a Excel.

    Parameters
    ----------
    tabla : pandas.DataFrame
        Tabla a guardar.
    ruta_salida : str or pathlib.Path
        Ruta del archivo de salida.

    Returns
    -------
    pathlib.Path
        Ruta del archivo guardado.
    """

    salida = Path(ruta_salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    tabla.to_excel(salida, index=True)
    return salida


def guardar_figura(fig: plt.Figure, ruta_salida: str | Path) -> Path:
    """Guarda una figura con fondo blanco y margenes ajustados.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        Figura a guardar.
    ruta_salida : str or pathlib.Path
        Ruta de salida.

    Returns
    -------
    pathlib.Path
        Ruta del archivo guardado.
    """

    salida = Path(ruta_salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(salida, bbox_inches="tight", facecolor="white")
    return salida


def plot_distribuciones(
    df: pd.DataFrame,
    convocatoria: str,
    figures_dir: str | Path,
    variables: Sequence[str] = tuple(VARIABLES_DESCRIPTIVAS),
) -> plt.Figure:
    """Grafica distribuciones compactas de variables clave.

    Parameters
    ----------
    df : pandas.DataFrame
        Datos de una convocatoria.
    convocatoria : str
        Nombre de la convocatoria.
    figures_dir : str or pathlib.Path
        Carpeta para guardar la figura.
    variables : sequence of str, default=VARIABLES_DESCRIPTIVAS
        Variables a visualizar.

    Returns
    -------
    matplotlib.figure.Figure
        Figura generada.
    """
    datos = ultima_observacion_por_estudiante(df)
    
    fig, axes = plt.subplots(2, 3, figsize=(14, 7.5))
    axes_flat = axes.ravel()

    for ax, variable in zip(axes_flat, variables):
        serie = _limitar_para_visualizacion(datos[variable])
        sns.histplot(serie, bins=32, kde=True, color="#6E93B3", edgecolor="white", ax=ax)
        ax.set_title(_label(variable), loc="left", fontsize=11)
        ax.set_xlabel(_label(variable))
        ax.set_ylabel("Frecuencia")

    axes_flat[-1].axis("off")
    _titulo_figura(
        fig,
        f"{convocatoria}: distribuciones de variables clave",
        "Valores extremos se recortan visualmente en p1-p99 para mejorar legibilidad; las tablas conservan los valores originales.",
    )
    guardar_figura(fig, Path(figures_dir) / f"{convocatoria.lower()}_distribuciones.png")
    return fig


def plot_comparacion_estado(
    df: pd.DataFrame,
    convocatoria: str,
    variable: str,
    figures_dir: str | Path,
    incluir_violin: bool = True,
) -> plt.Figure:
    """Compara una variable entre Matriculado y Abandono.

    Parameters
    ----------
    df : pandas.DataFrame
        Datos de una convocatoria.
    convocatoria : str
        Nombre de la convocatoria.
    variable : str
        Variable numerica a comparar.
    figures_dir : str or pathlib.Path
        Carpeta para guardar la figura.
    incluir_violin : bool, default=True
        Si es True incluye violin plot junto al boxplot.

    Returns
    -------
    matplotlib.figure.Figure
        Figura generada.
    """

    datos = ultima_observacion_por_estudiante(df)
    datos = datos.assign(valor_visual=_limitar_para_visualizacion(datos[variable]))

    ncols = 2 if incluir_violin else 1
    fig, axes = plt.subplots(1, ncols, figsize=(12, 4.8), squeeze=False)
    ax_box = axes[0, 0]

    sns.boxplot(
        data=datos,
        x="estado",
        y="valor_visual",
        order=ESTADOS_ANALISIS,
        palette=PALETA_ESTADO,
        width=0.55,
        fliersize=2,
        ax=ax_box,
    )
    ax_box.set_xlabel("")
    ax_box.set_ylabel(_label(variable))
    ax_box.set_title("Boxplot", loc="left", fontsize=11)

    if incluir_violin:
        ax_violin = axes[0, 1]
        sns.violinplot(
            data=datos,
            x="estado",
            y="valor_visual",
            order=ESTADOS_ANALISIS,
            palette=PALETA_ESTADO,
            inner="quartile",
            cut=0,
            linewidth=0.8,
            ax=ax_violin,
        )
        ax_violin.set_xlabel("")
        ax_violin.set_ylabel(_label(variable))
        ax_violin.set_title("Distribucion suavizada", loc="left", fontsize=11)

    _titulo_figura(
        fig,
        f"{convocatoria}: {_label(variable)} por estado final",
        "Corte a nivel estudiante usando la ultima observacion disponible <= periodo 4.",
    )
    guardar_figura(
        fig,
        Path(figures_dir) / f"{convocatoria.lower()}_{variable}_por_estado.png",
    )
    return fig


def plot_histograma_por_estado(
    df: pd.DataFrame,
    convocatoria: str,
    variable: str,
    figures_dir: str | Path,
) -> plt.Figure:
    """Grafica histogramas superpuestos por estado cuando aportan claridad.

    Parameters
    ----------
    df : pandas.DataFrame
        Datos de una convocatoria.
    convocatoria : str
        Nombre de la convocatoria.
    variable : str
        Variable numerica.
    figures_dir : str or pathlib.Path
        Carpeta para guardar la figura.

    Returns
    -------
    matplotlib.figure.Figure
        Figura generada.
    """

    datos = ultima_observacion_por_estudiante(df)
    datos = datos.assign(valor_visual=_limitar_para_visualizacion(datos[variable]))

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    sns.histplot(
        data=datos,
        x="valor_visual",
        hue="estado",
        hue_order=ESTADOS_ANALISIS,
        palette=PALETA_ESTADO,
        bins=32,
        stat="density",
        common_norm=False,
        alpha=0.35,
        edgecolor="white",
        ax=ax,
    )
    ax.set_xlabel(_label(variable))
    ax.set_ylabel("Densidad")
    _titulo_figura(
        fig,
        f"{convocatoria}: distribucion de {_label(variable)} por estado final",
        "Corte a nivel estudiante. Valores extremos recortados visualmente en p1-p99.",
    )
    guardar_figura(
        fig,
        Path(figures_dir) / f"{convocatoria.lower()}_{variable}_hist_estado.png",
    )
    return fig


def plot_curvas_promedio(
    df: pd.DataFrame,
    convocatoria: str,
    figures_dir: str | Path,
    periodo_grupo_maximo: int = 8,
) -> plt.Figure:
    """Grafica trayectorias promedio de desempeno por estado final temprano.

    Los grupos se definen por el estado observado en el ultimo periodo
    disponible menor o igual a ``periodo_grupo_maximo``.

    Parameters
    ----------
    df : pandas.DataFrame
        Datos de una convocatoria.
    convocatoria : str
        Nombre de la convocatoria.
    figures_dir : str or pathlib.Path
        Carpeta para guardar la figura.
    periodo_grupo_maximo : int, default=3
        Periodo maximo para definir el estado final del grupo.

    Returns
    -------
    matplotlib.figure.Figure
        Figura generada.
    """

    base = df.loc[df["periodo_orden"].le(periodo_grupo_maximo)].copy()
    grupos = (
        base.sort_values(["ID_PERSONA", "periodo_orden"])
        .groupby("ID_PERSONA", as_index=False)
        .tail(1)[["ID_PERSONA", "estado"]]
        .rename(columns={"estado": "estado_final_leq3"})
    )
    trayectorias = base.merge(grupos, on="ID_PERSONA", how="inner")
    promedio = (
        trayectorias.groupby(["periodo_orden", "estado_final_leq3"], as_index=False)
        .agg(
            pct_aprob_promedio=("pct_aprob_acum", "mean"),
            estudiantes=("ID_PERSONA", "nunique"),
        )
    )

    fig, ax = plt.subplots(figsize=(8.8, 5.2))
    sns.lineplot(
        data=promedio,
        x="periodo_orden",
        y="pct_aprob_promedio",
        hue="estado_final_leq3",
        hue_order=ESTADOS_ANALISIS,
        palette=PALETA_ESTADO,
        marker="o",
        linewidth=2.2,
        ax=ax,
    )
    ax.set_xlabel("Periodo")
    ax.set_ylabel("% creditos aprobados acumulados")
    ax.set_ylim(0, max(0.05, promedio["pct_aprob_promedio"].max() * 1.15))
    ax.legend(title="Estado final <= periodo 8")
    _titulo_figura(
        fig,
        f"{convocatoria}: curvas promedio de desempeno",
        "Promedio de pct_aprob_acum por periodo, agrupado segun el ultimo estado observado hasta periodo 3.",
    )
    guardar_figura(fig, Path(figures_dir) / f"{convocatoria.lower()}_curvas_promedio.png")
    return fig


def matriz_correlacion(
    df: pd.DataFrame,
    variables: Sequence[str] = tuple(VARIABLES_DESCRIPTIVAS),
) -> pd.DataFrame:
    """Calcula la matriz de correlacion de Pearson.

    Parameters
    ----------
    df : pandas.DataFrame
        Datos de entrada.
    variables : sequence of str, default=VARIABLES_DESCRIPTIVAS
        Variables numericas.

    Returns
    -------
    pandas.DataFrame
        Matriz de correlacion.
    """

    return df[list(variables)].corr().round(3)


def plot_matriz_correlacion(
    df: pd.DataFrame,
    convocatoria: str,
    figures_dir: str | Path,
    variables: Sequence[str] = tuple(VARIABLES_DESCRIPTIVAS),
) -> plt.Figure:
    """Grafica matriz de correlacion.

    Parameters
    ----------
    df : pandas.DataFrame
        Datos de una convocatoria.
    convocatoria : str
        Nombre de la convocatoria.
    figures_dir : str or pathlib.Path
        Carpeta para guardar la figura.
    variables : sequence of str, default=VARIABLES_DESCRIPTIVAS
        Variables a correlacionar.

    Returns
    -------
    matplotlib.figure.Figure
        Figura generada.
    """

    corr = matriz_correlacion(df, variables)
    fig, ax = plt.subplots(figsize=(7.2, 5.8))
    sns.heatmap(
        corr,
        annot=True,
        fmt=".2f",
        cmap=sns.light_palette("#2F6B9A", as_cmap=True),
        vmin=-1,
        vmax=1,
        center=0,
        linewidths=0.8,
        linecolor="white",
        cbar_kws={"label": "Correlacion"},
        ax=ax,
    )
    ax.set_xticklabels([_label(v) for v in corr.columns], rotation=35, ha="right")
    ax.set_yticklabels([_label(v) for v in corr.index], rotation=0)
    _titulo_figura(
        fig,
        f"{convocatoria}: matriz de correlacion",
        "Correlaciones descriptivas entre movilidad, transporte y desempeno.",
    )
    guardar_figura(fig, Path(figures_dir) / f"{convocatoria.lower()}_correlacion.png")
    return fig


def plot_relacion_bivariada(
    df: pd.DataFrame,
    convocatoria: str,
    x: str,
    y: str,
    figures_dir: str | Path,
    estado: str = "Matriculado",
) -> plt.Figure:
    """Grafica relacion bivariada con transparencia y tendencia suavizada.
    
    Parameters
    ----------
    df : pandas.DataFrame
        Datos de una convocatoria.
    convocatoria : str
        Nombre de la convocatoria.
    x : str
        Variable del eje x.
    y : str
        Variable del eje y.
    figures_dir : str or pathlib.Path
        Carpeta para guardar la figura.
    estado : str, default="Matriculado"
        Estado final a graficar. Opciones: ``"Matriculado"`` o ``"Abandono"``.
    
    Returns
    -------
    matplotlib.figure.Figure
        Figura generada.
    """

    estados_validos = ["Matriculado", "Abandono"]
    if estado not in estados_validos:
        raise ValueError(
            f"'estado' debe ser uno de {estados_validos}. Se recibió: {estado!r}"
        )

    datos = ultima_observacion_por_estudiante(df)
    datos = datos.loc[datos["estado"] == estado].copy()
    datos["x_visual"] = _limitar_para_visualizacion(datos[x])

    fig, ax = plt.subplots(figsize=(8.8, 5.4))
    sns.scatterplot(
        data=datos,
        x="x_visual",
        y=y,
        color=PALETA_ESTADO[estado],   # un solo color
        alpha=0.28,
        s=22,
        linewidth=0,
        ax=ax,
    )

    tendencia = _tendencia_por_bins(datos, "x_visual", y)
    sns.lineplot(
        data=tendencia,
        x="x_promedio",
        y="y_promedio",
        color="#222222",
        linewidth=2,
        marker="o",
        markersize=4,
        ax=ax,
    )

    ax.set_xlabel(_label(x))
    ax.set_ylabel(_label(y))
    # Ya no es necesaria la leyenda

    _titulo_figura(
        fig,
        f"{convocatoria}: {_label(x)} vs {_label(y)} ({estado})",
        "Corte a nivel estudiante. La línea negra resume promedios por bins de la variable explicativa.",
    )

    guardar_figura(
        fig,
        Path(figures_dir)
        / f"{convocatoria.lower()}_{estado.lower()}_{x}_vs_{y}.png",
    )

    return fig


def resumen_quintiles(
    df: pd.DataFrame,
    variable: str,
    n_quintiles: int = 5,
) -> pd.DataFrame:
    """Resume desempeno y abandono por quintiles de una variable.

    Parameters
    ----------
    df : pandas.DataFrame
        Datos de una convocatoria.
    variable : str
        Variable usada para construir quintiles.
    n_quintiles : int, default=5
        Numero de grupos cuantiles.

    Returns
    -------
    pandas.DataFrame
        Resumen por quintil a nivel estudiante.
    """

    datos = ultima_observacion_por_estudiante(df).copy()
    datos["quintil"] = _crear_quintiles(datos[variable], n_quintiles)
    resumen = (
        datos.dropna(subset=["quintil"])
        .groupby("quintil", observed=True)
        .agg(
            estudiantes=("ID_PERSONA", "nunique"),
            valor_min=(variable, "min"),
            valor_max=(variable, "max"),
            pct_aprob_promedio=("pct_aprob_acum", "mean"),
            tasa_abandono=("estado", lambda serie: (serie == "Abandono").mean()),
        )
        .reset_index()
    )
    resumen["quintil"] = resumen["quintil"].astype(str)
    return resumen.round(4)


def plot_quintiles(
    resumen: pd.DataFrame,
    convocatoria: str,
    variable: str,
    figures_dir: str | Path,
) -> plt.Figure:
    """Grafica desempeno promedio y abandono por quintiles.

    Parameters
    ----------
    resumen : pandas.DataFrame
        Tabla generada por ``resumen_quintiles``.
    convocatoria : str
        Nombre de la convocatoria.
    variable : str
        Variable usada para quintiles.
    figures_dir : str or pathlib.Path
        Carpeta para guardar la figura.

    Returns
    -------
    matplotlib.figure.Figure
        Figura generada.
    """

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharex=True)
    sns.barplot(
        data=resumen,
        x="quintil",
        y="pct_aprob_promedio",
        color="#6E93B3",
        ax=axes[0],
    )
    axes[0].set_title("Desempeno promedio", loc="left", fontsize=11)
    axes[0].set_xlabel(f"Quintil de {_label(variable)}")
    axes[0].set_ylabel("% aprobacion acumulada promedio")

    sns.barplot(
        data=resumen,
        x="quintil",
        y="tasa_abandono",
        color="#B85C5C",
        ax=axes[1],
    )
    axes[1].set_title("Porcentaje de abandono", loc="left", fontsize=11)
    axes[1].set_xlabel(f"Quintil de {_label(variable)}")
    axes[1].set_ylabel("Tasa de abandono")
    axes[1].set_ylim(0, max(0.05, resumen["tasa_abandono"].max() * 1.2))

    _titulo_figura(
        fig,
        f"{convocatoria}: resultados por quintiles de {_label(variable)}",
        "Corte a nivel estudiante usando la ultima observacion disponible <= periodo 8.",
    )
    guardar_figura(fig, Path(figures_dir) / f"{convocatoria.lower()}_{variable}_quintiles.png")
    return fig


def tasa_abandono_acumulada_por_quintil(
    df: pd.DataFrame,
    variable: str,
    n_quintiles: int = 5,
) -> pd.DataFrame:
    """Calcula tasa acumulada de abandono por periodo y quintil.

    Parameters
    ----------
    df : pandas.DataFrame
        Datos de una convocatoria.
    variable : str
        Variable usada para construir quintiles a nivel estudiante.
    n_quintiles : int, default=5
        Numero de grupos cuantiles.

    Returns
    -------
    pandas.DataFrame
        Tasa acumulada de abandono por periodo y quintil.
    """

    base_estudiante = ultima_observacion_por_estudiante(df)[["ID_PERSONA", variable]].copy()
    base_estudiante["quintil"] = _crear_quintiles(base_estudiante[variable], n_quintiles)
    panel = df.merge(base_estudiante[["ID_PERSONA", "quintil"]], on="ID_PERSONA", how="inner")
    primer_abandono = (
        panel.loc[panel["estado"].eq("Abandono")]
        .groupby("ID_PERSONA", as_index=False)["periodo_orden"]
        .min()
        .rename(columns={"periodo_orden": "periodo_abandono"})
    )
    estudiantes = base_estudiante.merge(primer_abandono, on="ID_PERSONA", how="left")
    periodos = sorted(panel["periodo_orden"].dropna().unique())

    registros = []
    for quintil, grupo in estudiantes.dropna(subset=["quintil"]).groupby("quintil", observed=True):
        total = grupo["ID_PERSONA"].nunique()
        for periodo in periodos:
            abandonos = grupo["periodo_abandono"].le(periodo).sum()
            registros.append(
                {
                    "quintil": str(quintil),
                    "periodo_orden": periodo,
                    "estudiantes": total,
                    "abandono_acumulado": abandonos / total if total else np.nan,
                }
            )
    return pd.DataFrame(registros)


def plot_tasa_abandono_acumulada(
    tabla: pd.DataFrame,
    convocatoria: str,
    variable: str,
    figures_dir: str | Path,
) -> plt.Figure:
    """Grafica tasa acumulada de abandono por quintil.

    Parameters
    ----------
    tabla : pandas.DataFrame
        Tabla generada por ``tasa_abandono_acumulada_por_quintil``.
    convocatoria : str
        Nombre de la convocatoria.
    variable : str
        Variable usada para quintiles.
    figures_dir : str or pathlib.Path
        Carpeta para guardar la figura.

    Returns
    -------
    matplotlib.figure.Figure
        Figura generada.
    """

    fig, ax = plt.subplots(figsize=(8.8, 5.2))
    sns.lineplot(
        data=tabla,
        x="periodo_orden",
        y="abandono_acumulado",
        hue="quintil",
        palette=sns.color_palette(PALETA_COMPLEMENTARIOS, n_colors=tabla["quintil"].nunique()),
        marker="o",
        linewidth=2,
        ax=ax,
    )
    ax.set_xlabel("Periodo")
    ax.set_ylabel("Tasa acumulada de abandono")
    
    conteos = (
        tabla.groupby("quintil")["estudiantes"]
        .first()
        .to_dict()
    )    
    
    handles, labels = ax.get_legend_handles_labels()
    
    labels = [f"{label} (n={conteos[label]})" for label in labels]
    
    ax.legend(
        handles,
        labels,
        title=f"Quintil de {_label(variable)}",
        ncol=1,
    )    
    _titulo_figura(
        fig,
        f"{convocatoria}: abandono acumulado por quintiles de {_label(variable)}",
        f"Permite observar si existe un gradiente descriptivo entre movilidad y abandono",
    )
    guardar_figura(
        fig,
        Path(figures_dir) / f"{convocatoria.lower()}_{variable}_abandono_acumulado.png",
    )
    return fig


def generar_conclusiones(
    df: pd.DataFrame,
    convocatoria: str,
) -> str:
    """Genera un resumen ejecutivo descriptivo para una convocatoria.

    Parameters
    ----------
    df : pandas.DataFrame
        Datos de una convocatoria.
    convocatoria : str
        Nombre de la convocatoria.

    Returns
    -------
    str
        Texto en Markdown con hallazgos descriptivos.
    """

    ultimo = ultima_observacion_por_estudiante(df)
    resumen_dist = _comparacion_media_por_estado(ultimo, "distancia_ies")
    resumen_acc = _comparacion_media_por_estado(ultimo, "acceso_transporte")
    resumen_perf = _comparacion_media_por_estado(ultimo, "pct_aprob_acum")

    corr = matriz_correlacion(ultimo)
    corr_dist = corr.loc["distancia_ies", "pct_aprob_acum"]
    corr_acc = corr.loc["acceso_transporte", "pct_aprob_acum"]

    q_dist = resumen_quintiles(df, "distancia_ies")
    q_acc = resumen_quintiles(df, "acceso_transporte")
    grad_dist = q_dist["tasa_abandono"].iloc[-1] - q_dist["tasa_abandono"].iloc[0]
    grad_acc = q_acc["tasa_abandono"].iloc[-1] - q_acc["tasa_abandono"].iloc[0]

    texto = f"""
### Conclusiones descriptivas - {convocatoria}

- La muestra filtrada contiene **{ultimo['ID_PERSONA'].nunique():,} estudiantes** con ultima observacion disponible hasta el periodo 4.
- En el corte final, la distancia promedio a la IES es de **{resumen_dist['Matriculado']:,.0f} m** para Matriculado y **{resumen_dist['Abandono']:,.0f} m** para Abandono.
- El acceso promedio al transporte es de **{resumen_acc['Matriculado']:.1f} puntos cercanos** para Matriculado y **{resumen_acc['Abandono']:.1f}** para Abandono.
- El desempeno promedio acumulado es de **{resumen_perf['Matriculado']:.3f}** para Matriculado y **{resumen_perf['Abandono']:.3f}** para Abandono.
- La correlacion descriptiva entre distancia a la IES y desempeno es **{corr_dist:.3f}**; entre acceso al transporte y desempeno es **{corr_acc:.3f}**.
- Entre el quintil mas bajo y mas alto de distancia, la tasa de abandono cambia en **{grad_dist:.2%}**. Entre el quintil mas bajo y mas alto de acceso al transporte, cambia en **{grad_acc:.2%}**.
- Estos patrones son asociaciones descriptivas. No deben interpretarse como efectos causales, pero si ayudan a priorizar especificaciones y controles para el analisis econometrico posterior.
"""
    return texto.strip()


def guardar_texto(texto: str, ruta_salida: str | Path) -> Path:
    """Guarda texto plano o Markdown.

    Parameters
    ----------
    texto : str
        Texto a guardar.
    ruta_salida : str or pathlib.Path
        Ruta de salida.

    Returns
    -------
    pathlib.Path
        Ruta guardada.
    """

    salida = Path(ruta_salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(texto, encoding="utf-8")
    return salida


def exportar_tablas_convocatoria(
    df: pd.DataFrame,
    convocatoria: str,
    outputs_dir: str | Path,
) -> dict[str, Path]:
    """Exporta tablas principales del EDA para una convocatoria.

    Parameters
    ----------
    df : pandas.DataFrame
        Datos de una convocatoria.
    convocatoria : str
        Nombre de la convocatoria.
    outputs_dir : str or pathlib.Path
        Carpeta de salida.

    Returns
    -------
    dict[str, pathlib.Path]
        Rutas de tablas exportadas.
    """

    out = Path(outputs_dir)
    rutas = {
        "resumen_general": exportar_tabla(
            resumen_general(df), out / f"{convocatoria.lower()}_resumen_general.xlsx"
        ),
        "estudiantes_periodo": exportar_tabla(
            estudiantes_por_periodo(df),
            out / f"{convocatoria.lower()}_estudiantes_por_periodo.xlsx",
        ),
        "estadisticos": exportar_tabla(
            estadisticos_descriptivos(df),
            out / f"{convocatoria.lower()}_estadisticos_descriptivos.xlsx",
        ),
        "correlacion": exportar_tabla(
            matriz_correlacion(ultima_observacion_por_estudiante(df)),
            out / f"{convocatoria.lower()}_correlacion.xlsx",
        ),
    }
    for variable in ("distancia_ies", "acceso_transporte"):
        rutas[f"quintiles_{variable}"] = exportar_tabla(
            resumen_quintiles(df, variable),
            out / f"{convocatoria.lower()}_{variable}_quintiles.xlsx",
        )
        rutas[f"abandono_acumulado_{variable}"] = exportar_tabla(
            tasa_abandono_acumulada_por_quintil(df, variable),
            out / f"{convocatoria.lower()}_{variable}_abandono_acumulado.xlsx",
        )
    return rutas


def interpretar_correlaciones(corr: pd.DataFrame) -> str:
    """Produce una lectura breve de la matriz de correlacion.

    Parameters
    ----------
    corr : pandas.DataFrame
        Matriz de correlacion.

    Returns
    -------
    str
        Interpretacion descriptiva breve.
    """

    pares = [
        ("distancia_ies", "pct_aprob_acum"),
        ("sitp_cercanos", "pct_aprob_acum"),
        ("tm_cercanos", "pct_aprob_acum"),
        ("acceso_transporte", "pct_aprob_acum"),
    ]
    frases = []
    for x, y in pares:
        valor = corr.loc[x, y]
        intensidad = "de magnitud baja"
        if abs(valor) >= 0.30:
            intensidad = "de magnitud moderada"
        if abs(valor) >= 0.60:
            intensidad = "de magnitud alta"
        direccion = "positiva" if valor > 0 else "negativa" if valor < 0 else "nula"
        frases.append(f"- {_label(x)} y {_label(y)} muestran una asociacion {direccion} {intensidad} (r = {valor:.3f}).")
    return "\n".join(frases)


def _limitar_para_visualizacion(serie: pd.Series, p_inf: float = 0.01, p_sup: float = 0.99) -> pd.Series:
    limites = serie.quantile([p_inf, p_sup])
    return serie.clip(lower=limites.iloc[0], upper=limites.iloc[1])


def _titulo_figura(fig: plt.Figure, titulo: str, subtitulo: str | None = None) -> None:
    fig.suptitle(titulo, x=0.01, y=1.03, ha="left", fontsize=14, fontweight="bold")
    if subtitulo:
        fig.text(0.01, 0.985, subtitulo, ha="left", va="top", fontsize=10, color="#555555")
    fig.tight_layout()


def _label(variable: str) -> str:
    etiquetas = {
        "distancia_ies": "Distancia a la IES (m)",
        "sitp_cercanos": "Paraderos SITP cercanos",
        "tm_cercanos": "Estaciones TM cercanas",
        "acceso_transporte": "Acceso al transporte",
        "pct_aprob_acum": "% aprobacion acumulada",
    }
    return etiquetas.get(variable, variable)


def _crear_quintiles(serie: pd.Series, n_quintiles: int) -> pd.Series:
    try:
        return pd.qcut(
            serie,
            q=n_quintiles,
            labels=[f"Q{i}" for i in range(1, n_quintiles + 1)],
            duplicates="drop",
        )
    except ValueError:
        return pd.Series(pd.NA, index=serie.index, dtype="object")


def _comparacion_media_por_estado(df: pd.DataFrame, variable: str) -> dict[str, float]:
    medias = df.groupby("estado")[variable].mean()
    return {estado: float(medias.get(estado, np.nan)) for estado in ESTADOS_ANALISIS}


def _tendencia_por_bins(
    df: pd.DataFrame,
    x: str,
    y: str,
    n_bins: int = 20,
) -> pd.DataFrame:
    datos = df[[x, y]].dropna().copy()
    datos["bin"] = pd.qcut(datos[x], q=n_bins, duplicates="drop")
    return (
        datos.groupby("bin", observed=True)
        .agg(x_promedio=(x, "mean"), y_promedio=(y, "mean"))
        .reset_index(drop=True)
    )
