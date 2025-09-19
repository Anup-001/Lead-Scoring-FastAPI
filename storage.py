# storage.py
from typing import List
from models import Offer, Lead, ScoredLead

# In-memory storage for simplicity
offer_store: Offer | None = None
leads_store: List[Lead] = []
scored_results: List[ScoredLead] = []

def save_offer(offer: Offer):
    global offer_store
    offer_store = offer

def add_leads(leads):
    global leads_store
    leads_store.extend(leads)

def get_leads():
    return leads_store

def save_results(results):
    global scored_results
    scored_results = results

def get_results():
    return scored_results

def clear_all():
    global offer_store, leads_store, scored_results
    offer_store = None
    leads_store = []
    scored_results = []
