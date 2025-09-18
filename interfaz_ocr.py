import streamlit as st
import tempfile
import json
import os
from pathlib import Path
import pandas as pd
from smart_ocr import SmartOCRProcessor, OCRSpaceClient, load_api_key
import re
import difflib
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

@dataclass
class DiscrepanciaItem:
    campo: str
    tipo_anexo1: str
    tipo_anexo2: str
    tipo_anexo3: str
    coincide: bool
    observaciones: str
    criticidad: str

class AnalizadorDiscrepancias:
    def __init__(self):
        self.sinonimos_insumos = {
            'cateter': ['cateter', 'sonda', 'tubo'],
            'gasa': ['gasa', 'compresa', 'gasas'],
            'sutura': ['sutura', 'hilo', 'punto'],
            'bisturi': ['bisturi', 'cuchilla', 'escalpelo'],
            'aguja': ['aguja', 'inyector', 'puncion']
        }
        
        self.patrones_fecha = [
            r'\d{1,2}/\d{1,2}/\d{4}',
            r'\d{1,2}-\d{1,2}-\d{4}',
            r'\d{4}/\d{1,2}/\d{1,2}',
            r'\d{4}-\d{1,2}-\d{1,2}'
        ]
    
    def normalizar_texto(self, texto: str) -> str:
        if not texto:
            return ""
        return re.sub(r'\s+', ' ', texto.lower().strip())
    
    def extraer_fecha_texto(self, texto: str) -> Optional[str]:
        texto_normalizado = self.normalizar_texto(texto)
        for patron in self.patrones_fecha:
            match = re.search(patron, texto_normalizado)
            if match:
                return match.group()
        return None
    
    def comparar_fechas(self, fecha1: str, fecha2: str, fecha3: str) -> Tuple[bool, str]:
        fechas = [
            self.extraer_fecha_texto(fecha1) if fecha1 else None,
            self.extraer_fecha_texto(fecha2) if fecha2 else None,
            self.extraer_fecha_texto(fecha3) if fecha3 else None
        ]
        
        fechas_validas = [f for f in fechas if f]
        
        if len(fechas_validas) == 0:
            return False, "No se encontraron fechas válidas"
        
        if len(set(fechas_validas)) == 1:
            return True, f"Todas las fechas coinciden"
        
        return False, f"Fechas diferentes: {', '.join(set(fechas_validas))}"
    
    def comparar_nombres(self, nombre1: str, nombre2: str, nombre3: str) -> Tuple[bool, str]:
        nombres = [
            self.normalizar_texto(nombre1) if nombre1 else "",
            self.normalizar_texto(nombre2) if nombre2 else "",
            self.normalizar_texto(nombre3) if nombre3 else ""
        ]
        
        nombres_validos = [n for n in nombres if n and n != "n/a"]
        
        if len(nombres_validos) == 0:
            return False, "No se encontraron nombres válidos"
        
        similitudes = []
        for i in range(len(nombres_validos)):
            for j in range(i+1, len(nombres_validos)):
                ratio = difflib.SequenceMatcher(None, nombres_validos[i], nombres_validos[j]).ratio()
                similitudes.append(ratio)
        
        if not similitudes:
            return True, f"Solo un nombre disponible"
        
        promedio_similitud = sum(similitudes) / len(similitudes)
        
        if promedio_similitud >= 0.8:
            return True, f"Nombres similares (similitud: {promedio_similitud:.2f})"
        
        return False, f"Nombres diferentes (similitud: {promedio_similitud:.2f})"
    
    def normalizar_insumo(self, nombre_insumo: str) -> str:
        nombre_norm = self.normalizar_texto(nombre_insumo)
        
        for base, variantes in self.sinonimos_insumos.items():
            for variante in variantes:
                if variante in nombre_norm:
                    return base
        
        return nombre_norm
    
    def comparar_insumos(self, insumos1: List[Dict], insumos2: List[Dict], insumos3: List[Dict]) -> Tuple[bool, str]:
        def extraer_nombres_cantidades(insumos):
            if not insumos:
                return {}
            
            result = {}
            for insumo in insumos:
                nombre = self.normalizar_insumo(insumo.get('nombre', ''))
                cantidad = insumo.get('cantidad', 'N/A')
                if nombre:
                    result[nombre] = cantidad
            return result
        
        ins1 = extraer_nombres_cantidades(insumos1)
        ins2 = extraer_nombres_cantidades(insumos2)
        ins3 = extraer_nombres_cantidades(insumos3)
        
        todos_insumos = set(ins1.keys()) | set(ins2.keys()) | set(ins3.keys())
        
        if not todos_insumos:
            return False, "No se encontraron insumos"
        
        discrepancias = []
        
        for insumo in todos_insumos:
            cant1 = ins1.get(insumo, 'Ausente')
            cant2 = ins2.get(insumo, 'Ausente')
            cant3 = ins3.get(insumo, 'Ausente')
            
            cantidades_presentes = [c for c in [cant1, cant2, cant3] if c != 'Ausente']
            
            if len(set(cantidades_presentes)) > 1:
                discrepancias.append(f"{insumo}: T1:{cant1}, T2:{cant2}, T3:{cant3}")
        
        if not discrepancias:
            return True, f"Insumos coinciden ({len(todos_insumos)} items)"
        
        return False, f"Discrepancias en {len(discrepancias)} insumos"
    
    def analizar_trazabilidad(self, resultado_tipo1: Dict) -> Tuple[bool, str]:
        if not resultado_tipo1:
            return False, "No hay datos del Tipo 1"
        
        trazabilidad = resultado_tipo1.get('etiquetas_trazabilidad', {})
        
        if not trazabilidad:
            return False, "Sin datos de trazabilidad"
        
        elementos = {
            'referencias': trazabilidad.get('tiene_referencias', False),
            'lotes': trazabilidad.get('tiene_lotes', False),
            'udi': trazabilidad.get('tiene_udi', False),
            'fechas_venc': trazabilidad.get('tiene_fechas_vencimiento', False)
        }
        
        presentes = [k for k, v in elementos.items() if v]
        
        if len(presentes) >= 3:
            return True, f"Trazabilidad completa: {', '.join(presentes)}"
        elif len(presentes) >= 1:
            return False, f"Trazabilidad parcial: {', '.join(presentes)}"
        else:
            return False, "Sin trazabilidad"
    
    def procesar_resultados(self, resultado_tipo1: Dict, resultado_tipo2: Dict, resultado_tipo3: Dict) -> List[DiscrepanciaItem]:
        discrepancias = []
        
        fecha_coincide, fecha_obs = self.comparar_fechas(
            resultado_tipo1.get('fecha_reporte', ''),
            resultado_tipo2.get('fecha_reporte', ''),
            resultado_tipo3.get('fecha_reporte', '')
        )
        
        discrepancias.append(DiscrepanciaItem(
            campo="Fecha de cirugía/reporte",
            tipo_anexo1=resultado_tipo1.get('fecha_reporte', 'N/A'),
            tipo_anexo2=resultado_tipo2.get('fecha_reporte', 'N/A'),
            tipo_anexo3=resultado_tipo3.get('fecha_reporte', 'N/A'),
            coincide=fecha_coincide,
            observaciones=fecha_obs,
            criticidad="ALTA" if not fecha_coincide else "BAJA"
        ))
        
        paciente_coincide, paciente_obs = self.comparar_nombres(
            resultado_tipo1.get('nombre_paciente', ''),
            resultado_tipo2.get('nombre_paciente', ''),
            resultado_tipo3.get('nombre_paciente', '')
        )
        
        discrepancias.append(DiscrepanciaItem(
            campo="Datos del paciente",
            tipo_anexo1=resultado_tipo1.get('nombre_paciente', 'N/A'),
            tipo_anexo2=resultado_tipo2.get('nombre_paciente', 'N/A'),
            tipo_anexo3=resultado_tipo3.get('nombre_paciente', 'N/A'),
            coincide=paciente_coincide,
            observaciones=paciente_obs,
            criticidad="ALTA" if not paciente_coincide else "BAJA"
        ))
        
        proc_coincide, proc_obs = self.comparar_nombres(
            resultado_tipo1.get('datos_procedimiento', ''),
            resultado_tipo2.get('datos_procedimiento', ''),
            resultado_tipo3.get('datos_procedimiento', '')
        )
        
        discrepancias.append(DiscrepanciaItem(
            campo="Datos del procedimiento",
            tipo_anexo1=resultado_tipo1.get('datos_procedimiento', 'N/A')[:30] + '...' if len(resultado_tipo1.get('datos_procedimiento', '')) > 30 else resultado_tipo1.get('datos_procedimiento', 'N/A'),
            tipo_anexo2=resultado_tipo2.get('datos_procedimiento', 'N/A')[:30] + '...' if len(resultado_tipo2.get('datos_procedimiento', '')) > 30 else resultado_tipo2.get('datos_procedimiento', 'N/A'),
            tipo_anexo3=resultado_tipo3.get('datos_procedimiento', 'N/A')[:30] + '...' if len(resultado_tipo3.get('datos_procedimiento', '')) > 30 else resultado_tipo3.get('datos_procedimiento', 'N/A'),
            coincide=proc_coincide,
            observaciones=proc_obs,
            criticidad="MEDIA" if not proc_coincide else "BAJA"
        ))
        
        medico_coincide, medico_obs = self.comparar_nombres(
            resultado_tipo1.get('medico_responsable', ''),
            resultado_tipo2.get('cirujano', ''),
            resultado_tipo3.get('medico_responsable', '')
        )
        
        discrepancias.append(DiscrepanciaItem(
            campo="Médico responsable",
            tipo_anexo1=resultado_tipo1.get('medico_responsable', 'N/A'),
            tipo_anexo2=resultado_tipo2.get('cirujano', 'N/A'),
            tipo_anexo3=resultado_tipo3.get('medico_responsable', 'N/A'),
            coincide=medico_coincide,
            observaciones=medico_obs,
            criticidad="MEDIA" if not medico_coincide else "BAJA"
        ))
        
        lugar_coincide, lugar_obs = self.comparar_nombres(
            resultado_tipo1.get('ciudad_lugar', ''),
            resultado_tipo2.get('ciudad_lugar', ''),
            resultado_tipo3.get('ciudad_lugar', '')
        )
        
        discrepancias.append(DiscrepanciaItem(
            campo="Lugar o ciudad",
            tipo_anexo1=resultado_tipo1.get('ciudad_lugar', 'N/A'),
            tipo_anexo2=resultado_tipo2.get('ciudad_lugar', 'N/A'),
            tipo_anexo3=resultado_tipo3.get('ciudad_lugar', 'N/A'),
            coincide=lugar_coincide,
            observaciones=lugar_obs,
            criticidad="BAJA"
        ))
        
        insumos_coincide, insumos_obs = self.comparar_insumos(
            resultado_tipo1.get('insumos_utilizados', []),
            resultado_tipo2.get('insumos_utilizados', []),
            resultado_tipo3.get('insumos_mencionados', [])
        )
        
        discrepancias.append(DiscrepanciaItem(
            campo="Insumos utilizados",
            tipo_anexo1=f"{len(resultado_tipo1.get('insumos_utilizados', []))} insumos",
            tipo_anexo2=f"{len(resultado_tipo2.get('insumos_utilizados', []))} insumos",
            tipo_anexo3=f"{len(resultado_tipo3.get('insumos_mencionados', []))} insumos",
            coincide=insumos_coincide,
            observaciones=insumos_obs,
            criticidad="ALTA" if not insumos_coincide else "BAJA"
        ))
        
        traz_coincide, traz_obs = self.analizar_trazabilidad(resultado_tipo1)
        
        discrepancias.append(DiscrepanciaItem(
            campo="Trazabilidad (REF/LOT)",
            tipo_anexo1="Evaluado" if resultado_tipo1 else "N/A",
            tipo_anexo2="No aplica",
            tipo_anexo3="No aplica",
            coincide=traz_coincide,
            observaciones=traz_obs,
            criticidad="ALTA" if not traz_coincide else "BAJA"
        ))
        
        return discrepancias
    
    def generar_resumen_ejecutivo(self, discrepancias: List[DiscrepanciaItem]) -> Dict[str, Any]:
        total_campos = len(discrepancias)
        coincidencias = sum(1 for d in discrepancias if d.coincide)
        
        criticidad_counts = {}
        for d in discrepancias:
            if not d.coincide:
                criticidad_counts[d.criticidad] = criticidad_counts.get(d.criticidad, 0) + 1
        
        requiere_revision = any(d.criticidad == 'ALTA' and not d.coincide for d in discrepancias)
        
        if criticidad_counts.get('ALTA', 0) >= 3:
            recomendacion = "REVISION URGENTE: Múltiples discrepancias críticas"
        elif criticidad_counts.get('ALTA', 0) >= 1:
            recomendacion = "REVISION NECESARIA: Discrepancias críticas detectadas"
        else:
            recomendacion = "REVISION OPCIONAL: Solo discrepancias menores"
        
        return {
            'total_campos_evaluados': total_campos,
            'campos_coincidentes': coincidencias,
            'campos_con_discrepancias': total_campos - coincidencias,
            'porcentaje_coincidencia': round((coincidencias / total_campos) * 100, 2),
            'discrepancias_por_criticidad': criticidad_counts,
            'requiere_revision_manual': requiere_revision,
            'recomendacion': recomendacion
        }

