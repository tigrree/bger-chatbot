from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic
import requests
from bs4 import BeautifulSoup
import os

app = FastAPI()

# CORS-Einstellungen für die Kommunikation mit deiner Webseite
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialisierung der API-Keys aus den Render-Umgebungsvariablen
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
SCRAPER_KEY = os.getenv("SCRAPER_API_KEY")

client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

class ChatRequest(BaseModel):
    urteilsnummer: str
    frage: str

@app.post("/ask")
async def ask_bot(request: ChatRequest):
    if not SCRAPER_KEY:
        return {"antwort": "Konfigurationsfehler: SCRAPER_API_KEY fehlt in Render."}
        
    raw_nr = request.urteilsnummer.strip()
    
    # Ziel-URL beim Bundesgericht
    target_url = f"https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index.php?lang=de&type=highlight_simple_query&name={raw_nr}"
    
    # ScraperAPI-URL mit JS-Rendering und Premium-Proxys (Residential IPs)
    proxy_url = f"http://api.scraperapi.com?api_key={SCRAPER_KEY}&url={target_url}&render=true&premium=true"

    volltext = ""
    try:
        # Abruf über den Proxy mit erhöhtem Timeout
        response = requests.get(proxy_url, timeout=90)
        
        if response.status_code == 401:
            return {"antwort": "Fehler 401: Ungültiger ScraperAPI-Key. Bitte Key in Render prüfen."}
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # HTML-Bereinigung (Skripte und Navigation entfernen)
        for element in soup(["script", "style", "nav", "header", "footer"]):
            element.decompose()
        
        volltext = soup.get_text(separator=' ', strip=True)
        
    except Exception as e:
        return {"antwort": f"Verbindungsfehler zum Proxy: {str(e)}"}

    # Prüfung, ob tatsächlich ein Urteil gefunden wurde
    if not volltext or len(volltext) < 600:
        return {"antwort": "Das Bundesgericht hat den automatischen Zugriff blockiert oder das Urteil nicht gefunden."}

    # KI-Analyse durch Claude 3.5 Sonnet
    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3500,
            temperature=0,
            system="Du bist ein spezialisierter Schweizer Rechtsassistent. Antworte PRÄZISE und NUR auf Basis des bereitgestellten Urteilstextes. Nutze Schweizer Rechtschreibung (ss statt ß).",
            messages=[
                {"role": "user", "content": f"Urteil: {raw_nr}\n\nText:\n{volltext}\n\nFrage: {request.frage}"}
            ]
        )
        return {"antwort": message.content[0].text}
    except Exception as e:
        return {"antwort": f"Fehler bei der KI-Analyse: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)