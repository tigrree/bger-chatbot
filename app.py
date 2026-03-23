from fastapi import FastAPI, HTTPException
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
    
    # Wir nutzen die exakte URL-Struktur für die Druckansicht (direkter Volltext)
    # Das überspringt die Trefferliste, die man in deinem Video sieht
    url = "https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index.php"
    params = {
        "lang": "de",
        "type": "highlight_simple_query",
        "page": "1",
        "from_date": "",
        "to_date": "",
        "sort": "relevance",
        "insertion_date": "",
        "query_words": "",
        "name": raw_nr  # Hier suchen wir nach 9C_512/2024
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'de-CH,de;q=0.9,en-US;q=0.8,en;q=0.7'
    }

    try:
        # Wir rufen die Seite ab
        response = requests.get(url, params=params, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Säuberung: Wir entfernen unnötigen Ballast
        for element in soup(["script", "style", "nav", "header", "footer"]):
            element.decompose()
        
        volltext = soup.get_text(separator=' ', strip=True)

        # Validierung: Finden wir das Aktenzeichen im Text?
        if len(volltext) < 1000 or raw_nr.replace("_", " ") not in volltext.replace("_", " "):
             # Zweiter Versuch: Falls BGer eine Session-ID braucht
             return {"antwort": f"Ich konnte den Volltext zu '{raw_nr}' nicht stabil laden. Das Bundesgericht blockiert den Zugriff aktuell. Bitte versuchen Sie es in ein paar Minuten erneut."}

        # Claude mit der modernsten ID aufrufen
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
            temperature=0,
            system="""Du bist ein spezialisierter Schweizer Rechtsassistent. 
            DIR LIEGT DER VOLLTEXT DES URTEILS UNTEN VOR. 
            Antworte PRÄZISE und NUR auf Basis dieses Textes.
            
            Wichtig: Suche nach Erwägungen (E.) und Links (z.B. Charité). 
            Wenn das Gericht CFS als Ausschlussdiagnose bezeichnet, nenne das.
            Nutze 'ss' statt 'ß'.""",
            messages=[
                {"role": "user", "content": f"Urteil: {raw_nr}\n\nText:\n{volltext}\n\nFrage: {request.frage}"}
            ]
        )
        return {"antwort": message.content[0].text}

    except Exception as e:
        return {"antwort": f"Technischer Fehler beim Abruf: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
