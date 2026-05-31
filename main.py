from fastapi import FastAPI, UploadFile, File
import requests
import zipfile
import io
import os
import shutil
import subprocess
import json

app = FastAPI()

def download_latest_il2cppdumper(output_folder="il2cppdumper"):
    """Télécharge la dernière version Linux d'Il2CppDumper depuis GitHub"""
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    api_url = "https://api.github.com/repos/Perfare/Il2CppDumper/releases/latest"
    try:
        response = requests.get(api_url).json()
        download_url = None
        for asset in response.get('assets', []):
            # Render utilise des serveurs Linux, on cible donc le binaire Linux
            if "linux" in asset['name'].lower() and asset['name'].endswith('.zip'):
                download_url = asset['browser_download_url']
                break
                
        if download_url:
            r = requests.get(download_url)
            z = zipfile.ZipFile(io.BytesIO(r.content))
            z.extractall(output_folder)
            
            # Donne les droits d'exécution au fichier binaire sur le serveur Linux
            executable_path = os.path.join(output_folder, "Il2CppDumper")
            if os.path.exists(executable_path):
                os.chmod(executable_path, 0o755)
    except Exception as e:
        print(f"Erreur téléchargement dumper : {e}")

def run_dumper_and_parse(executable_bin, metadata_dat, output_dir="output"):
    """Exécute le dumper et extrait les adresses (offsets) du fichier script.json"""
    command = [
        "./il2cppdumper/Il2CppDumper", 
        executable_bin, 
        metadata_dat, 
        output_dir
    ]
    
    # Lance le processus en arrière-plan sur Render
    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    if process.returncode == 0:
        script_json_path = os.path.join(output_dir, "script.json")
        if os.path.exists(script_json_path):
            with open(script_json_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                
            clean_offsets = {}
            for method in data.get("ScriptMethod", []):
                name = method.get("Name")
                address = method.get("Address")
                if name and address is not None:
                    clean_offsets[name] = hex(address) # Convertit l'adresse en hexadécimal (ex: 0x1a2b)
            return clean_offsets
    return None

@app.get("/")
def read_root():
    return {
        "statut": "Serveur opérationnel", 
        "message": "Bienvenue sur l'API de diagnostic et de Reverse Engineering !"
    }

@app.post("/api/v1/dump")
async def upload_and_dump(
    binary: UploadFile = File(...), 
    metadata: UploadFile = File(...)
):
    # Noms temporaires pour stocker les fichiers envoyés par ton mobile
    bin_path = f"temp_{binary.filename}"
    meta_path = f"temp_{metadata.filename}"
    
    with open(bin_path, "wb") as buffer:
        shutil.copyfileobj(binary.file, buffer)
    with open(meta_path, "wb") as buffer:
        shutil.copyfileobj(metadata.file, buffer)
        
    # Exécution de la logique automatique
    download_latest_il2cppdumper()
    offsets = run_dumper_and_parse(bin_path, meta_path)
    
    # Nettoyage strict des fichiers pour ne pas saturer le serveur gratuit de Render
    if os.path.exists(bin_path): os.remove(bin_path)
    if os.path.exists(meta_path): os.remove(meta_path)
    if os.path.exists("output"): shutil.rmtree("output")
    
    if offsets:
        return {"status": "success", "data": offsets}
    return {"status": "error", "message": "Le dump automatique a échoué. Vérifie la validité de tes deux fichiers."}
