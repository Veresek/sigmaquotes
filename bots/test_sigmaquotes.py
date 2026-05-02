import pytest
import discord
from unittest.mock import AsyncMock, patch

# Importujemy bota tak, aby zamockować klienta Gemini zanim podejmie próbę autoryzacji
with patch('google.genai.Client') as mock_genai_client:
    from sigmaquotes import SigmaQuotesBot

@pytest.fixture
def bot():
    # Inicjalizujemy bota omijając standardową inicjalizację discord.Client
    with patch('discord.Client.__init__', return_value=None):
        test_bot = SigmaQuotesBot()
        test_bot.session = AsyncMock()
        test_bot._log_action = AsyncMock()
        return test_bot

@pytest.mark.asyncio
async def test_validate_daily_challenge_content_valid(bot):
    # Podmieniamy _call_gemini na mocka, który zwraca JSON'a potwierdzającego sens wyzwania
    bot._call_gemini = AsyncMock(return_value='{"is_valid": true, "reason": "To ma sens"}')
    
    result = await bot.validate_daily_challenge_content("Przeczytaj 10 stron książki")
    
    assert result["is_valid"] is True
    assert result["reason"] == "To ma sens"
    bot._call_gemini.assert_called_once()

@pytest.mark.asyncio
async def test_validate_daily_challenge_content_invalid(bot):
    bot._call_gemini = AsyncMock(return_value='{"is_valid": false, "reason": "To jest spam"}')
    
    result = await bot.validate_daily_challenge_content("asdasdasdasd")
    
    assert result["is_valid"] is False
    assert result["reason"] == "To jest spam"

@pytest.mark.asyncio
async def test_parse_challenge_content(bot):
    expected_json = '{"content": "Wygraj gre", "author": "User1", "start_at": null, "end_at": "do piatku", "is_sensible": true, "reason": "Sensowne"}'
    bot._call_gemini = AsyncMock(return_value=expected_json)
    
    result = await bot.parse_challenge_content("Wygraj gre do piatku", "User1")
    
    assert result["content"] == "Wygraj gre"
    assert result["end_at"] == "do piatku"
    assert result["is_sensible"] is True

@pytest.mark.asyncio
async def test_handle_daily_challenge_empty_content(bot):
    mock_message = AsyncMock(spec=discord.Message)
    mock_message.content = "   " # Same spacje (pusta wiadomość, np. tylko obrazek)
    mock_message.author.mention = "@User"
    mock_message.delete = AsyncMock()

    await bot.handle_daily_challenge(mock_message)
    
    mock_message.delete.assert_called_once()
    bot._log_action.assert_called_once_with("@User Musisz podać treść dziennego challange'a, nie może być to obrazek.")

@pytest.mark.asyncio
async def test_handle_daily_challenge_rejected_by_gemini(bot):
    mock_message = AsyncMock(spec=discord.Message)
    mock_message.content = "głupoty"
    mock_message.author.mention = "@User"
    mock_message.delete = AsyncMock()

    # Zmuszamy metodę walidacji by zachowała się jak przy odmowie przez LLM
    bot.validate_daily_challenge_content = AsyncMock(return_value={"is_valid": False, "reason": "Spam"})
    
    await bot.handle_daily_challenge(mock_message)
    
    mock_message.delete.assert_called_once()
    bot._log_action.assert_called_once_with("@User Odrzucono dzienny challenge. Uzasadnienie: Spam")
