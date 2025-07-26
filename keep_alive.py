from fastapi import FastAPI
import uvicorn
import threading

app = FastAPI()

@app.get("/")
def home():
    return {"status": "online"}

def run():
    def start():
        uvicorn.run(app, host="0.0.0.0", port=8080)
    threading.Thread(target=start).start()
