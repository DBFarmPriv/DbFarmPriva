from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
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
            # Render utilise Linux, on prend donc le binaire Linux
            if "linux" in asset['name'].lower() and asset['name'].endswith('.zip'):
                download_url = asset['browser_download_url']
                break
        if download_url:
            r = requests.get(download_url)
            z = zipfile.ZipFile(io.BytesIO(r.content))
            z.extractall(output_folder)
            executable_path = os.path.join(output_folder, "Il2CppDumper")
            if os.path.exists(executable_path):
                os.chmod(executable_path, 0o755)
    except Exception as e:
        print(f"Erreur téléchargement dumper : {e}")

def run_dumper_and_parse(executable_bin, metadata_dat, output_dir="output"):
    """Exécute Il2CppDumper et extrait les adresses sous forme de dictionnaire"""
    command = [
        "./il2cppdumper/Il2CppDumper", 
        executable_bin, 
        metadata_dat, 
        output_dir
    ]
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
                    clean_offsets[name] = hex(address)
            return clean_offsets
    return None

# --- INTERFACE WEB EN HTML (S'affiche sur ton téléphone) ---
@app.get("/", response_class=HTMLResponse)
def read_root():
    html_content = """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>IL2CPP Cloud Dumper</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #121212;
                color: #e0e0e0;
                margin: 0;
                padding: 20px;
                display: flex;
                flex-direction: column;
                align-items: center;
            }
            .container {
                max-width: 600px;
                width: 100%;
                background: #1e1e1e;
                padding: 30px;
                border-radius: 12px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.5);
                box-sizing: border-box;
            }
            h1 { text-align: center; color: #00ff66; margin-bottom: 25px; }
            .form-group { margin-bottom: 20px; }
            label { display: block; margin-bottom: 8px; font-weight: bold; color: #aaa; }
            input[type="file"] {
                width: 100%;
                padding: 10px;
                background: #2d2d2d;
                border: 1px dashed #444;
                color: #fff;
                border-radius: 6px;
                box-sizing: border-box;
            }
            button {
                width: 100%;
                padding: 12px;
                background: #00ff66;
                color: #121212;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                font-weight: bold;
                cursor: pointer;
                transition: background 0.2s;
                margin-top: 10px;
            }
            button:hover { background: #00cc52; }
            #loading { display: none; text-align: center; color: #00bcff; font-weight: bold; margin-top: 15px; }
            #result {
                margin-top: 25px;
                background: #0d0d0d;
                padding: 15px;
                border-radius: 6px;
                border: 1px solid #333;
                max-height: 400px;
                overflow-y: auto;
                display: none;
                white-space: pre-wrap;
                font-family: monospace;
                font-size: 13px;
                color: #00ff66;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>IL2CPP Dumper Cloud</h1>
            <form id="dumpForm">
                <div class="form-group">
                    <label>Fichier Binaire (libil2cpp.so ou .dll) :</label>
                    <input type="file" id="binaryFile" required>
                </div>
                <div class="form-group">
                    <label>Fichier Metadata (global-metadata.dat) :</label>
                    <input type="file" id="metadataFile" required>
                </div>
                <button type="submit">Lancer le Dump Automatique</button>
            </form>
            <div id="loading">Traitement en cours sur Render... (Patienter environ 10-30s)</div>
            <pre id="result"></pre>
        </div>

        <script>
            document.getElementById('dumpForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const binary = document.getElementById('binaryFile').files[0];
                const metadata = document.getElementById('metadataFile').files[0];
                const loading = document.getElementById('loading');
                const resultBlock = document.getElementById('result');
                
                const formData = new FormData();
                formData.append('binary', binary);
                formData.append('metadata', metadata);
                
                loading.style.display = 'block';
                resultBlock.style.display = 'none';
                
                try {
                    // Envoi en arrière-plan vers l'API Python
                    const response = await fetch('/api/v1/dump', {
                        method: 'POST',
                        body: formData
                    });
                    const resData = await response.json();
                    loading.style.display = 'none';
                    resultBlock.style.display = 'block';
                    
                    if (resData.status === 'success') {
                        resultBlock.textContent = JSON.stringify(resData.data, null, 2);
                        resultBlock.style.color = '#00ff66';
                    } else {
                        resultBlock.textContent = 'Erreur: ' + resData.message;
                        resultBlock.style.color = '#ff3333';
                    }
                } catch (err) {
                    loading.style.display = 'none';
                    resultBlock.style.display = 'block';
                    resultBlock.textContent = 'Erreur réseau ou fichier trop volumineux pour Render.';
                    resultBlock.style.color = '#ff3333';
                }
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)

# --- BACKEND API (Traitement des fichiers) ---
@app.post("/api/v1/dump")
async def upload_and_dump(
    binary: UploadFile = File(...), 
    metadata: UploadFile = File(...)
):
    bin_path = f"temp_{binary.filename}"
    meta_path = f"temp_{metadata.filename}"
    
    with open(bin_path, "wb") as buffer:
        shutil.copyfileobj(binary.file, buffer)
    with open(meta_path, "wb") as buffer:
        shutil.copyfileobj(metadata.file, buffer)
        
    download_latest_il2cppdumper()
    offsets = run_dumper_and_parse(bin_path, meta_path)
    
    # Nettoyage automatique pour préserver l'espace disque sur Render
    if os.path.exists(bin_path): os.remove(bin_path)
    if os.path.exists(meta_path): os.remove(meta_path)
    if os.path.exists("output"): shutil.rmtree("output")
    
    if offsets:
        return {"status": "success", "data": offsets}
    return {"status": "error", "message": "Le dump a échoué. Vérifie la validité des fichiers."}
    