st.set_page_config(
    page_title="Smart OCR - Extractor Médico",
    layout="wide"
)

def init_session_state():
    if 'processor' not in st.session_state:
        try:
            api_key = load_api_key()
            ocr_client = OCRSpaceClient(api_key)
            st.session_state.processor = SmartOCRProcessor(ocr_client)
            st.session_state.api_ready = True
        except Exception as e:
            st.session_state.api_ready = False
            st.session_state.error_msg = str(e)

def format_insumos_table(insumos, tipo):
    if not insumos:
        return None
    
    if tipo == 1:
        df_data = []
        for insumo in insumos:
            df_data.append({
                'Nombre': insumo.get('nombre', 'N/A'),
                'Cantidad': insumo.get('cantidad', 'N/A'),
                'Referencia': insumo.get('referencia_ref', 'N/A'),
                'Lote': insumo.get('lote_lot', 'N/A'),
                'Vencimiento': insumo.get('fecha_vencimiento', 'N/A'),
                'Etiqueta': 'SI' if insumo.get('etiqueta_presente') else 'NO'
            })
    
    elif tipo == 2:
        df_data = []
        for insumo in insumos:
            df_data.append({
                'Nombre': insumo.get('nombre', 'N/A'),
                'Cantidad': insumo.get('cantidad', 'N/A'),
                'Observaciones': insumo.get('observaciones', 'N/A')
            })
    
    elif tipo == 3:
        df_data = []
        for insumo in insumos:
            variantes = ', '.join(insumo.get('variantes_denominacion', []))
            df_data.append({
                'Nombre': insumo.get('nombre', 'N/A'),
                'Variantes': variantes if variantes else 'N/A',
                'Trazabilidad': 'SI' if insumo.get('mencion_trazabilidad') else 'NO'
            })
    
    return pd.DataFrame(df_data)

