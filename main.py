# main.py
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
import pandas as pd
import io
from models import Offer, Lead
import storage
from scoring import score_lead

app = FastAPI(title="Lead Scoring API", version="0.1")

@app.get("/")
async def root():
    return {"message": "Lead Scoring API is running! Visit /docs for interactive API docs."}

@app.post("/offer")
async def post_offer(offer: Offer):
    storage.save_offer(offer)
    return {"status": "ok", "message": "Offer saved."}

@app.post("/leads/upload")
async def upload_leads(file: UploadFile = File(...)):
    if not file.filename.endswith((".csv", ".txt")):
        raise HTTPException(status_code=400, detail="Only CSV files supported.")
    contents = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {e}")

    required_cols = {"name","role","company","industry","location","linkedin_bio"}
    if not required_cols.issubset(set(df.columns.str.lower())):
        # Allow case-insensitive columns by normalizing
        df.columns = [c.lower() for c in df.columns]
    # Fill missing columns with empty strings
    for c in required_cols:
        if c not in df.columns:
            df[c] = ""

    leads = []
    for _, row in df.iterrows():
        leads.append(Lead(
            name=row.get("name",""),
            role=row.get("role",""),
            company=row.get("company",""),
            industry=row.get("industry",""),
            location=row.get("location",""),
            linkedin_bio=row.get("linkedin_bio",""),
        ))
    storage.add_leads(leads)
    return {"status":"ok", "imported": len(leads)}

@app.post("/score")
async def run_scoring():
    offer = storage.offer_store
    if not offer:
        raise HTTPException(status_code=400, detail="No offer found. POST /offer first.")
    leads = storage.get_leads()
    results = []
    for lead in leads:
        out = score_lead(lead, offer)
        results.append(out)
    storage.save_results(results)
    return {"status":"ok", "scored": len(results)}

@app.get("/results")
async def get_results():
    results = storage.get_results()
    return JSONResponse(results)

@app.get("/results/export")
async def export_csv():
    results = storage.get_results()
    if not results:
        return JSONResponse({"detail":"No results yet."}, status_code=404)
    df = pd.DataFrame(results)
    stream = io.StringIO()
    df.to_csv(stream, index=False)
    stream.seek(0)
    return StreamingResponse(io.BytesIO(stream.getvalue().encode()), media_type="text/csv", headers={"Content-Disposition":"attachment; filename=results.csv"})
