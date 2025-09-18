import subprocess
import sys
import os
from pathlib import Path

def create_venv():
    print("Creando entorno virtual...")
    try:
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print("✓ Entorno virtual creado")
        return True
    except subprocess.CalledProcessError:
        print("✗ Error creando entorno virtual")
        return False

def check_venv():
    venv_path = Path("venv")
    if not venv_path.exists():
        print("No se encontró el entorno virtual")
        return create_venv()
    return True

def create_env_file():
    print("Creando archivo .env...")
    api_key = input("Ingresa tu OCR_SPACE_API_KEY (o presiona Enter para usar clave de ejemplo): ").strip()
    
    if not api_key:
        api_key = "K88945205088957"
        print("Usando API key de ejemplo")
    
    try:
        with open(".env", "w") as f:
            f.write(f"OCR_SPACE_API_KEY={api_key}\n")
        print("✓ Archivo .env creado")
        return True
    except Exception as e:
        print(f"✗ Error creando .env: {e}")
        return False

def check_env_file():
    env_path = Path(".env")
    if not env_path.exists():
        print("No se encontró el archivo .env")
        return create_env_file()
    return True

def check_dependencies():
    try:
        import streamlit
        import pandas  
        import requests
        import pydantic
        from dotenv import load_dotenv
        return True
    except ImportError as e:
        print(f"Error: Faltan dependencias - {e}")
        print("Instala con: pip install streamlit pandas requests pydantic python-dotenv")
        return False

def start_interface():
    print("Smart OCR - Extractor Médico")
    print("=" * 40)
    
    if not check_venv():
        return 1
    
    if not check_env_file():
        return 1
        
    print("Verificando dependencias...")
    
    venv_python = "venv/bin/python" if os.name != 'nt' else "venv\\Scripts\\python.exe"
    
    try:
        result = subprocess.run([venv_python, "-c", 
            "import streamlit, pandas, requests, pydantic; from dotenv import load_dotenv"], 
            capture_output=True, text=True)
        
        if result.returncode != 0:
            print("Faltan dependencias en el entorno virtual")
            print("Instalando dependencias desde requirements.txt...")
            
            pip_cmd = "venv/bin/pip" if os.name != 'nt' else "venv\\Scripts\\pip.exe"
            
        
            if Path("requirements.txt").exists():
                install_result = subprocess.run([pip_cmd, "install", "-r", "requirements.txt"], 
                                               capture_output=True, text=True)
                if install_result.returncode == 0:
                    print("✓ Dependencias instaladas correctamente")
                else:
                    print("✗ Error instalando dependencias:")
                    print(install_result.stderr)
                    return 1
            else:
                print("Instalando dependencias individuales...")
                packages = ["streamlit>=1.28.0", "pandas>=2.0.0", "requests>=2.31.0", 
                           "pydantic>=2.0.0", "python-dotenv>=1.0.0", "openpyxl>=3.1.0"]
                
                for package in packages:
                    print(f"Instalando {package}...")
                    subprocess.run([pip_cmd, "install", package])
            
    except FileNotFoundError:
        print("Error: No se pudo acceder al entorno virtual")
        return 1
    
    print("Iniciando interfaz web...")
    print("URL: http://localhost:8501")
    print("Para detener: Ctrl+C")
    print("-" * 40)
    
    try:
        streamlit_cmd = "venv/bin/streamlit" if os.name != 'nt' else "venv\\Scripts\\streamlit.exe"
        subprocess.run([streamlit_cmd, "run", "interfaz_ocr.py"], check=True)
    except KeyboardInterrupt:
        print("\nInterfaz detenida por el usuario")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"Error al ejecutar la interfaz: {e}")
        return 1
    except FileNotFoundError:
        print("Error: Streamlit no está instalado correctamente")
        return 1

