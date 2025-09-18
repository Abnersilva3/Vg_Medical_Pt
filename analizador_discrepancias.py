import json
import pandas as pd
from datetime import datetime
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import difflib
from pathlib import Path
import argparse

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
            return True, f"Todas las fechas coinciden: {fechas_validas[0]}"
        
        return False, f"Fechas diferentes encontradas: {', '.join(set(fechas_validas))}"
    
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
            return True, f"Solo un nombre disponible: {nombres_validos[0]}"
        
        promedio_similitud = sum(similitudes) / len(similitudes)
        
        if promedio_similitud >= 0.8:
            return True, f"Nombres similares (similitud: {promedio_similitud:.2f})"
        
        return False, f"Nombres diferentes (similitud: {promedio_similitud:.2f}): {', '.join(nombres_validos)}"
    
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
            return False, "No se encontraron insumos en ningún documento"
        
        discrepancias = []
        coincidencias = []
        
        for insumo in todos_insumos:
            cant1 = ins1.get(insumo, 'Ausente')
            cant2 = ins2.get(insumo, 'Ausente')
            cant3 = ins3.get(insumo, 'Ausente')
            
            cantidades_presentes = [c for c in [cant1, cant2, cant3] if c != 'Ausente']
            
            if len(set(cantidades_presentes)) <= 1:
                if cantidades_presentes:
                    coincidencias.append(f"{insumo}: {cantidades_presentes[0]}")
            else:
                discrepancias.append(f"{insumo} - T1:{cant1}, T2:{cant2}, T3:{cant3}")
        
        if not discrepancias:
            return True, f"Insumos coinciden: {'; '.join(coincidencias[:3])}{'...' if len(coincidencias) > 3 else ''}"
        
        return False, f"Discrepancias: {'; '.join(discrepancias[:2])}{'...' if len(discrepancias) > 2 else ''}"
    
    def analizar_trazabilidad(self, resultado_tipo1: Dict) -> Tuple[bool, str]:
        if not resultado_tipo1:
            return False, "No hay datos del Tipo 1 (Interno)"
        
        trazabilidad = resultado_tipo1.get('etiquetas_trazabilidad', {})
        
        if not trazabilidad:
            return False, "No se encontraron datos de trazabilidad"
        
        elementos = {
            'referencias': trazabilidad.get('tiene_referencias', False),
            'lotes': trazabilidad.get('tiene_lotes', False),
            'udi': trazabilidad.get('tiene_udi', False),
            'fechas_venc': trazabilidad.get('tiene_fechas_vencimiento', False)
        }
        
        presentes = [k for k, v in elementos.items() if v]
        ausentes = [k for k, v in elementos.items() if not v]
        
        if len(presentes) >= 3:
            return True, f"Trazabilidad completa: {', '.join(presentes)}"
        elif len(presentes) >= 1:
            return False, f"Trazabilidad parcial. Presente: {', '.join(presentes)}. Falta: {', '.join(ausentes)}"
        else:
            return False, "Sin datos de trazabilidad"
    
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
            tipo_anexo1=resultado_tipo1.get('datos_procedimiento', 'N/A')[:50] + '...' if len(resultado_tipo1.get('datos_procedimiento', '')) > 50 else resultado_tipo1.get('datos_procedimiento', 'N/A'),
            tipo_anexo2=resultado_tipo2.get('datos_procedimiento', 'N/A')[:50] + '...' if len(resultado_tipo2.get('datos_procedimiento', '')) > 50 else resultado_tipo2.get('datos_procedimiento', 'N/A'),
            tipo_anexo3=resultado_tipo3.get('datos_procedimiento', 'N/A')[:50] + '...' if len(resultado_tipo3.get('datos_procedimiento', '')) > 50 else resultado_tipo3.get('datos_procedimiento', 'N/A'),
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
    
    def generar_reporte(self, discrepancias: List[DiscrepanciaItem]) -> pd.DataFrame:
        data = []
        for disc in discrepancias:
            data.append({
                'Campo': disc.campo,
                'Anexo 1 (Interno)': disc.tipo_anexo1,
                'Anexo 2 (Hospital)': disc.tipo_anexo2,
                'Anexo 3 (Descripción)': disc.tipo_anexo3,
                'Coincide': 'SI' if disc.coincide else 'NO',
                'Observaciones': disc.observaciones,
                'Criticidad': disc.criticidad
            })
        
        return pd.DataFrame(data)
    
    def generar_resumen_ejecutivo(self, discrepancias: List[DiscrepanciaItem]) -> Dict[str, Any]:
        total_campos = len(discrepancias)
        coincidencias = sum(1 for d in discrepancias if d.coincide)
        
        criticidad_counts = {}
        for d in discrepancias:
            if not d.coincide:
                criticidad_counts[d.criticidad] = criticidad_counts.get(d.criticidad, 0) + 1
        
        return {
            'total_campos_evaluados': total_campos,
            'campos_coincidentes': coincidencias,
            'campos_con_discrepancias': total_campos - coincidencias,
            'porcentaje_coincidencia': round((coincidencias / total_campos) * 100, 2),
            'discrepancias_por_criticidad': criticidad_counts,
            'requiere_revision_manual': any(d.criticidad == 'ALTA' and not d.coincide for d in discrepancias),
            'recomendacion': self._generar_recomendacion(discrepancias)
        }
    
    def _generar_recomendacion(self, discrepancias: List[DiscrepanciaItem]) -> str:
        alta_criticidad = [d for d in discrepancias if d.criticidad == 'ALTA' and not d.coincide]
        
        if len(alta_criticidad) >= 3:
            return "REVISION URGENTE: Múltiples discrepancias críticas detectadas"
        elif len(alta_criticidad) >= 1:
            return "REVISION NECESARIA: Discrepancias críticas en campos importantes"
        else:
            return "REVISION OPCIONAL: Solo discrepancias menores detectadas"

