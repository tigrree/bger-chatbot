from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic
import requests
from bs4 import BeautifulSoup
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
SCRAPER_KEY = os.getenv("SCRAPER_API_KEY")

client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

class ChatRequest(BaseModel):
    urteilsnummer: str
    frage: str

@app.post("/ask")
async def ask_bot(request: ChatRequest):
    if not SCRAPER_KEY:
        return {"antwort": "Konfigurationsfehler: SCRAPER_API_KEY fehlt."}
        
    # Nummer bereinigen (9C_512/2024)
    raw_nr = request.urteilsnummer.strip()
    
    # Direkte Such-URL
    target_url = f"https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index.php?lang=de&type=highlight_simple_query&name={raw_nr}"
    
    # Wir nutzen den Proxy OHNE render=true, um den Status 500 zu vermeiden.
    # Wir fügen aber keep_headers=true hinzu, um wie ein echter Browser zu wirken.
    proxy_url = f"http://api.scraperapi.com?api_key={SCRAPER_KEY}&url={target_url}&keep_headers=true"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }

    volltext = ""
    try:
        # Timeout auf 45s, um ScraperAPI Zeit zu geben
        response = requests.get(proxy_url, headers=headers, timeout=45)
        
        if response.status_code != 200:
            return {"antwort": f"Der Proxy-Dienst meldet Fehler {response.status_code}. Bitte versuchen Sie es in 1 Minute erneut."}
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Falls das BGer eine Trefferliste zeigt, versuchen wir den ersten Link zu finden
        # oder direkt den Body-Text zu extrahieren
        for element in soup(["script", "style", "nav", "header", "footer"]):
            element.decompose()
            
        volltext = soup.get_text(separator=' ', strip=True)
        
    except Exception as e:
        return {"antwort": f"Verbindungsfehler: {str(e)}"}

    # Prüfen, ob wir Text gefunden haben
    if not volltext or len(volltext) < 500:
        return {"antwort": "Volltext-Extraktion fehlgeschlagen. Das Bundesgericht blockiert den automatischen Abruf. Bitte kopieren Sie den Text manuell in das Feld."}

    # KI-Analyse
    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3500,
            temperature=0,
            system="Du bist ein spezialisierter Schweizer Rechtsassistent. Antworte PRÄZISE und NUR auf Basis des bereitgestellten Urteilstextes. Nutze ss statt ß.",
            messages=[
                {"role": "user", "content": f"Urteil: {raw_nr}\n\nText:\n{volltext}\n\nFrage: {request.frage}"}
            ]
        )
        return {"antwort": message.content[0].text}
    except Exception as e:
        return {"antwort": f"Claude-Fehler: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
