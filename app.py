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

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

class ChatRequest(BaseModel):
    urteilsnummer: str
    frage: str

@app.post("/ask")
async def ask_bot(request: ChatRequest):
    raw_nr = request.urteilsnummer.strip()
    
    # 1. ScraperAPI Konfiguration
    # Wir holen den Key aus den Render-Umgebungsvariablen
    S_API_KEY = os.getenv("SCRAPER_API_KEY")
    
    # Die Ziel-URL beim Bundesgericht
    target_url = f"https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index.php?lang=de&type=highlight_simple_query&name={raw_nr}"
    
    # Die Proxy-URL, die die Anfrage verschleiert
    proxy_url = f"http://api.scraperapi.com?api_key={S_API_KEY}&url={target_url}"

    volltext = ""
    try:
        # Wir senden die Anfrage über den Proxy (Timeout auf 60s erhöhen, da Proxys Zeit brauchen)
        response = requests.get(proxy_url, timeout=60)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Bereinigung
        for element in soup(["script", "style", "nav", "header", "footer"]):
            element.decompose()
        
        text_candidate = soup.get_text(separator=' ', strip=True)
        
        # Prüfung auf Inhalt
        if any(x in text_candidate for x in ["Erwägung", "Considérant", "E."]):
            volltext = text_candidate
        else:
            return {"antwort": "Das Bundesgericht liefert über den Proxy aktuell keinen Volltext. Bitte prüfen Sie die Nummer."}

    except Exception as e:
        return {"antwort": f"Proxy-Fehler: {str(e)}"}

    # 2. Übergabe an Claude
    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
            temperature=0,
            system="Du bist ein präziser Schweizer Rechtsassistent. Antworte NUR auf Basis des bereitgestellten Textes. Nutze ss statt ß.",
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
