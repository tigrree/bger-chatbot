from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic
import requests
from bs4 import BeautifulSoup
import os
import re

app = FastAPI()

# CORS erlaubt deiner Webseite die Kommunikation mit dem Bot
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
    # 1. Live-Volltext vom Bundesgericht abrufen
    # Wir bauen die URL dynamisch basierend auf der Eingabe
    url = f"https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index.php?lang=de&type=highlight_simple_query&query_words=&name={request.urteilsnummer}"
    
    try:
        response = requests.get(url, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        volltext = soup.get_text()
        
        # 2. Claude 4-6 mit dem Volltext und der Frage füttern
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            temperature=0,
            system="Du bist ein spezialisierter Assistent für Schweizer Sozialversicherungsrecht. Beantworte Fragen zum gelieferten Urteil präzise und nenne Erwägungen (E. X). Nutze 'ss'. Wenn das Gericht eine URL nennt, nenne sie.",
            messages=[
                {"role": "user", "content": f"Urteil {request.urteilsnummer}:\n\n{volltext[:18000]}\n\nFrage: {request.frage}"}
            ]
        )
        return {"antwort": message.content[0].text}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
