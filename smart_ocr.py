import re
import json
import argparse
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path
from pydantic import BaseModel, Field
from datetime import datetime

import requests
from dotenv import load_dotenv
import os


class InsumoInterno(BaseModel):
    nombre: Optional[str] = None
    cantidad: Optional[int] = None
    referencia_ref: Optional[str] = None
    lote_lot: Optional[str] = None
    fecha_vencimiento: Optional[str] = None
    etiqueta_presente: Optional[bool] = None


class InsumoHospital(BaseModel):
    nombre: Optional[str] = None
    cantidad: Optional[int] = None
    observaciones: Optional[str] = None


class InsumoDescripcion(BaseModel):
    nombre: Optional[str] = None
    variantes_denominacion: List[str] = Field(default_factory=list)
    mencion_trazabilidad: Optional[bool] = None


class ReporteInternoQuirurgico(BaseModel):
    tipo_documento: str = "REPORTE DE GASTO QUIRÚRGICO (INTERNO)"
    nombre_paciente: Optional[str] = None
    fecha_reporte: Optional[str] = None
    datos_procedimiento: Optional[str] = None
    medico_responsable: Optional[str] = None
    insumos_utilizados: List[InsumoInterno] = Field(default_factory=list)
    etiquetas_trazabilidad: Dict[str, bool] = Field(default_factory=dict)
    ciudad_lugar: Optional[str] = None
    firmas_responsables: Optional[str] = None


class ReporteHospitalQuirurgico(BaseModel):
    tipo_documento: str = "REPORTE DE GASTO QUIRÚRGICO (HOSPITAL)"
    nombre_paciente: Optional[str] = None
    fecha_reporte: Optional[str] = None
    datos_procedimiento: Optional[str] = None
    cirujano: Optional[str] = None
    insumos_utilizados: List[InsumoHospital] = Field(default_factory=list)
    ciudad_lugar: Optional[str] = None
    datos_clinicos_administrativos: Dict[str, Any] = Field(default_factory=dict)
    nota_trazabilidad: str = "Generalmente no incluye REF/LOT o etiquetas"


class DescripcionQuirurgica(BaseModel):
    tipo_documento: str = "DESCRIPCIÓN QUIRÚRGICA (DOCTOR)"
    descripcion_procedimiento: Optional[str] = None
    insumos_mencionados: List[InsumoDescripcion] = Field(default_factory=list)
    referencias_trazabilidad: Dict[str, Any] = Field(default_factory=dict)
    datos_complementarios: Dict[str, Any] = Field(default_factory=dict)


class OCRClient(ABC):
    
    @abstractmethod
    def extract_text(self, image_path: str, **kwargs) -> str:
        pass


class DataExtractor(ABC):
    
    @abstractmethod
    def extract(self, text: str) -> BaseModel:
        pass


class TextProcessor(ABC):
    
    @abstractmethod
    def clean_text(self, text: str) -> str:
        pass


class OCRSpaceClient(OCRClient):
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.ocr.space/parse/image"
    
    def extract_text(self, image_path: str, language: str = "spa", **kwargs) -> str:
        
        if not Path(image_path).exists():
            raise FileNotFoundError(f"No se encontró: {image_path}")
        
        payload = {
            'apikey': self.api_key,
            'language': language,
            'isOverlayRequired': 'false',
            'detectOrientation': 'true',
            'scale': 'true',
            'OCREngine': '2'
        }
        
        with open(image_path, 'rb') as file:
            files = {'file': file}
            
            try:
                response = requests.post(self.base_url, files=files, data=payload, timeout=30)
                response.raise_for_status()
                
                result = response.json()
                
                if result.get('IsErroredOnProcessing', True):
                    raise Exception(f"Error OCR: {result.get('ErrorMessage', 'Desconocido')}")
                
                text_results = []
                for parsed in result.get('ParsedResults', []):
                    text = parsed.get('ParsedText', '').strip()
                    if text:
                        text_results.append(text)
                
                return '\n\n'.join(text_results)
                
            except requests.exceptions.RequestException as e:
                raise Exception(f"Error en API: {e}")


