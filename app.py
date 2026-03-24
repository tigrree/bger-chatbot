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
allow_origins=[”*”],
allow_methods=[”*”],
allow_headers=[”*”],
)

client = anthropic.Anthropic(api_key=os.getenv(“ANTHROPIC_API_KEY”))

class ChatRequest(BaseModel):
urteilsnummer: str
frage: str

@app.get(”/ping”)
async def ping():
“”“Keep-alive Endpoint – wird beim Öffnen des Chat-Widgets aufgerufen,
damit der Render-Server aufgeweckt wird, bevor der Nutzer die erste Frage stellt.”””
return {“status”: “ok”}

@app.post(”/ask”)
async def ask_bot(request: ChatRequest):
raw_nr = request.urteilsnummer.strip()

```
# Volltext direkt vom Bundesgericht abrufen
url = (
    f"https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index.php"
    f"?lang=de&type=highlight_simple_query&query_words=&name={raw_nr}"
)

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

try:
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Navigation und technische Elemente entfernen
    for hidden in soup(["script", "style", "nav", "header", "footer"]):
        hidden.decompose()

    # Haupttext extrahieren
    content = soup.find("div", class_="content") or soup.find("body")
    volltext = content.get_text(separator=" ", strip=True)

    # Sicherheitscheck: Text zu kurz oder Urteil nicht gefunden
    if len(volltext) < 800:
        return {
            "antwort": (
                f"Ich konnte den Volltext zu '{raw_nr}' nicht extrahieren. "
                "Das Bundesgericht liefert aktuell keine Daten fuer diese Anfrage. "
                "Bitte versuchen Sie es gleich noch einmal."
            )
        }

    # Claude mit dem Volltext füttern
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3500,
        temperature=0,
        system="""Du bist ein spezialisierter Schweizer Rechtsassistent.
```

DIR LIEGT DER VOLLTEXT DES URTEILS UNTEN VOR.
Beantworte die Frage PRAEZISE und NUR auf Basis dieses Textes.

REGELN:

1. Nenne konkrete Erwaegungen (z.B. E. 4.2).
1. Achte auf medizinische Quellen oder Weblinks (z.B. Charite), falls erwaehnt.
1. Falls die Information NICHT im Text steht, sage es deutlich.
1. Nutze konsequent ‘ss’ statt Eszett.
1. Antworte immer auf Deutsch, auch wenn das Urteil franzoesisch oder italienisch ist.”””,
   messages=[
   {
   “role”: “user”,
   “content”: (
   f”Urteil: {raw_nr}\n\n”
   f”Inhalt:\n{volltext}\n\n”
   f”Frage: {request.frage}”
   ),
   }
   ],
   )
   
   ```
    return {"antwort": message.content[0].text}
   ```
   
   except requests.exceptions.Timeout:
   return {
   “antwort”: (
   “Das Bundesgericht hat zu langsam geantwortet (Timeout). “
   “Bitte versuchen Sie es in ein paar Sekunden erneut.”
   )
   }
   except Exception as e:
   return {“antwort”: f”Fehler beim Text-Abruf: {str(e)}”}

if **name** == “**main**”:
import uvicorn
uvicorn.run(app, host=“0.0.0.0”, port=8000)