from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"statut": "Serveur opérationnel", "message": "Bienvenue sur l'API de diagnostic"}
  
