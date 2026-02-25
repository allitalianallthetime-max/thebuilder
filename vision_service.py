import os
from fastapi import FastAPI, UploadFile, File
import google.generativeai as genai

app = FastAPI()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

@app.post("/inspect")
async def inspect_hardware(file: UploadFile = File(...)):
    # Convert upload to Gemini-compatible format
    img_data = await file.read()
    model = genai.GenerativeModel('gemini-1.5-flash') # Flash is great for fast vision
    
    response = model.generate_content([
        "Identify this machinery. List key components, model numbers, and salvageable parts for engineering.",
        {"mime_type": "image/jpeg", "data": img_data}
    ])
    
    return {"analysis": response.text}
