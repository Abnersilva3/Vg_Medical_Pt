# Smart OCR - Extractor Médico

¿Qué es esto?

Este es un sistema que desarrollé para automatizar la extracción de información de documentos médicos quirúrgicos. 

¿Por qué OCR?

Decidí usar OCR (Reconocimiento Óptico de Caracteres) porque la mayoría de documentos médicos llegan como imágenes escaneadas o fotografías. En lugar de transcribir manualmente cada documento, el sistema puede "leer" automáticamente el texto de las imágenes y extraer la información estructurada que necesitamos.

Elegí **OCR.space** como proveedor porque:
- Tiene una API sencilla de usar
- Maneja bien documentos en español
- Ofrece un plan gratuito para empezar
- Es confiable para documentos médicos

## ¿Por qué el archivo .env?

El archivo `.env` almacena la clave de la API de OCR.space de forma segura. Es una práctica común en desarrollo no hardcodear claves API directamente en el código por seguridad. Así, cada persona puede usar su propia clave sin modificar el código fuente.

## ¿Cómo ejecutar el programa?

Es súper simple. Solo necesitas ejecutar:

```bash
python3 main.py
```

Y ya está. El programa automáticamente:
1. Verifica si tienes todo instalado
2. Te pide la clave de API (o puedes usar la de ejemplo)
3. Instala las librerías que falten
4. Abre la interfaz web en tu navegador

No necesitas saber nada técnico. El sistema se configura solo.

## Tipos de documentos que maneja

El sistema está diseñado para procesar tres tipos específicos de documentos médicos:

### Tipo 1: Reporte de Gasto Quirúrgico (Interno)
Este es el documento más completo. Incluye toda la información de trazabilidad de los insumos:
- Datos del paciente y procedimiento
- Lista detallada de insumos con cantidades
- Códigos REF y LOT de cada insumo
- Fechas de vencimiento
- Presencia de etiquetas de trazabilidad

### Tipo 2: Reporte de Gasto Quirúrgico (Hospital)
Versión simplificada del reporte interno:
- Información básica del paciente y procedimiento
- Lista de insumos pero sin códigos de trazabilidad
- Datos administrativos del hospital

### Tipo 3: Descripción Quirúrgica (Doctor)
El relato médico del procedimiento:
- Descripción narrativa detallada
- Insumos mencionados en el texto
- Información clínica complementaria

## Lo mejor del sistema: Análisis de Discrepancias

Cuando subes documentos de los tres tipos del mismo procedimiento, el sistema automáticamente:

- **Compara las fechas** entre documentos
- **Verifica que el paciente sea el mismo** (con tolerancia a variaciones de escritura)
- **Analiza si los procedimientos coinciden**
- **Compara las listas de insumos** (normalizando sinónimos)
- **Evalúa la completitud de la trazabilidad**

Te muestra un resumen con alertas:
- **ALTA:** Discrepancias críticas que requieren revisión urgente
- **MEDIA:** Diferencias que podrían necesitar verificación
- ℹ**BAJA:** Variaciones menores normales

## Capacidades actuales y futuras

**Actualmente procesa:**
- Imágenes PNG, JPG, JPEG
- Archivos PDF (se convierten automáticamente a imagen)

**En el futuro se podría implementar:**
- Procesamiento nativo de PDF con mejor calidad
- Reconocimiento de tablas complejas
- Integración con sistemas hospitalarios
- Exportación a formatos ERP/HIS
- Análisis de firmas digitales
- Reconocimiento de códigos de barras en etiquetas

## Arquitectura técnica (para los curiosos)

Diseñé el sistema siguiendo principios SOLID para que sea fácil de mantener y extender:

- **Modular:** Cada tipo de documento tiene su propio extractor
- **Extensible:** Agregar nuevos tipos es sencillo
- **Testeable:** Cada componente se puede probar independientemente
- **Configurable:** Todo se maneja a través de archivos de configuración

Uso **Pydantic** para validar que los datos extraídos tengan el formato correcto, y **Streamlit** para la interfaz web porque es rápido de desarrollar y fácil de usar.

## Instalación y requisitos

### Lo que necesitas:
- Python 3.8 o superior
- Conexión a internet (para la API de OCR)
- Una clave de API de OCR.space (gratuita)

### Instalación automática:
```bash
python3 main.py
```

El programa se instala solo. Si algo falla, puedes forzar la reinstalación con:
```bash
python3 main.py install
```

## Comandos disponibles

```bash
python3 main.py          # Instalación automática e inicio
python3 main.py start    # Solo iniciar (si ya está instalado)
python3 main.py status   # Verificar que todo esté OK
python3 main.py help     # Ver ayuda completa
python3 main.py install  # Reinstalar dependencias
```

## Dependencias del proyecto

```
streamlit     # Interfaz web interactiva
pandas        # Manejo de datos y tablas
requests      # Comunicación con API de OCR
pydantic      # Validación de modelos de datos
python-dotenv # Manejo de archivo .env
openpyxl      # Exportación a Excel
```

Todo lo demás son librerías estándar de Python.

## Obtener clave de OCR.space

1. Ve a [ocr.space](https://ocr.space/ocrapi)
2. Regístrate gratis
3. Copia tu API key
4. Pégala cuando el programa te la pida

O simplemente usa la clave de ejemplo que viene incluida para probar.

## Estructura del proyecto

```
smart-ocr-medico/
├── main.py                       # Script principal - ejecuta esto
├── interfaz_ocr.py              # Interfaz web con Streamlit
├── smart_ocr.py                 # Motor de extracción OCR
├── analizador_discrepancias.py  # Análisis independiente (opcional)
├── requirements.txt             # Lista de dependencias
├── .env                         # Tu clave de API (se crea automáticamente)
├── README.md                    # Este archivo
└── venv/                        # Entorno virtual (se crea automáticamente)
```

## Flujo de uso típico

1. **Ejecuta** `python3 main.py`
2. **Abre** http://localhost:8501 en tu navegador
3. **Sube** tus imágenes de documentos médicos
4. **Selecciona** el tipo de cada documento
5. **Presiona** "Procesar Todos los Documentos"
6. **Revisa** los resultados y el análisis de discrepancias
7. **Descarga** los resultados en JSON si los necesitas

## Casos de uso

- **Auditorías médicas:** Verificar consistencia entre documentos
- **Control de inventario:** Rastrear uso de insumos quirúrgicos
- **Facturación:** Validar consumos reportados
- **Investigación:** Analizar patrones en procedimientos quirúrgicos
- **Calidad:** Detectar inconsistencias en la documentación

## Limitaciones actuales

- **Calidad de imagen:** Necesita imágenes legibles
- **Idioma:** Optimizado para español (aunque soporta inglés)
- **Formato:** Funciona mejor con documentos estructurados
- **Internet:** Requiere conexión para OCR.space
- **Velocidad:** Depende de la velocidad de la API

