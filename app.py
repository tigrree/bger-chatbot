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
- Antworte prägnant in 1 bis max. 3 Sätzen.
- Bringe die Kernaussage sofort auf den Punkt.
- VERZICHTE komplett auf Markdown-Überschriften (###), Fettdruck oder lange Aufzählungen.
- ABSOLUTE PFLICHT zu Leitlinien und URLs: Wenn das Gericht auf eine Leitlinie oder eine Internetseite (URL) verweist, MUSST du diese am Ende zwingend erwähnen (zählt NICHT zum 3-Sätze-Limit). Schreibe NIEMALS "Quelle: [...]".
- REGELUNG FÜR VERWEISE: Wenn das Gericht die Leitlinie/URL aktiv im fliessenden Text erklärt, fasse diesen Kontext kurz zusammen. WENN das Gericht die Angabe aber lediglich beiläufig in einer Klammer nennt (z.B. "vgl. z.B. [...]"), dann schreibe EXAKT und AUSSCHLIESSLICH folgenden Satz an den Schluss: "Das BGer hat im Weiteren auf [Leitlinie/URL] verwiesen." Füge diesem Satz unter keinen Umständen eigene Erklärungen, Begründungen oder Zusätze hinzu!
- Nutze konsequent 'ss' statt 'ß'.""",
            messages=[
                {"role": "user", "content": f"Hier ist der Urteilstext:\n<text>\n{request.urteil_text}\n</text>\n\nBeantworte folgende Frage extrem kurz und ohne Formatierungen ausschliesslich basierend auf diesem Text:\nFrage: {request.frage}"}
            ]
        )
        return {"antwort": message.content[0].text}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Claude-Fehler: {str(e)}")