class MedicalTextProcessor(TextProcessor):
    
    def clean_text(self, text: str) -> str:
        corrections = {
            r'Torn\s+enceçálico': 'Tornillo encefálico',
            r'Tôrn\s+encefálico': 'Tornillo encefálico',
            r'curvanervios': 'CurvaNerv',
            r'Especialeta': 'Especialista',
            r'Procedmeo': 'Procedimiento',
            r'Fecho': 'Fecha',
            r'Remitión': 'Remisión'
        }
        
        cleaned_text = text
        for pattern, replacement in corrections.items():
            cleaned_text = re.sub(pattern, replacement, cleaned_text, flags=re.IGNORECASE)
        
        return cleaned_text


class ReporteInternoExtractor(DataExtractor):
    
    def __init__(self, text_processor: TextProcessor):
        self.text_processor = text_processor
    
    def extract(self, text: str) -> ReporteInternoQuirurgico:
        
        cleaned_text = self.text_processor.clean_text(text)
        
        return ReporteInternoQuirurgico(
            nombre_paciente=self._extract_patient_name(cleaned_text),
            fecha_reporte=self._extract_date(cleaned_text),
            datos_procedimiento=self._extract_procedure(cleaned_text),
            medico_responsable=self._extract_doctor(cleaned_text),
            insumos_utilizados=self._extract_supplies_with_traceability(cleaned_text),
            etiquetas_trazabilidad=self._check_traceability(cleaned_text),
            ciudad_lugar=self._extract_location(cleaned_text),
            firmas_responsables=self._extract_signatures(cleaned_text)
        )
    
    def _extract_patient_name(self, text: str) -> Optional[str]:
        patterns = [
            r'por\s+([A-Za-záéíóúñÑ\s]+?)(?:\n|\d{10})',
            r'Paciente[:\s]+([A-Za-záéíóúñÑ\s]+?)(?:\n|$)',
            r'Cliente[:\s]+([A-Za-záéíóúñÑ\s]+?)(?:\n|$)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                name = match.group(1).strip()
                if len(name) > 3 and not name.isdigit():
                    return name
        return None
    
    def _extract_date(self, text: str) -> Optional[str]:
        patterns = [
            r'Fecha[:\s]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
            r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
            r'(\d{1,2}/\d{1,2}/\d{4})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None
    
    def _extract_procedure(self, text: str) -> Optional[str]:
        patterns = [
            r'Procedimiento[:\s]+([^\n]+)',
            r'Osteosíntesis[^\n]*',
            r'Procedmeo[:\s]+([^\n]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0).strip()
        return None
    
    def _extract_doctor(self, text: str) -> Optional[str]:
        patterns = [
            r'Especialista[:\s]+(Dr\.?\s*[A-Za-záéíóúñÑ\s]+?)(?:\n|$)',
            r'(Dr\.?\s*[A-Za-záéíóúñÑ\s]+?)(?:\n|Procedimiento)',
            r'Médico[:\s]+([A-Za-záéíóúñÑ\s]+?)(?:\n|$)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None
    
    def _extract_supplies_with_traceability(self, text: str) -> List[InsumoInterno]:
        supplies = []
        
        lines = text.split('\n')
        for i, line in enumerate(lines):
            ref_match = re.search(r'(\d{5,}[-\d]*)', line)
            if ref_match:
                supply = InsumoInterno()
                supply.referencia_ref = ref_match.group(1)
                
                desc_match = re.search(r'(Tornillo|Placa|Pin|Torn)[^0-9]*', line, re.IGNORECASE)
                if desc_match:
                    supply.nombre = desc_match.group(0).strip()
                
                qty_match = re.search(r'^(\d+)', line.strip())
                if qty_match and int(qty_match.group(1)) < 1000:
                    supply.cantidad = int(qty_match.group(1))
                
                for j in range(max(0, i-2), min(len(lines), i+3)):
                    lot_match = re.search(r'LOT[:\s]*(\d+)', lines[j], re.IGNORECASE)
                    if lot_match:
                        supply.lote_lot = lot_match.group(1)
                        break
                
                for j in range(max(0, i-2), min(len(lines), i+3)):
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', lines[j])
                    if date_match:
                        supply.fecha_vencimiento = date_match.group(1)
                        break
                
                supply.etiqueta_presente = bool(supply.lote_lot or supply.fecha_vencimiento)
                
                if supply.referencia_ref:
                    supplies.append(supply)
        
        return supplies
    
    def _check_traceability(self, text: str) -> Dict[str, bool]:
        return {
            'tiene_referencias': bool(re.search(r'REF[:\s]*\d+', text, re.IGNORECASE)),
            'tiene_lotes': bool(re.search(r'LOT[:\s]*\d+', text, re.IGNORECASE)),
            'tiene_udi': bool(re.search(r'UDI[:\s]*\d+', text, re.IGNORECASE)),
            'tiene_fechas_vencimiento': bool(re.search(r'\d{4}-\d{2}-\d{2}', text))
        }
    
    def _extract_location(self, text: str) -> Optional[str]:
        patterns = [
            r'(Bucaramanga|Bogotá|Medellín|Cali|Barranquilla)',
            r'slidad\s+([A-Za-záéíóúñÑ]+)',
            r'Ciudad[:\s]+([A-Za-záéíóúñÑ]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1) if len(match.groups()) > 0 else match.group(0)
        return None
    
    def _extract_signatures(self, text: str) -> Optional[str]:
        patterns = [
            r'Firmay?\s+([^\n]+)',
            r'Firma[:\s]+([^\n]+)',
            r'Instrumentador[:\s]+([^\n]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None


class ReporteHospitalExtractor(DataExtractor):
    
    def __init__(self, text_processor: TextProcessor):
        self.text_processor = text_processor
    
    def extract(self, text: str) -> ReporteHospitalQuirurgico:
        
        cleaned_text = self.text_processor.clean_text(text)
        
        return ReporteHospitalQuirurgico(
            nombre_paciente=self._extract_patient_name(cleaned_text),
            fecha_reporte=self._extract_date(cleaned_text),
            datos_procedimiento=self._extract_procedure(cleaned_text),
            cirujano=self._extract_doctor(cleaned_text),
            insumos_utilizados=self._extract_supplies_basic(cleaned_text),
            ciudad_lugar=self._extract_location(cleaned_text),
            datos_clinicos_administrativos=self._extract_clinical_data(cleaned_text)
        )
    
    def _extract_patient_name(self, text: str) -> Optional[str]:
        patterns = [
            r'por\s+([A-Za-záéíóúñÑ\s]+?)(?:\n|\d{10})',
            r'Paciente[:\s]+([A-Za-záéíóúñÑ\s]+?)(?:\n|$)',
            r'Cliente[:\s]+([A-Za-záéíóúñÑ\s]+?)(?:\n|$)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                name = match.group(1).strip()
                if len(name) > 3 and not name.isdigit():
                    name = ' '.join(word.capitalize() for word in name.split())
                    return name
        return None
    
    def _extract_date(self, text: str) -> Optional[str]:
        patterns = [
            r'Fecha[:\s]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
            r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
            r'(\d{1,2}/\d{1,2}/\d{4})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None
    
    def _extract_procedure(self, text: str) -> Optional[str]:
        patterns = [
            r'Procedimiento[:\s]+([^\n]+)',
            r'Osteosíntesis[^\n]*',
            r'Procedmeo[:\s]+([^\n]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0).strip()
        return None
    
    def _extract_doctor(self, text: str) -> Optional[str]:
        patterns = [
            r'Cirujano[:\s]+([A-Za-záéíóúñÑ\s\.]+?)(?:\n|$)',
            r'CIRUJANO[:\s]+([A-Za-záéíóúñÑ\s\.]+?)(?:\n|$)',
            r'Especialista[:\s]+(Dr\.?\s*[A-Za-záéíóúñÑ\s]+?)(?:\n|Procedimiento|$)',
            r'Médico[:\s]+(Dr\.?\s*[A-Za-záéíóúñÑ\s]+?)(?:\n|$)',
            r'(?<!por\s)(?<!por\s\w{1,10}\s)(Dr\.?\s*[A-Za-záéíóúñÑ\s]+?)(?:\n|Procedimiento|$)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                doctor_name = match.group(1).strip()
                if len(doctor_name) > 3 and not self._is_patient_name(doctor_name, text):
                    return doctor_name
        return None
    
    def _is_patient_name(self, doctor_name: str, text: str) -> bool:
        patient_patterns = [
            r'por\s+([A-Za-záéíóúñÑ\s]+?)(?:\n|\d{10})',
            r'Paciente[:\s]+([A-Za-záéíóúñÑ\s]+?)(?:\n|$)',
            r'Cliente[:\s]+([A-Za-záéíóúñÑ\s]+?)(?:\n|$)'
        ]
        
        for pattern in patient_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                patient_name = match.group(1).strip()
                if (doctor_name.lower() in patient_name.lower() or 
                    patient_name.lower() in doctor_name.lower()):
                    return True
        return False
    
    def _extract_supplies_basic(self, text: str) -> List[InsumoHospital]:
        supplies = []
        
        lines = text.split('\n')
        for line in lines:
            if re.search(r'(Tornillo|Placa|Pin|Torn)', line, re.IGNORECASE):
                supply = InsumoHospital()
                
                desc_match = re.search(r'(Tornillo[^0-9]*|Placa[^0-9]*|Pin[^0-9]*)', line, re.IGNORECASE)
                if desc_match:
                    supply.nombre = desc_match.group(0).strip()
                
                qty_match = re.search(r'^(\d+)', line.strip())
                if qty_match and int(qty_match.group(1)) < 100:
                    supply.cantidad = int(qty_match.group(1))
                
                if not re.search(r'LOT|REF', line, re.IGNORECASE):
                    supply.observaciones = "Sin datos de trazabilidad"
                
                if supply.nombre:
                    supplies.append(supply)
        
        return supplies
    
    def _extract_location(self, text: str) -> Optional[str]:
        patterns = [
            r'(Bucaramanga|Bogotá|Medellín|Cali|Barranquilla)',
            r'slidad\s+([A-Za-záéíóúñÑ]+)',
            r'Ciudad[:\s]+([A-Za-záéíóúñÑ]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1) if len(match.groups()) > 0 else match.group(0)
        return None
    
    def _extract_clinical_data(self, text: str) -> Dict[str, Any]:
        data = {}
        
        asegurador_match = re.search(r'Asegurador[:\s]+([^\n]+)', text, re.IGNORECASE)
        if asegurador_match:
            data['asegurador'] = asegurador_match.group(1).strip()
        
        remision_match = re.search(r'Remisión[:\s]+(\w+)', text, re.IGNORECASE)
        if remision_match:
            data['numero_remision'] = remision_match.group(1)
        
        codigo_match = re.search(r'Código[:\s]+([^\n]+)', text, re.IGNORECASE)
        if codigo_match:
            data['codigo_reporte'] = codigo_match.group(1).strip()
        
        return data


class DescripcionQuirurgicaExtractor(DataExtractor):
    
    def __init__(self, text_processor: TextProcessor):
        self.text_processor = text_processor
    
    def extract(self, text: str) -> DescripcionQuirurgica:
        
        cleaned_text = self.text_processor.clean_text(text)
        
        return DescripcionQuirurgica(
            descripcion_procedimiento=self._extract_procedure_description(cleaned_text),
            insumos_mencionados=self._extract_mentioned_supplies(cleaned_text),
            referencias_trazabilidad=self._extract_traceability_mentions(cleaned_text),
            datos_complementarios=self._extract_complementary_data(cleaned_text)
        )
    
    def _extract_procedure_description(self, text: str) -> Optional[str]:
        lines = text.split('\n')
        description_lines = []
        
        medical_keywords = [
            'osteosíntesis', 'osteosintesis', 'encefálica', 'encefalica', 'craneofacial',
            'fractura', 'fracturas', 'temporal', 'parietal', 'frontal',
            'fijación', 'fijacion', 'dispositivo', 'dispositivos',
            'reducción', 'reduccion', 'cirugía', 'cirugia', 'quirúrgico', 'quirurgico',
            'anestesia', 'incisión', 'incision', 'sutura', 'craneales',
            'maxilofacial', 'neurocirugia', 'neurocirugía'
        ]
        
        for line in lines:
            line_clean = line.strip()
            if len(line_clean) > 10:
                if any(keyword in line_clean.lower() for keyword in medical_keywords):
                    description_lines.append(line_clean)
                elif re.search(r'(T\d+|Cirujano\s+\d+|Pre-Quirúrgico|Post-Quirúrgico)', line_clean, re.IGNORECASE):
                    description_lines.append(line_clean)
        
        seen = set()
        unique_lines = []
        for line in description_lines:
            if line not in seen:
                seen.add(line)
                unique_lines.append(line)
        
        return '\n'.join(unique_lines) if unique_lines else None
    
    def _extract_mentioned_supplies(self, text: str) -> List[InsumoDescripcion]:
        supplies = []
        supply_variants = {}
        
        variants = [
            (r'osteosintesis\s+encefalica?\s*[^\n]*', 'Osteosíntesis Encefálica'),
            (r'torn[illo]*\s*encefalic[oa]?[^\n]*', 'Tornillo Encefálico'),
            (r'placa\s*curv[ae]?nerv?[^\n]*', 'Placa CurvaNerv'),
            (r'pin\s*smartman[^\n]*', 'Pin Smartman'),
            (r'dispositivo[s]?\s+de\s+fijaci[óo]n[^\n]*', 'Dispositivo de Fijación'),
            (r'dispositivo[s]?\s+de\s+osteosintesis[^\n]*', 'Dispositivo de Osteosíntesis'),
            (r'fractura[s]?\s+[^\n]*', 'Manejo de Fracturas'),
            (r'fijaci[óo]n\s+[^\n]*', 'Fijación Quirúrgica'),
            (r'reducci[óo]n\s+[^\n]*', 'Reducción Quirúrgica'),
            (r'craneofacial[^\n]*', 'Cirugía Craneofacial'),
            (r'maxilofacial[^\n]*', 'Cirugía Maxilofacial'),
            (r'temporal[^\n]*fractura[^\n]*', 'Fractura Temporal'),
            (r'frontal[^\n]*fractura[^\n]*', 'Fractura Frontal'),
            (r'parietal[^\n]*fractura[^\n]*', 'Fractura Parietal'),
            (r'tornillo[s]?[^\n]*', 'Tornillos'),
            (r'placa[s]?[^\n]*', 'Placas'),
            (r'pin[es]?[^\n]*', 'Pines')
        ]
        
        for pattern, normalized_name in variants:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                if normalized_name not in supply_variants:
                    supply_variants[normalized_name] = set()
                clean_matches = [match.strip() for match in matches if len(match.strip()) > 3]
                supply_variants[normalized_name].update(clean_matches)
        
        for name, variant_set in supply_variants.items():
            if variant_set:
                supply = InsumoDescripcion()
                supply.nombre = name
                supply.variantes_denominacion = list(variant_set)
                supply.mencion_trazabilidad = self._check_traceability_mention_for_supply(text, name)
                supplies.append(supply)
        
        return supplies
    
    def _check_traceability_mention_for_supply(self, text: str, supply_name: str) -> bool:
        lines = text.split('\n')
        for line in lines:
            if supply_name.lower() in line.lower():
                if re.search(r'(REF|LOT|etiqueta|trazabilidad)', line, re.IGNORECASE):
                    return True
        return False
    
    def _extract_traceability_mentions(self, text: str) -> Dict[str, Any]:
        mentions = {}
        
        if re.search(r'REF[:\s]*\d+', text, re.IGNORECASE):
            mentions['menciona_ref'] = True
            mentions['refs_encontradas'] = re.findall(r'REF[:\s]*(\d+)', text, re.IGNORECASE)
        
        if re.search(r'LOT[:\s]*\d+', text, re.IGNORECASE):
            mentions['menciona_lot'] = True
            mentions['lots_encontrados'] = re.findall(r'LOT[:\s]*(\d+)', text, re.IGNORECASE)
        
        if re.search(r'etiqueta[s]?', text, re.IGNORECASE):
            mentions['menciona_etiquetas'] = True
        
        if re.search(r'trazabilidad', text, re.IGNORECASE):
            mentions['menciona_trazabilidad'] = True
        
        return mentions
    
    def _extract_complementary_data(self, text: str) -> Dict[str, Any]:
        data = {}
        
        date_patterns = [
            r'(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
            r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
            r'Fecha[:\s]+([^\n]+)',
            r'(\d{1,2}/\d{1,2}/\d{4})'
        ]
        
        for pattern in date_patterns:
            date_match = re.search(pattern, text, re.IGNORECASE)
            if date_match:
                data['fecha'] = date_match.group(1).strip()
                break
        
        patient_patterns = [
            r'paciente[:\s]+([A-Za-záéíóúñÑ\s]+?)(?:\n|$)',
            r'Nombre[:\s]+([A-Za-záéíóúñÑ\s]+?)(?:\n|$)',
            r'CC[:\s]+\d+[:\s]+([A-Za-záéíóúñÑ\s]+?)(?:\n|$)'
        ]
        
        for pattern in patient_patterns:
            patient_match = re.search(pattern, text, re.IGNORECASE)
            if patient_match:
                data['paciente'] = patient_match.group(1).strip()
                break
        
        doctor_patterns = [
            r'Médico\s+Tratante[:\s]+([A-Za-záéíóúñÑ\s\.]+?)(?:\n|$)',
            r'Cirujano[:\s]+([A-Za-záéíóúñÑ\s\.]+?)(?:\n|$)',
            r'Dr\.\s+([A-Za-záéíóúñÑ\s]+?)(?:\n|$)'
        ]
        
        for pattern in doctor_patterns:
            doctor_match = re.search(pattern, text, re.IGNORECASE)
            if doctor_match:
                data['medico_tratante'] = doctor_match.group(1).strip()
                break
        
        specialty_match = re.search(r'Especialidad[:\s]+([^\n]+)', text, re.IGNORECASE)
        if specialty_match:
            data['especialidad'] = specialty_match.group(1).strip()
        
        proc_codes = re.findall(r'T\d+[A-Z]*\d*', text)
        if proc_codes:
            data['codigos_procedimiento'] = proc_codes
        
        anesthesia_match = re.search(r'Tipo\s+de\s+anestesia[:\s]+([^\n]+)', text, re.IGNORECASE)
        if anesthesia_match:
            data['tipo_anestesia'] = anesthesia_match.group(1).strip()
        
        hospital_patterns = [
            r'HOSPITAL\s+([^\n]+)',
            r'Centro[:\s]+([^\n]+)',
            r'Institución[:\s]+([^\n]+)'
        ]
        
        for pattern in hospital_patterns:
            hospital_match = re.search(pattern, text, re.IGNORECASE)
            if hospital_match:
                data['centro_medico'] = hospital_match.group(1).strip()
                break
        
        return data


class SmartOCRProcessor:
    
    def __init__(self, ocr_client: OCRClient):
        self.ocr_client = ocr_client
        self.text_processor = MedicalTextProcessor()
        
        self.extractors = {
            1: ReporteInternoExtractor(self.text_processor),
            2: ReporteHospitalExtractor(self.text_processor),
            3: DescripcionQuirurgicaExtractor(self.text_processor)
        }
    
    def process(self, image_path: str, extraction_type: int, **kwargs) -> BaseModel:
        
        if extraction_type not in self.extractors:
            raise ValueError(f"Tipo de extracción no válido: {extraction_type}")
        
        raw_text = self.ocr_client.extract_text(image_path, **kwargs)
        
        extractor = self.extractors[extraction_type]
        result = extractor.extract(raw_text)
        
        return result


def load_api_key() -> str:
    load_dotenv()
    
    api_key = os.getenv('OCR_SPACE_API_KEY')
    if not api_key:
        raise ValueError("Falta OCR_SPACE_API_KEY en .env")
    
    return api_key


def main():
    parser = argparse.ArgumentParser(description='Smart OCR con extracción específica')
    parser.add_argument('image_path', help='Ruta a la imagen')
    parser.add_argument('--tipo', '-t', type=int, choices=[1, 2, 3], default=1,
                       help='Tipo extracción: 1=Interno, 2=Hospital, 3=Descripción')
    parser.add_argument('--output', '-o', help='Archivo de salida JSON')
    parser.add_argument('--language', '-l', default='spa', help='Idioma OCR')
    
    args = parser.parse_args()
    
    try:
        api_key = load_api_key()
        ocr_client = OCRSpaceClient(api_key)
        processor = SmartOCRProcessor(ocr_client)
        
        print(f"Procesando: {args.image_path}")
        print(f"Tipo de extracción: {args.tipo}")
        
        result = processor.process(
            args.image_path, 
            args.tipo,
            language=args.language
        )
        
        result_json = result.model_dump_json(indent=2)
        print("\n=== RESULTADO ===")
        print(result_json)
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(result_json)
            print(f"\nGuardado en: {args.output}")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
