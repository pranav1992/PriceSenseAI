from unittest.mock import MagicMock, patch

import pytest

from backend.app.schemas.analysis import AnalysisResponse, PriceStats, PriceSuggestion, StockSignal
from backend.app.services.insights import get_ai_insights

pytestmark = pytest.mark.unit

_ASIN = "B0TEST0001"

_GOOD_JSON = (
    '{"price_analysis": "You are 11% above market.", '
    '"discount_recommendation": "Reduce by 10% to $89.99.", '
    '"competitive_positioning": "Position as a premium value option."}'
)

_FENCED_JSON = f"```json\n{_GOOD_JSON}\n```"


def _make_analysis():
    return AnalysisResponse(
        asin=_ASIN,
        current_price=99.99,
        price_stats=PriceStats(median=89.99, avg=92.0, min=79.99, max=109.99, count=10),
        suggestion=PriceSuggestion(
            suggested_price=89.99, discount_pct=10.0, price_position="above_market"
        ),
        stock_signal=StockSignal(level="in_stock", severity="ok", action=None),
    )


def _mock_client(text: str):
    """Return a patched Anthropic client whose messages.create returns `text`."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=text)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    return mock_client


# ── no API key ────────────────────────────────────────────────────────────────

class TestMissingApiKey:
    def test_returns_graceful_message_when_key_not_set(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        result = get_ai_insights(_ASIN, "Test Product", 99.99, _make_analysis())
        assert "unavailable" in result.price_analysis.lower()
        assert result.asin == _ASIN

    def test_does_not_call_anthropic_when_key_missing(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with patch("backend.app.services.insights.anthropic.Anthropic") as mock_cls:
            get_ai_insights(_ASIN, "Test Product", 99.99, _make_analysis())
            mock_cls.assert_not_called()


# ── happy path ────────────────────────────────────────────────────────────────

class TestSuccessfulInsights:
    def test_parses_clean_json_response(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        with patch("backend.app.services.insights.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value = _mock_client(_GOOD_JSON)
            result = get_ai_insights(_ASIN, "Test Product", 99.99, _make_analysis())

        assert result.price_analysis == "You are 11% above market."
        assert result.discount_recommendation == "Reduce by 10% to $89.99."
        assert result.competitive_positioning == "Position as a premium value option."
        assert result.asin == _ASIN

    def test_strips_markdown_fences_before_parsing(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        with patch("backend.app.services.insights.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value = _mock_client(_FENCED_JSON)
            result = get_ai_insights(_ASIN, "Test Product", 99.99, _make_analysis())

        assert result.price_analysis == "You are 11% above market."

    def test_falls_back_to_raw_text_when_response_is_not_json(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        with patch("backend.app.services.insights.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value = _mock_client("Plain text response from the model.")
            result = get_ai_insights(_ASIN, "Test Product", 99.99, _make_analysis())

        assert result.price_analysis == "Plain text response from the model."
        assert result.discount_recommendation == ""

    def test_passes_product_context_to_api(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        with patch("backend.app.services.insights.anthropic.Anthropic") as mock_cls:
            mock_client = _mock_client(_GOOD_JSON)
            mock_cls.return_value = mock_client
            get_ai_insights(_ASIN, "NIMO Laptop", 99.99, _make_analysis(), "USD")

        call_kwargs = mock_client.messages.create.call_args
        user_content = call_kwargs.kwargs["messages"][0]["content"]
        assert "NIMO Laptop" in user_content
        assert "99.99" in user_content
        assert _ASIN in user_content

    def test_uses_correct_model(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        with patch("backend.app.services.insights.anthropic.Anthropic") as mock_cls:
            mock_client = _mock_client(_GOOD_JSON)
            mock_cls.return_value = mock_client
            get_ai_insights(_ASIN, "Test", 99.99, _make_analysis())

        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs["model"] == "claude-sonnet-4-6"

    def test_system_prompt_has_cache_control(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        with patch("backend.app.services.insights.anthropic.Anthropic") as mock_cls:
            mock_client = _mock_client(_GOOD_JSON)
            mock_cls.return_value = mock_client
            get_ai_insights(_ASIN, "Test", 99.99, _make_analysis())

        call_kwargs = mock_client.messages.create.call_args
        system_block = call_kwargs.kwargs["system"][0]
        assert system_block["cache_control"] == {"type": "ephemeral"}


# ── API error handling ────────────────────────────────────────────────────────

class TestApiErrorHandling:
    def _raise_api_error(self, message: str, body: dict):
        import anthropic as anthropic_lib
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.headers = {}
        return anthropic_lib.BadRequestError(
            message=message,
            response=mock_resp,
            body=body,
        )

    def test_returns_clean_message_on_billing_error(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        err = self._raise_api_error(
            "bad request",
            {"error": {"message": "Your credit balance is too low."}},
        )
        with patch("backend.app.services.insights.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = err
            result = get_ai_insights(_ASIN, "Test", 99.99, _make_analysis())

        assert "unavailable" in result.price_analysis.lower()
        assert "credit balance" in result.price_analysis.lower()
        assert result.asin == _ASIN

    def test_does_not_raise_on_api_error(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        err = self._raise_api_error("error", {"error": {"message": "Rate limit exceeded."}})
        with patch("backend.app.services.insights.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = err
            result = get_ai_insights(_ASIN, "Test", 99.99, _make_analysis())

        assert result is not None
