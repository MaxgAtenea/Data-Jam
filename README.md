## Problema

En Bogotá, existen diferencias en la accesibilidad física de los estudiantes de programas presenciales a las instituciones de educación superior. Estas diferencias podrían estar asociadas con menores niveles de rendimiento académico y una mayor probabilidad de abandono durante los primeros semestres académicos, limitando la formación de capital humano y el retorno social de la inversión educativa. 

Este proyecto explora si la distancia entre el domicilio del estudiante y su institución educativa, así como la accesibilidad al sistema de transporte público, presentan asociaciones con indicadores de desempeño académico. El objetivo es aportar evidencia descriptiva que contribuya a comprender posibles barreras geográficas para la permanencia estudiantil y la formación de capital humano.

---

## Fuentes de datos utilizadas

* **Instituciones de Educación Superior (IES):** https://datosabiertos.bogota.gov.co/dataset/institucion-de-educacion-superior
* **Paraderos del componente zonal (SITP):** https://datosabiertos.bogota.gov.co/dataset/informacion-general-rutas-componente-troncal-del-sitp
* **Estaciones troncales de TransMilenio:** https://datosabiertos.bogota.gov.co/dataset/estaciones-troncales-de-transmilenio
* **Rutas troncales de TransMilenio:** https://datosabiertos-transmilenio.hub.arcgis.com/documents/d006e92936824698a49ba44558cd8162/about
* **Base administrativa de beneficiarios de Atenea**, que contiene información académica y geográfica anonimizada de los estudiantes.

---

## Metodología

El proyecto realiza un análisis espacial y descriptivo para explorar la relación entre la accesibilidad geográfica y el desempeño académico de estudiantes universitarios en modalidad presencial.

Las principales actividades desarrolladas son:

* Calcular la distancia euclidiana entre el domicilio del estudiante y la Institución de Educación Superior (IES).
* Calcular el número de estaciones de TransMilenio y paraderos del SITP ubicados dentro de un radio de 800 metros alrededor del domicilio del estudiante como una aproximación a la accesibilidad al transporte público.
* Agregar indicadores espaciales a nivel de Unidad de Planeamiento Local (UPL), incluyendo distancia promedio a la IES, acceso al transporte público, tasas de abandono y porcentaje promedio de avance académico.
* Construir visualizaciones interactivas para explorar la distribución espacial de estos indicadores.
* Calcular estadísticas descriptivas y analizar la relación entre las variables de accesibilidad (distancia y transporte) y las variables de desempeño académico (abandono y porcentaje acumulado de créditos aprobados).

Actualmente las distancias se calculan utilizando la distancia euclidiana como una aproximación simplificada de la separación espacial entre los puntos.

Como trabajo futuro se propone incorporar medidas más realistas de accesibilidad mediante el cálculo de:

* Tiempo estimado de desplazamiento en transporte público.
* Distancia recorrida sobre la red vial y de transporte público.

---

## Estructura del repositorio

* **src/**: código fuente del proyecto, incluyendo scripts y notebooks de análisis.
* **data/**: datos requeridos para la ejecución. Solo se incluyen los paraderos del SITP, ya que el resto de la información pública se consulta directamente mediante servicios REST. Los archivos administrativos de Atenea no se distribuyen debido a restricciones de tamaño y confidencialidad.
* **figures/**: figuras generadas durante el análisis descriptivo.
* **outputs/**: tablas, archivos HTML, mapas y demás resultados generados por el proyecto.

---

## Instrucciones de ejecución

* **src/analisis_descriptivo.ipynb**: ejecuta el análisis exploratorio, las estadísticas descriptivas y las visualizaciones utilizadas en el estudio.
* **src/spatial_analysis.py**: genera el visor geográfico interactivo con indicadores agregados por UPL, así como una muestra anonimizada de los domicilios de los estudiantes (mediante desplazamiento aleatorio de las ubicaciones), las Instituciones de Educación Superior (IES), los paraderos del SITP y las estaciones de TransMilenio.