def show_help():
    print("Smart OCR - Extractor Médico")
    print("=" * 40)
    print("Sistema inteligente de extracción y análisis de documentos médicos")
    print()
    print("INSTALACIÓN AUTOMÁTICA:")
    print("  python3 main.py              - Instalación completa automática")
    print()
    print("COMANDOS:")
    print("  start, run                   - Iniciar la interfaz web")
    print("  status                       - Verificar estado del sistema")
    print("  help, -h                     - Mostrar esta ayuda")
    print("  install                      - Forzar reinstalación de dependencias")
    print()
    print("ARCHIVOS DEL SISTEMA:")
    print("  requirements.txt             - Lista de dependencias")
    print("  .env                         - API key de OCR.space")
    print("  venv/                        - Entorno virtual de Python")
    print("  smart_ocr.py                 - Motor de extracción OCR")
    print("  interfaz_ocr.py              - Interfaz web Streamlit")
    print("  analizador_discrepancias.py  - Análisis independiente")
    print()
    print("TIPOS DE DOCUMENTOS:")
    print("  Tipo 1: Reporte Interno     - Con trazabilidad completa (REF/LOT)")
    print("  Tipo 2: Reporte Hospital    - Sin trazabilidad, datos básicos")
    print("  Tipo 3: Descripción Médica  - Narrativa científica detallada")
    print()
    print("FUNCIONALIDADES:")
    print("  • Extracción OCR inteligente por tipo de documento")
    print("  • Procesamiento múltiple simultáneo (hasta 3 documentos)")
    print("  • Análisis automático de discrepancias entre documentos")
    print("  • Sistema de alertas por criticidad (ALTA/MEDIA/BAJA)")
    print("  • Interfaz web interactiva con métricas en tiempo real")
    print("  • Exportación de resultados en JSON y Excel")
    print()
    print("PRIMER USO:")
    print("  1. python3 main.py           - Instalación automática")
    print("  2. Ingresar API key          - OCR.space (o usar ejemplo)")
    print("  3. Abrir http://localhost:8501 - Interfaz web")
    print("  4. Subir documentos médicos  - PNG/JPG/PDF")
    print("  5. Ver análisis automático   - Discrepancias y métricas")
    print()
    print("SOPORTE:")
    print("  README.md                    - Documentación completa")
    print("  python3 main.py status       - Diagnóstico del sistema")

def check_status():
    print("Smart OCR - Estado del Sistema")
    print("=" * 40)
    
    status = True
    
    if check_venv():
        print("✓ Entorno virtual: OK")
    else:
        print("✗ Entorno virtual: FALTA")
        status = False
        
    if check_env_file():
        print("✓ Archivo .env: OK")
    else:
        print("✗ Archivo .env: FALTA")
        status = False
    
    required_files = ["smart_ocr.py", "interfaz_ocr.py"]
    for file in required_files:
        if Path(file).exists():
            print(f"✓ {file}: OK")
        else:
            print(f"✗ {file}: FALTA")
            status = False
    
    venv_python = "venv/bin/python" if os.name != 'nt' else "venv\\Scripts\\python.exe"
    try:
        result = subprocess.run([venv_python, "-c", 
            "import streamlit, pandas, requests, pydantic; from dotenv import load_dotenv"], 
            capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✓ Dependencias: OK")
        else:
            print("✗ Dependencias: FALTAN")
            status = False
    except:
        print("✗ Dependencias: ERROR")
        status = False
    
    print("-" * 40)
    if status:
        print("Sistema listo para usar")
        print("Ejecuta: python main.py start")
    else:
        print("Sistema requiere configuración")
    
    return 0 if status else 1

def force_install():
    print("Smart OCR - Instalación Forzada")
    print("=" * 40)
    
    if not check_venv():
        return 1
    
    print("Reinstalando todas las dependencias...")
    pip_cmd = "venv/bin/pip" if os.name != 'nt' else "venv\\Scripts\\pip.exe"
    
    try:
        if Path("requirements.txt").exists():
            print("Instalando desde requirements.txt...")
            result = subprocess.run([pip_cmd, "install", "--upgrade", "-r", "requirements.txt"], 
                                   capture_output=True, text=True)
            if result.returncode == 0:
                print("✓ Todas las dependencias reinstaladas")
            else:
                print("✗ Error en la instalación:")
                print(result.stderr)
                return 1
        else:
            print("requirements.txt no encontrado, instalando dependencias básicas...")
            packages = ["streamlit>=1.28.0", "pandas>=2.0.0", "requests>=2.31.0", 
                       "pydantic>=2.0.0", "python-dotenv>=1.0.0", "openpyxl>=3.1.0"]
            
            for package in packages:
                print(f"Instalando {package}...")
                subprocess.run([pip_cmd, "install", "--upgrade", package], check=True)
            
            print("✓ Dependencias básicas instaladas")
        
        return 0
        
    except subprocess.CalledProcessError as e:
        print(f"✗ Error durante la instalación: {e}")
        return 1
    except Exception as e:
        print(f"✗ Error inesperado: {e}")
        return 1

def main():
    if len(sys.argv) < 2:
        return start_interface()
    
    command = sys.argv[1].lower()
    
    if command in ['start', 'run']:
        return start_interface()
    elif command in ['help', '-h', '--help']:
        show_help()
        return 0
    elif command == 'status':
        return check_status()
    elif command == 'install':
        return force_install()
    else:
        print(f"Comando desconocido: {command}")
        print("Comandos disponibles: start, status, help, install")
        print("Usa 'python3 main.py help' para ver información completa")
        return 1

if __name__ == "__main__":
    exit(main())
