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
    S_API_KEY = os.getenv("SCRAPER_API_KEY")
    
    # 1. OPTIMIERTE PROXY-URL
    # render=true simuliert einen echten Browser
    # premium=true nutzt hochwertige IP-Adressen (Residential)
    target_url = f"https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index.php?lang=de&type=highlight_simple_query&name={raw_nr}"
    proxy_url = f"http://api.scraperapi.com?api_key={S_API_KEY}&url={target_url}&render=true&premium=true"

    volltext = ""
    try:
        # Erhöhtes Timeout auf 90s, da Rendering und Premium-Proxys Zeit brauchen
        response = requests.get(proxy_url, timeout=90)
        
        if response.status_code != 200:
            return {"antwort": f"Fehler vom Proxy-Dienst (Status {response.status_code}). Bitte ScraperAPI-Guthaben prüfen."}

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Reinigung: Alles Unnötige entfernen
        for element in soup(["script", "style", "nav", "header", "footer", "iframe"]):
            element.decompose()
        
        # Wir suchen gezielt im Hauptbereich der BGer Seite
        text_candidate = soup.get_text(separator=' ', strip=True)
        
        # Strenge Prüfung auf Inhalt
        if any(x in text_candidate for x in ["Erwägung", "Considérant", "Considerando", "E."]):
            volltext = text_candidate
        else:
            return {"antwort": "Der Text konnte geladen werden, scheint aber kein Urteil zu sein. Bitte Nummer prüfen."}

    except Exception as e:
        return {"antwort": f"Proxy-Verbindungsfehler: {str(e)}"}

    # 2. ÜBERGABE AN CLAUDE
    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3500,
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