def display_single_result(result, tipo, doc_name):
    result_dict = json.loads(result.model_dump_json())
    
    with st.container():
        st.success(f"Procesado: {doc_name} - {result_dict['tipo_documento']}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Información Básica")
            
            if result_dict.get('nombre_paciente'):
                st.write(f"**Paciente:** {result_dict['nombre_paciente']}")
            
            if result_dict.get('fecha_reporte'):
                st.write(f"**Fecha:** {result_dict['fecha_reporte']}")
            
            if result_dict.get('datos_procedimiento'):
                st.write(f"**Procedimiento:** {result_dict['datos_procedimiento']}")
            
            if result_dict.get('medico_responsable'):
                st.write(f"**Médico:** {result_dict['medico_responsable']}")
            
            if result_dict.get('cirujano'):
                st.write(f"**Cirujano:** {result_dict['cirujano']}")
            
            if result_dict.get('ciudad_lugar'):
                st.write(f"**Ciudad:** {result_dict['ciudad_lugar']}")
        
        with col2:
            st.subheader("Información Adicional")
            
            if tipo == 1 and result_dict.get('etiquetas_trazabilidad'):
                st.write("**Trazabilidad:**")
                traza = result_dict['etiquetas_trazabilidad']
                st.write(f"- Referencias: {'SI' if traza.get('tiene_referencias') else 'NO'}")
                st.write(f"- Lotes: {'SI' if traza.get('tiene_lotes') else 'NO'}")
                st.write(f"- UDI: {'SI' if traza.get('tiene_udi') else 'NO'}")
                st.write(f"- Fechas venc.: {'SI' if traza.get('tiene_fechas_vencimiento') else 'NO'}")
            
            if tipo == 2 and result_dict.get('datos_clinicos_administrativos'):
                datos = result_dict['datos_clinicos_administrativos']
                if datos:
                    st.write("**Datos Administrativos:**")
                    for key, value in datos.items():
                        st.write(f"- {key.replace('_', ' ').title()}: {value}")
            
            if tipo == 3 and result_dict.get('datos_complementarios'):
                datos = result_dict['datos_complementarios']
                if datos:
                    st.write("**Datos Complementarios:**")
                    for key, value in datos.items():
                        if key == 'codigos_procedimiento' and isinstance(value, list):
                            st.write(f"- Códigos: {', '.join(value)}")
                        else:
                            st.write(f"- {key.replace('_', ' ').title()}: {value}")
        
        if tipo == 1 and result_dict.get('insumos_utilizados'):
            st.subheader("Insumos Utilizados (Con Trazabilidad)")
            df = format_insumos_table(result_dict['insumos_utilizados'], tipo)
            if df is not None:
                st.dataframe(df, width='stretch')
        
        elif tipo == 2 and result_dict.get('insumos_utilizados'):
            st.subheader("Insumos Utilizados (Sin Trazabilidad)")
            df = format_insumos_table(result_dict['insumos_utilizados'], tipo)
            if df is not None:
                st.dataframe(df, width='stretch')
        
        elif tipo == 3 and result_dict.get('insumos_mencionados'):
            st.subheader("Insumos Mencionados")
            df = format_insumos_table(result_dict['insumos_mencionados'], tipo)
            if df is not None:
                st.dataframe(df, width='stretch')
        
        if tipo == 3 and result_dict.get('descripcion_procedimiento'):
            st.subheader("Descripción del Procedimiento")
            st.text_area(
                "Detalles técnicos:",
                result_dict['descripcion_procedimiento'],
                height=200,
                disabled=True,
                key=f"desc_{doc_name}"
            )
        
        col_json, col_download = st.columns(2)
        
        with col_json:
            with st.expander(f"Ver JSON - {doc_name}"):
                st.json(result_dict)
        
        with col_download:
            st.download_button(
                label=f"Descargar JSON - {doc_name}",
                data=result.model_dump_json(indent=2),
                file_name=f"resultado_{doc_name}_tipo_{tipo}.json",
                mime="application/json",
                key=f"download_{doc_name}"
            )

