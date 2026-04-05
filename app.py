import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic

app = FastAPI()

# SICHERHEIT: Nur deine Webseite darf diesen Bot anfunken!
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://tigrree.github.io", "http://localhost:8000", "http://127.0.0.1:8000"], 
    allow_methods=["POST"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    urteil_text: str
    frage: str

@app.post("/ask")
async def ask_bot(request: ChatRequest):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Konfigurationsfehler: ANTHROPIC_API_KEY fehlt auf dem Server.")

    client = anthropic.Anthropic(api_key=api_key)

    try:
        # Hier nutzen wir das korrekte, aktuelle Claude 3.5 Sonnet Modell
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500, # Reduziert für kurze, prägnante Antworten
            temperature=0.1, # Sehr niedrige Temperatur = Fokus auf Fakten, keine Ausschweifungen
            system="""Du bist ein hochqualifizierter Schweizer Rechtsassistent. Beantworte die Frage des Nutzers EXTREM KURZ, PRÄZISE und AUSSCHLIESSLICH basierend auf dem nachfolgend übermittelten Urteilstext. 

WICHTIGE FORMATVORGABEN:
- Antworte so kurz wie möglich, idealerweise in 1 bis 3 Sätzen.
- Bringe die Kernaussage sofort auf den Punkt.
- VERZICHTE komplett auf Markdown-Überschriften (###), Fettdruck oder lange Aufzählungen.
- Wenn das Gericht auf eine Quelle oder Internetseite verweist, nenne diese direkt.
- Wenn die Antwort nicht im Text steht, erfinde nichts, sondern kommuniziere klar, dass das Urteil dazu keine Angaben macht.
- Nutze konsequent 'ss' statt 'ß'.""",
            messages=[
                {"role": "user", "content": f"Hier ist der Urteilstext:\n<text>\n{request.urteil_text}\n</text>\n\nBeantworte folgende Frage extrem kurz und ohne Formatierungen ausschliesslich basierend auf diesem Text:\nFrage: {request.frage}"}
            ]
        )
        return {"antwort": message.content[0].text}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Claude-Fehler: {str(e)}")
