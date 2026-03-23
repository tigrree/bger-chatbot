from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic
import requests
from bs4 import BeautifulSoup
import os
import re

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
    
    # Wir nutzen die URL-Logik, die auch beim Scraper funktioniert
    # Diese steuert direkt die strukturierte Inhaltsseite an
    url = f"https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index.php?lang=de&type=highlight_simple_query&query_words=&name={raw_nr}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        # Abruf mit 30 Sekunden Geduld (analog zum Scraper-Verhalten bei vielen Anfragen)
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Wir entfernen Navigation und technische Skripte
        for hidden in soup(["script", "style", "nav", "header", "footer"]):
            hidden.decompose()
        
        # Extraktion des Haupttextes
        # Wir suchen gezielt nach den Inhalts-Containern des Bundesgerichts
        content = soup.find('div', class_='content') or soup.find('body')
        volltext = content.get_text(separator=' ', strip=True)

        # Sicherheitscheck: Falls der Text zu kurz ist oder das AZ fehlt
        if len(volltext) < 800:
            return {"antwort": f"Ich konnte den Volltext zu '{raw_nr}' nicht extrahieren. Das Bundesgericht liefert aktuell keine Daten für diese Anfrage. Bitte versuchen Sie es gleich noch einmal."}

        # Claude 3.5 Sonnet (4-6) mit dem echten Text füttern
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3500,
            temperature=0,
            system="""Du bist ein spezialisierter Schweizer Rechtsassistent. 
            DIR LIEGT DER VOLLTEXT DES URTEILS UNTEN VOR. 
            Beantworte die Frage PRÄZISE und NUR auf Basis dieses Textes.
            
            REGELN:
            1. Nenne konkrete Erwägungen (z.B. E. 4.2).
            2. Achte auf medizinische Quellen oder Weblinks (z.B. Charité), falls erwähnt.
            3. Falls die Information NICHT im Text steht, sage es deutlich.
            4. Nutze konsequent 'ss' statt 'ß'.""",
            messages=[
                {"role": "user", "content": f"Urteil: {raw_nr}\n\nInhalt:\n{volltext}\n\nFrage: {request.frage}"}
            ]
        )
        return {"antwort": message.content[0].text}

    except requests.exceptions.Timeout:
        return {"antwort": "Das Bundesgericht hat zu langsam geantwortet (Timeout). Bitte versuchen Sie es in ein paar Sekunden erneut."}
    except Exception as e:
        return {"antwort": f"Fehler beim Text-Abruf: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
