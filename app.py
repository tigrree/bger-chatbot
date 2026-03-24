from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic
import requests
from bs4 import BeautifulSoup
import os
import time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
SCRAPER_KEY = os.getenv("SCRAPER_API_KEY")

class ChatRequest(BaseModel):
    urteilsnummer: str
    frage: str

@app.post("/ask")
async def ask_bot(request: ChatRequest):
    if not SCRAPER_KEY:
        return {"antwort": "Konfigurationsfehler: SCRAPER_API_KEY fehlt."}
        
    raw_nr = request.urteilsnummer.strip()
    
    # Wir versuchen zwei verschiedene URL-Formate des Bundesgerichts
    urls_to_try = [
        f"https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index.php?lang=de&type=highlight_simple_query&name={raw_nr}",
        f"https://search.bger.ch/index.php?lang=de&type=show_document&name={raw_nr}"
    ]

    volltext = ""
    
    for target_url in urls_to_try:
        # ScraperAPI mit render=true ist hier entscheidend
        proxy_url = f"http://api.scraperapi.com?api_key={SCRAPER_KEY}&url={target_url}&render=true&premium=true&country_code=ch"
        
        try:
            response = requests.get(proxy_url, timeout=120) # Mehr Zeit für Schweizer IPs
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Wir löschen den Müll
                for element in soup(["script", "style", "nav", "header", "footer"]):
                    element.decompose()
                
                text_candidate = soup.get_text(separator=' ', strip=True)
                
                # Validierung: Finden wir Urteils-Merkmale?
                if any(x in text_candidate for x in ["Erwägung", "Considérant", "E."]):
                    volltext = text_candidate
                    break # Erfolg!
        except Exception:
            continue # Nächste URL versuchen

    if not volltext or len(volltext) < 800:
        return {"antwort": "Das Bundesgericht blockiert den Zugriff weiterhin hartnäckig. Bitte stellen Sie sicher, dass die Nummer (z.B. 9C_512/2024) absolut korrekt ist. Falls ja, ist der Server in Lausanne gerade überlastet."}

    # KI-Analyse
    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3500,
            temperature=0,
            system="Du bist ein spezialisierter Schweizer Rechtsassistent. Antworte PRÄZISE und NUR auf Basis des bereitgestellten Textes. Nutze ss statt ß.",
            messages=[{"role": "user", "content": f"Urteil: {raw_nr}\n\nText:\n{volltext}\n\nFrage: {request.frage}"}]
        )
        return {"antwort": message.content[0].text}
    except Exception as e:
        return {"antwort": f"Fehler bei Claude: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)