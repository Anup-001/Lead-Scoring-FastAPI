# scoring.py
import os
from typing import Tuple
from models import Lead
import openai
import textwrap

openai_api_key = os.getenv("OPENAI_API_KEY")
openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# --- Rule layer (max 50) ---
def rule_score(lead: Lead, offer_ideal_use_cases: list) -> Tuple[int, str]:
    """Return (rule_points, short_reasoning)"""
    points = 0
    reasons = []

    # Role relevance
    role = (lead.role or "").lower()
    if any(k in role for k in ["ceo", "founder", "head", "vp", "director", "chief", "owner", "manager"]):
        points += 20
        reasons.append("Role looks like decision-maker (+20)")
    elif any(k in role for k in ["lead", "senior", "principal", "influencer", "analyst", "specialist"]):
        points += 10
        reasons.append("Role looks like influencer (+10)")

    # Industry match
    industry = (lead.industry or "").lower()
    matched = False
    for icp in offer_ideal_use_cases:
        icp_lower = icp.lower()
        if icp_lower == industry and industry:
            points += 20
            reasons.append("Industry exact match (+20)")
            matched = True
            break
    if not matched:
        # very simple "adjacent" heuristic: substring match
        if any(icp.lower() in industry or industry in icp.lower() for icp in offer_ideal_use_cases if industry):
            points += 10
            reasons.append("Industry adjacent (+10)")

    # Data completeness
    if all([lead.name, lead.role, lead.company, lead.industry, lead.location, lead.linkedin_bio]):
        points += 10
        reasons.append("All fields present (+10)")

    return points, "; ".join(reasons)

# --- AI layer (max 50) ---
def ai_intent_and_reasoning(lead: Lead, offer: dict, debug=False) -> Tuple[str, int, str]:
    """
    Returns (intent_label, ai_points, ai_reasoning)
    Uses OpenAI chat completions. If key not found, returns a mock.
    """
    if not openai_api_key:
        # Mock response for local development without API key
        # Simple heuristic from lead data
        text = f"Mock: Based on role {lead.role} and industry {lead.industry}, intent is Medium."
        intent = "Medium"
        points = 30
        return intent, points, text

    openai.api_key = openai_api_key

    # Build prompt
    prompt = textwrap.dedent(f"""
    You are an assistant that reads a product/offer and a prospect profile and classifies the prospect's buying intent into High, Medium, or Low.
    Offer:
    {offer}

    Prospect:
    name: {lead.name}
    role: {lead.role}
    company: {lead.company}
    industry: {lead.industry}
    location: {lead.location}
    linkedin_bio: {lead.linkedin_bio}

    Output only JSON with keys: intent, reasoning (1-2 sentences).
    Example:
    {{ "intent": "High", "reasoning": "Short 1-2 sentences" }}
    """)

    # Use chat completion (adjust call per client library version)
    try:
        resp = openai.ChatCompletion.create(
            model=openai_model,
            messages=[{"role":"user","content":prompt}],
            max_tokens=150,
            temperature=0.0,
        )
        text = resp["choices"][0]["message"]["content"].strip()
    except Exception as e:
        # fallback mock if API fails
        text = f"Error contacting OpenAI: {e}. Defaulting to Medium."
        return "Medium", 30, text

    # parse simple JSON-like response
    import json, re
    # Try to extract JSON substring
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            data = json.loads(m.group(0))
            intent = data.get("intent", "Medium")
            reasoning = data.get("reasoning", text)
        except Exception:
            # If JSON parse fails, fallback to analyzing words
            intent = "Medium"
            reasoning = text
    else:
        # If no JSON, try to find High/Medium/Low in text
        if "high" in text.lower():
            intent = "High"
        elif "low" in text.lower():
            intent = "Low"
        else:
            intent = "Medium"
        reasoning = text

    mapping = {"High": 50, "Medium": 30, "Low": 10}
    ai_points = mapping.get(intent, 30)
    return intent, ai_points, reasoning

# --- full pipeline per lead ---
def score_lead(lead: Lead, offer, debug=False):
    r_points, r_reason = rule_score(lead, offer.get("ideal_use_cases", []))
    intent, ai_points, ai_reason = ai_intent_and_reasoning(lead, offer, debug=debug)
    final_score = r_points + ai_points
    reasoning = "; ".join([r_reason, f"AI: {ai_reason}"]).strip("; ")
    return {
        "name": lead.name,
        "role": lead.role,
        "company": lead.company,
        "industry": lead.industry,
        "intent": intent,
        "score": final_score,
        "reasoning": reasoning
    }