def process_multiple_files(files, language):
    results = []
    
    file_type_mapping = {
        1: "Reporte Interno",
        2: "Reporte Hospital", 
        3: "Descripción Quirúrgica"
    }
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, (uploaded_file, tipo) in enumerate(files):
        try:
            status_text.text(f"Procesando {uploaded_file.name} (Tipo {tipo})...")
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name
            
            result = st.session_state.processor.process(
                tmp_path,
                tipo,
                language=language
            )
            
            os.unlink(tmp_path)
            
            results.append({
                'file_name': uploaded_file.name,
                'tipo': tipo,
                'result': result,
                'success': True,
                'error': None
            })
            
        except Exception as e:
            results.append({
                'file_name': uploaded_file.name,
                'tipo': tipo,
                'result': None,
                'success': False,
                'error': str(e)
            })
            
            if "tmp_path" in locals():
                try:
                    os.unlink(tmp_path)
                except:
                    pass
        
        progress_bar.progress((i + 1) / len(files))
    
    status_text.text("Procesamiento completado")
    progress_bar.empty()
    status_text.empty()
    
    return results

def display_discrepancias(successful_results):
    if len(successful_results) < 2:
        return
    
    analizador = AnalizadorDiscrepancias()
    
    resultado_tipo1 = {}
    resultado_tipo2 = {}
    resultado_tipo3 = {}
    
    for result_info in successful_results:
        result_dict = json.loads(result_info['result'].model_dump_json())
        if result_info['tipo'] == 1:
            resultado_tipo1 = result_dict
        elif result_info['tipo'] == 2:
            resultado_tipo2 = result_dict
        elif result_info['tipo'] == 3:
            resultado_tipo3 = result_dict
    
    if not any([resultado_tipo1, resultado_tipo2, resultado_tipo3]):
        return
    
    discrepancias = analizador.procesar_resultados(resultado_tipo1, resultado_tipo2, resultado_tipo3)
    resumen = analizador.generar_resumen_ejecutivo(discrepancias)
    
    st.markdown("---")
    st.subheader("Análisis de Discrepancias")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Campos evaluados", resumen['total_campos_evaluados'])
    
    with col2:
        st.metric("Coincidencias", resumen['campos_coincidentes'])
    
    with col3:
        st.metric("Discrepancias", resumen['campos_con_discrepancias'])
    
    with col4:
        porcentaje = resumen['porcentaje_coincidencia']
        color = "normal" if porcentaje >= 80 else "inverse" if porcentaje >= 60 else "off"
        st.metric("% Coincidencia", f"{porcentaje}%")
    
    if resumen['requiere_revision_manual']:
        st.error(f"🚨 {resumen['recomendacion']}")
    else:
        st.success(f"✅ {resumen['recomendacion']}")
    
    df_data = []
    for disc in discrepancias:
        color_coincide = "🟢 SI" if disc.coincide else "🔴 NO"
        
        if disc.criticidad == "ALTA":
            criticidad_icon = "🚨 ALTA"
        elif disc.criticidad == "MEDIA":
            criticidad_icon = "⚠️ MEDIA"
        else:
            criticidad_icon = "ℹ️ BAJA"
        
        df_data.append({
            'Campo': disc.campo,
            'Anexo 1 (Interno)': disc.tipo_anexo1,
            'Anexo 2 (Hospital)': disc.tipo_anexo2,
            'Anexo 3 (Descripción)': disc.tipo_anexo3,
            'Coincide': color_coincide,
            'Observaciones': disc.observaciones,
            'Criticidad': criticidad_icon
        })
    
    df_discrepancias = pd.DataFrame(df_data)
    
    st.subheader("Tabla de Discrepancias Detallada")
    st.dataframe(df_discrepancias, width='stretch', height=400)
    
    if resumen['discrepancias_por_criticidad']:
        st.subheader("Resumen por Criticidad")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            alta = resumen['discrepancias_por_criticidad'].get('ALTA', 0)
            if alta > 0:
                st.error(f"🚨 ALTA: {alta} discrepancias")
            else:
                st.success("🚨 ALTA: 0 discrepancias")
        
        with col2:
            media = resumen['discrepancias_por_criticidad'].get('MEDIA', 0)
            if media > 0:
                st.warning(f"⚠️ MEDIA: {media} discrepancias")
            else:
                st.success("⚠️ MEDIA: 0 discrepancias")
        
        with col3:
            baja = resumen['discrepancias_por_criticidad'].get('BAJA', 0)
            if baja > 0:
                st.info(f"ℹ️ BAJA: {baja} discrepancias")
            else:
                st.success("ℹ️ BAJA: 0 discrepancias")

