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
    nr = request.urteilsnummer.strip()
    # Direkte URL zum Volltext
    url = f"https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index.php?lang=de&type=highlight_simple_query&query_words=&name={nr}"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Bereinigung des HTML-Mülls
        for element in soup(["script", "style", "nav", "header", "footer"]):
            element.decompose()
            
        volltext = soup.get_text(separator=' ', strip=True)
        
        if len(volltext) < 500:
            return {"antwort": "Fehler: Der Volltext des Urteils konnte nicht geladen werden. Bitte prüfen Sie die Nummer."}

        # JETZT MIT DER AKTUELLEN MODELL-ID AUS DEINEM SCREENSHOT
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
            temperature=0,
            system="""Du bist ein spezialisierter Schweizer Rechtsassistent. 
            DIR LIEGT DER VOLLTEXT DES URTEILS UNTEN VOR. 
            
            STRIKTE REGELN:
            1. Antworte NUR auf Basis des bereitgestellten Textes.
            2. Wenn die Info nicht im Text steht, sage: 'Dazu macht das Bundesgericht keine Angaben.'
            3. Erfinde niemals Details (keine Halluzinationen!).
            4. Suche aktiv nach Erwägungen (E.) und Quellen-Links (z.B. Charité).
            5. Nutze 'ss' statt 'ß'.""",
            messages=[
                {"role": "user", "content": f"Hier ist der Volltext zum Urteil {nr}:\n\n{volltext}\n\nFrage: {request.frage}"}
            ]
        )
        return {"antwort": message.content[0].text}
        
    except Exception as e:
        return {"antwort": f"Technischer Fehler: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
