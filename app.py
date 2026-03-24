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
        return {"antwort": "Konfigurationsfehler: SCRAPER_API_KEY fehlt in Render."}
        
    raw_nr = request.urteilsnummer.strip().replace(" ", "_")
    
    # NEU: Wir nutzen die direkte Export-Schnittstelle des Bundesgerichts
    # Diese liefert fast immer sofort den Volltext ohne Suchmaske
    target_url = f"https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index.php?lang=de&type=highlight_simple_query&page=1&from_date=&to_date=&sort=relevance&insertion_date=&query_words=&name={raw_nr}"
    
    # ScraperAPI mit Rendering und Country-Code (Schweiz) falls möglich
    proxy_url = f"http://api.scraperapi.com?api_key={SCRAPER_KEY}&url={target_url}&render=true&premium=true&country_code=de"

    volltext = ""
    try:
        response = requests.get(proxy_url, timeout=120)
        
        if response.status_code != 200:
            return {"antwort": f"Proxy-Fehler: Status {response.status_code}. Bitte ScraperAPI-Guthaben prüfen."}
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Wir suchen gezielt nach dem Urteilskörper
        # BGer nutzt oft Klassen wie 'content' oder 'aza-content'
        main_content = soup.find('div', class_='content') or soup.find('body')
        
        if main_content:
            for element in main_content(["script", "style", "nav", "header", "footer"]):
                element.decompose()
            volltext = main_content.get_text(separator=' ', strip=True)
        
    except Exception as e:
        return {"antwort": f"Verbindungsfehler: {str(e)}"}

    # VALIDIERUNG: Prüfen auf typische Schlagworte
    if not volltext or not any(x in volltext for x in ["Erwägung", "Considérant", "Considerando", "E."]):
        return {"antwort": "Das Bundesgericht verweigert aktuell den Zugriff. Bitte kopieren Sie den Text des Urteils kurz manuell hier hinein (Option 3), damit ich ihn analysieren kann."}

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
        return {"antwort": f"Fehler bei der KI-Analyse: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