def create_comparison_table(results):
    comparison_data = []
    
    for result_info in results:
        if result_info['success']:
            result_dict = json.loads(result_info['result'].model_dump_json())
            comparison_data.append({
                'Documento': result_info['file_name'],
                'Tipo': f"Tipo {result_info['tipo']}",
                'Paciente': result_dict.get('nombre_paciente', 'N/A'),
                'Fecha': result_dict.get('fecha_reporte', 'N/A'),
                'Procedimiento': result_dict.get('datos_procedimiento', 'N/A')[:50] + '...' if result_dict.get('datos_procedimiento') and len(result_dict.get('datos_procedimiento', '')) > 50 else result_dict.get('datos_procedimiento', 'N/A'),
                'Estado': 'Procesado'
            })
        else:
            comparison_data.append({
                'Documento': result_info['file_name'],
                'Tipo': f"Tipo {result_info['tipo']}",
                'Paciente': 'Error',
                'Fecha': 'Error',
                'Procedimiento': 'Error',
                'Estado': 'Error'
            })
    
    return pd.DataFrame(comparison_data)

def main():
    init_session_state()
    
    st.title("Smart OCR - Extractor Médico")
    st.markdown("### Procesa múltiples documentos médicos simultáneamente")
    st.markdown("**Desarrollado por Abner Silva**")
    
    if not st.session_state.api_ready:
        st.error(f"Error de configuración: {st.session_state.error_msg}")
        st.info("Asegúrate de que el archivo .env contenga OCR_SPACE_API_KEY")
        return
    
    st.sidebar.header("Configuración")
    
    language = st.sidebar.selectbox(
        "Idioma OCR:",
        options=["spa", "eng"],
        format_func=lambda x: "Español" if x == "spa" else "English"
    )
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("Tipos de Documentos")
    st.sidebar.info("""
    **Tipo 1 - Reporte Interno:**
    Con trazabilidad completa (REF/LOT)
    
    **Tipo 2 - Reporte Hospital:**
    Sin trazabilidad, datos básicos
    
    **Tipo 3 - Descripción Quirúrgica:**
    Narrativa científica detallada
    """)
    
    st.markdown("---")
    st.subheader("Subir Documentos")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Tipo 1: Reporte Interno**")
        file_tipo1 = st.file_uploader(
            "Reporte con trazabilidad",
            type=['png', 'jpg', 'jpeg', 'pdf'],
            key="file1",
            help="Reporte interno con REF/LOT completo"
        )
        if file_tipo1:
            st.image(file_tipo1, caption=f"Tipo 1: {file_tipo1.name}", width=200)
    
    with col2:
        st.markdown("**Tipo 2: Reporte Hospital**")
        file_tipo2 = st.file_uploader(
            "Reporte básico",
            type=['png', 'jpg', 'jpeg', 'pdf'],
            key="file2",
            help="Reporte hospitalario sin trazabilidad"
        )
        if file_tipo2:
            st.image(file_tipo2, caption=f"Tipo 2: {file_tipo2.name}", width=200)
    
    with col3:
        st.markdown("**Tipo 3: Descripción Quirúrgica**")
        file_tipo3 = st.file_uploader(
            "Descripción narrativa",
            type=['png', 'jpg', 'jpeg', 'pdf'],
            key="file3",
            help="Descripción quirúrgica del médico"
        )
        if file_tipo3:
            st.image(file_tipo3, caption=f"Tipo 3: {file_tipo3.name}", width=200)
    
    files_to_process = []
    if file_tipo1:
        files_to_process.append((file_tipo1, 1))
    if file_tipo2:
        files_to_process.append((file_tipo2, 2))
    if file_tipo3:
        files_to_process.append((file_tipo3, 3))
    
    if files_to_process:
        st.markdown("---")
        st.subheader("Resumen de Archivos")
        
        summary_data = []
        total_size = 0
        for file, tipo in files_to_process:
            summary_data.append({
                'Archivo': file.name,
                'Tipo': f"Tipo {tipo}",
                'Tamaño': f"{file.size / 1024:.1f} KB"
            })
            total_size += file.size
        
        st.dataframe(pd.DataFrame(summary_data), width='stretch')
        st.write(f"**Total:** {len(files_to_process)} archivos - {total_size / 1024:.1f} KB")
        
        if st.button("Procesar Todos los Documentos", type="primary"):
            with st.spinner("Procesando documentos..."):
                results = process_multiple_files(files_to_process, language)
            
            st.markdown("---")
            st.subheader("Resultados del Procesamiento")
            
            comparison_df = create_comparison_table(results)
            st.dataframe(comparison_df, width='stretch')
            
            successful_results = [r for r in results if r['success']]
            failed_results = [r for r in results if not r['success']]
            
            if failed_results:
                st.error(f"Error en {len(failed_results)} documento(s):")
                for failed in failed_results:
                    st.write(f"- {failed['file_name']}: {failed['error']}")
            
            if successful_results:
                st.success(f"Procesados exitosamente: {len(successful_results)} documento(s)")
                
                display_discrepancias(successful_results)
                
                st.markdown("---")
                st.subheader("Detalles de Cada Documento")
                
                for result_info in successful_results:
                    st.markdown(f"### {result_info['file_name']} (Tipo {result_info['tipo']})")
                    
                    with st.container():
                        display_single_result(
                            result_info['result'], 
                            result_info['tipo'], 
                            result_info['file_name'].replace('.', '_')
                        )
                    
                    st.markdown("---")
                
                combined_data = {}
                for result_info in successful_results:
                    result_dict = json.loads(result_info['result'].model_dump_json())
                    combined_data[f"documento_tipo_{result_info['tipo']}"] = result_dict
                
                st.download_button(
                    label="Descargar Todos los Resultados (JSON)",
                    data=json.dumps(combined_data, indent=2, ensure_ascii=False),
                    file_name="resultados_completos.json",
                    mime="application/json"
                )
    
    else:
        st.info("Sube al menos un documento para comenzar el procesamiento")
    
    st.markdown("---")
    with st.expander("Información sobre el procesamiento múltiple"):
        st.markdown("""
        **Procesamiento en Lote:**
        - Sube hasta 3 documentos simultáneamente
        - Cada documento se procesa según su tipo específico
        - Los resultados se muestran organizados por documento
        - Tabla comparativa para análisis rápido
        - Descarga individual o completa en JSON
        
        **Ventajas:**
        - Procesamiento eficiente de múltiples archivos
        - Comparación automática de datos básicos
        - Detección de inconsistencias entre documentos
        - Exportación organizada de todos los resultados
        """)
    
    st.markdown("---")
    st.markdown("**© 2024 Smart OCR - Desarrollado por Abner Silva**")

if __name__ == "__main__":
    main()