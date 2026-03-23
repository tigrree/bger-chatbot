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
    # Bereinigung der Nummer für die Suche
    raw_nr = request.urteilsnummer.strip()
    # Wir versuchen zwei Varianten: 9C_512/2024 und 9C 512/2024
    search_variants = [raw_nr, raw_nr.replace("_", " ")]
    
    volltext = ""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    for variant in search_variants:
        url = f"https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index.php?lang=de&type=highlight_simple_query&query_words=&name={variant}"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Wir suchen den Hauptinhalt
            for element in soup(["script", "style", "nav", "header", "footer"]):
                element.decompose()
            
            text_candidate = soup.get_text(separator=' ', strip=True)
            
            # Ein echtes Urteil hat immer Erwägungen (E. 1, E. 2 etc.)
            if "Erwägung" in text_candidate or "Considérant" in text_candidate or "E." in text_candidate:
                volltext = text_candidate
                break
        except:
            continue

    if len(volltext) < 800:
        return {"antwort": f"Ich konnte den Text zum Urteil '{raw_nr}' leider nicht direkt beim Bundesgericht abrufen. Bitte stellen Sie sicher, dass die Nummer exakt stimmt (z.B. 9C_512/2024)."}

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
            temperature=0,
            system="""Du bist ein spezialisierter Schweizer Rechtsassistent. 
            DIR LIEGT DER VOLLTEXT DES URTEILS UNTEN VOR. 
            Beantworte die Frage PRÄZISE und NUR auf Basis des bereitgestellten Textes.
            
            REGELN:
            1. Wenn die Info nicht im Text steht, sage es offen.
            2. Erwähne Links (z.B. Charité) und Erwägungen (E. X).
            3. Nutze 'ss' statt 'ß'.""",
            messages=[
                {"role": "user", "content": f"Urteil {raw_nr}:\n\n{volltext}\n\nFrage: {request.frage}"}
            ]
        )
        return {"antwort": message.content[0].text}
    except Exception as e:
        return {"antwort": f"Claude-Fehler: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
