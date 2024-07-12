import os
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from app.middleware.processPrompt import promptResponse
import pymongo
import requests

app = FastAPI()

# Setup templates directory
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def read_form(request: Request):
    return templates.TemplateResponse("form.html", {"request": request})

@app.post("/", response_class=HTMLResponse)
async def process_form(request: Request, prompt: str = Form(...)):
    # Process the prompt and get the response
    newResponse = promptResponse(prompt)
    
    # Perform search based on the prompt
    client = pymongo.MongoClient("")
    db = client.sample_mflix
    collection = db.movies
    hf_token = ""
    
    if not hf_token:
        raise ValueError("Hugging Face token not found. Please set the HF_TOKEN environment variable.")
    
    embedding_url = "https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2"

    def generate_embedding(text: str) -> list:
        response = requests.post(
            embedding_url,
            headers={"Authorization": f"Bearer {hf_token}"},
            json={"inputs": text}
        )
        if response.status_code != 200:
            raise ValueError(f"Request failed with status code {response.status_code}: {response.text}")
        return response.json()


    try:
        for doc in collection.find({'plot': {"$exists": True}}).limit(50):
            doc['plot_embedding_hf'] = generate_embedding(doc['plot'])
            collection.replace_one({'_id': doc['_id']}, doc)
    except Exception as e:
        print(f"Error updating documents: {e}")

    # Perform search
    try:
        results = collection.aggregate([
            {
                "$search": {
                    "index": "PlotSemanticSearch",
                    "text": {
                        "query": prompt,
                        "path": "plot"
                    }
                }
            },
            {
                "$limit": 4
            }
        ])

        search_results = []
        for document in results:
            search_results.append({
                "title": document["title"],
                "plot": document["plot"]
            })
    except Exception as e:
        print(f"Error performing search: {e}")
        search_results = []

    return templates.TemplateResponse("form.html", {
        "request": request,
        "response": newResponse,
        "search_results": search_results
    })