def cargar_resultados_json(archivo_path: str) -> Dict[str, Any]:
    try:
        with open(archivo_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error cargando {archivo_path}: {e}")
        return {}

def main():
    parser = argparse.ArgumentParser(description='Analizador de Discrepancias Médicas')
    parser.add_argument('--json', help='Archivo JSON con resultados completos')
    parser.add_argument('--tipo1', help='Archivo JSON del tipo 1')
    parser.add_argument('--tipo2', help='Archivo JSON del tipo 2')
    parser.add_argument('--tipo3', help='Archivo JSON del tipo 3')
    parser.add_argument('--output', default='discrepancias.xlsx', help='Archivo de salida')
    
    args = parser.parse_args()
    
    analizador = AnalizadorDiscrepancias()
    
    if args.json:
        datos_completos = cargar_resultados_json(args.json)
        resultado_tipo1 = datos_completos.get('documento_tipo_1', {})
        resultado_tipo2 = datos_completos.get('documento_tipo_2', {})
        resultado_tipo3 = datos_completos.get('documento_tipo_3', {})
    else:
        resultado_tipo1 = cargar_resultados_json(args.tipo1) if args.tipo1 else {}
        resultado_tipo2 = cargar_resultados_json(args.tipo2) if args.tipo2 else {}
        resultado_tipo3 = cargar_resultados_json(args.tipo3) if args.tipo3 else {}
    
    if not any([resultado_tipo1, resultado_tipo2, resultado_tipo3]):
        print("Error: No se pudieron cargar datos de ningún documento")
        return
    
    print("Analizando discrepancias...")
    discrepancias = analizador.procesar_resultados(resultado_tipo1, resultado_tipo2, resultado_tipo3)
    
    df_discrepancias = analizador.generar_reporte(discrepancias)
    resumen = analizador.generar_resumen_ejecutivo(discrepancias)
    
    print("\n=== REPORTE DE DISCREPANCIAS ===")
    print(f"Total campos evaluados: {resumen['total_campos_evaluados']}")
    print(f"Campos coincidentes: {resumen['campos_coincidentes']}")
    print(f"Campos con discrepancias: {resumen['campos_con_discrepancias']}")
    print(f"Porcentaje de coincidencia: {resumen['porcentaje_coincidencia']}%")
    print(f"Requiere revisión manual: {'SI' if resumen['requiere_revision_manual'] else 'NO'}")
    print(f"Recomendación: {resumen['recomendacion']}")
    
    print("\n=== TABLA DE DISCREPANCIAS ===")
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', 50)
    print(df_discrepancias.to_string(index=False))
    
    try:
        with pd.ExcelWriter(args.output, engine='openpyxl') as writer:
            df_discrepancias.to_excel(writer, sheet_name='Discrepancias', index=False)
            
            df_resumen = pd.DataFrame([resumen])
            df_resumen.to_excel(writer, sheet_name='Resumen_Ejecutivo', index=False)
        
        print(f"\nReporte guardado en: {args.output}")
    except Exception as e:
        print(f"Error guardando Excel: {e}")
        
        csv_output = args.output.replace('.xlsx', '.csv')
        df_discrepancias.to_csv(csv_output, index=False, encoding='utf-8')
        print(f"Reporte guardado en CSV: {csv_output}")

if __name__ == "__main__":
    main()
