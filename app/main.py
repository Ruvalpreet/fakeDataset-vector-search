import os
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from app.middleware.processPrompt import promptResponse
import pymongo
import httpx

app = FastAPI()

# Setup templates directory
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def read_form(request: Request):
    return templates.TemplateResponse("form.html", {"request": request})

@app.post("/", response_class=HTMLResponse)
async def process_form(request: Request, prompt: str = Form(...)):
    # Here you can process the prompt and get the response
    newResponse = promptResponse(prompt)
    return templates.TemplateResponse("form.html", {"request": request, "response": newResponse})


try:
    client = pymongo.MongoClient("mongodb+srv://jcooo805:eRkn8iktQYQauNMJ@cluster0.q8yxaia.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
    db = client.sample_mflix
    collection = db.movies
    hf_token = os.getenv("HF_TOKEN")
    embedding_url = "https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2"

    items = collection.find().limit(5)

    for item in items:
        print(item)

    async def generate_embedding(text: str) -> list:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                embedding_url,
                headers={"Authorization": f"Bearer {hf_token}"},
                json={"inputs": text}
            )
            if response.status_code != 200:
                raise ValueError(f"Request failed with status code {response.status_code}: {response.text}")
            return response.json()

    async def update_documents():
        async for doc in collection.find({'plot': {"$exists": True}}).limit(50):
            doc['plot_embedding_hf'] = await generate_embedding(doc['plot'])
            collection.replace_one({'_id': doc['_id']}, doc)

    import asyncio
    asyncio.run(update_documents())

    query = "imaginary characters from outer space at war"
    query_embedding = asyncio.run(generate_embedding(query))

    results = collection.aggregate([
        {
            "$search": {
                "index": "PlotSemanticSearch",
                "text": {
                    "query": query,
                    "path": "plot"
                }
            }
        },
        {
            "$limit": 4
        }
    ])

    for document in results:
        print(f'Movie Name: {document["title"]},\nMovie Plot: {document["plot"]}\n')

except Exception as e:
    print(e)
