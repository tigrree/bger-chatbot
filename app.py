from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic
import requests
from bs4 import BeautifulSoup
import os
import time

app = FastAPI()

# Erlaubt die Kommunikation mit deiner Webseite
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialisierung des Anthropic-Clients mit deinem API-Key von Render
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

class ChatRequest(BaseModel):
    urteilsnummer: str
    frage: str

@app.post("/ask")
async def ask_bot(request: ChatRequest):
    raw_nr = request.urteilsnummer.strip()
    # Wir nutzen die URL, die direkt auf die Datenbank-Abfrage zielt
    url = "https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index.php"
    params = {
        "lang": "de",
        "type": "highlight_simple_query",
        "page": "1",
        "sort": "relevance",
        "name": raw_nr
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9'
    }

    volltext = ""
    # Zwei Versuche bei Timeouts
    for attempt in range(2):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Unnötigen HTML-Ballast entfernen
            for element in soup(["script", "style", "nav", "header", "footer"]):
                element.decompose()
            
            text_candidate = soup.get_text(separator=' ', strip=True)
            
            # Validierung: Enthält der Text typische Urteils-Elemente?
            if any(x in text_candidate for x in ["Erwägung", "Considérant", "Considerando", "E."]):
                volltext = text_candidate
                break
            
            if attempt == 0: time.sleep(2)
        except Exception:
            if attempt == 0: time.sleep(2)
            continue

    if len(volltext) < 800:
        return {"antwort": "Fehler: Der Volltext konnte nicht extrahiert werden. Das Bundesgericht blockiert aktuell den Zugriff oder die Seite ist überlastet."}

    try:
        # Aufruf von Claude 3.5 Sonnet (Version 4-6)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
            temperature=0,
            system="""Du bist ein präziser Schweizer Rechtsassistent. 
            Beantworte die Frage des Nutzers PRÄZISE und NUR auf Basis des bereitgestellten Textes.
            Nutze 'ss' statt 'ß'.""",
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
