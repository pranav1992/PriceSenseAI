import json
import os

import anthropic

from ..schemas.analysis import AnalysisResponse, InsightsResponse

_SYSTEM_PROMPT = (
    "You are a pricing strategist for Amazon sellers. "
    "Given a product's current price, competitor market stats, and computed suggestions, "
    "provide concise, actionable recommendations. "
    "Respond with a JSON object containing exactly these keys:\n"
    "- price_analysis: 1-2 sentences on how the current price compares to the market.\n"
    "- discount_recommendation: A specific action, e.g. 'Reduce by 8% to $X.XX to match market median'.\n"
    "- competitive_positioning: 1 sentence on how the seller should position this product.\n"
    "Return JSON only — no markdown fences, no extra text."
)


def get_ai_insights(
    asin: str,
    product_title: str | None,
    current_price: float | None,
    analysis: AnalysisResponse,
    currency: str = "USD",
) -> InsightsResponse:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return InsightsResponse(
            asin=asin,
            price_analysis="AI insights unavailable — ANTHROPIC_API_KEY is not configured.",
            discount_recommendation="Set ANTHROPIC_API_KEY in your environment to enable this feature.",
            competitive_positioning="",
        )

    stats = analysis.price_stats
    suggestion = analysis.suggestion
    stock = analysis.stock_signal

    user_content = (
        f"Product ASIN: {asin}\n"
        f"Title: {product_title or 'Unknown'}\n"
        f"Current Price: {currency} {current_price}\n"
        f"Stock Status: {stock.level}\n\n"
        f"Competitor Market Stats:\n"
        f"  Median: {currency} {stats.median if stats else 'N/A'}\n"
        f"  Average: {currency} {stats.avg if stats else 'N/A'}\n"
        f"  Min: {currency} {stats.min if stats else 'N/A'}\n"
        f"  Max: {currency} {stats.max if stats else 'N/A'}\n"
        f"  Competitors analysed: {stats.count if stats else 0}\n\n"
        f"Computed Suggestion:\n"
        f"  Suggested Price: {currency} {suggestion.suggested_price if suggestion else 'N/A'}\n"
        f"  Discount needed: {suggestion.discount_pct if suggestion else 0}%\n"
        f"  Market Position: {suggestion.price_position if suggestion else 'unknown'}"
    )

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=[
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
            messages=[{"role": "user", "content": user_content}],
        )
    except anthropic.APIStatusError as exc:
        # Extract the human-readable message from the API error body when available
        body = exc.body or {}
        msg = (body.get("error", {}).get("message") if isinstance(body, dict) else None) or exc.message or str(exc)
        return InsightsResponse(
            asin=asin,
            price_analysis=f"AI insights unavailable: {msg}",
            discount_recommendation="",
            competitive_positioning="",
        )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        payload = json.loads(raw)
        return InsightsResponse(
            asin=asin,
            price_analysis=payload.get("price_analysis", ""),
            discount_recommendation=payload.get("discount_recommendation", ""),
            competitive_positioning=payload.get("competitive_positioning", ""),
        )
    except json.JSONDecodeError:
        return InsightsResponse(
            asin=asin,
            price_analysis=raw,
            discount_recommendation="",
            competitive_positioning="",
        )
