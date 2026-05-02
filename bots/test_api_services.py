import pytest
import aiohttp
import discord
from unittest.mock import AsyncMock, MagicMock

from api_services import (
    cwel_manifesto_scraper,
    add_quote_to_database,
    get_random_daily_challenge,
    get_random_quote,
    get_active_challenges,
    add_challenge_to_database,
    add_daily_challenge_to_database
)

@pytest.fixture
def mock_session():
    """Tworzy mockowaną sesję aiohttp."""
    session = AsyncMock(spec=aiohttp.ClientSession)
    return session

@pytest.mark.asyncio
async def test_get_random_daily_challenge_success(mock_session):
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {"content": "Zrób 10 pompek"}
    
    # Context manager mock (__aenter__) dla instrukcji 'async with session.get(...)'
    mock_session.get.return_value.__aenter__.return_value = mock_response

    result = await get_random_daily_challenge(mock_session)
    
    assert result == "Zrób 10 pompek"
    mock_session.get.assert_called_once_with('http://127.0.0.1:8000/daily-challenge')

@pytest.mark.asyncio
async def test_get_random_daily_challenge_failure(mock_session):
    mock_response = AsyncMock()
    mock_response.status = 500
    mock_response.text.return_value = "Internal Server Error"
    
    mock_session.get.return_value.__aenter__.return_value = mock_response

    result = await get_random_daily_challenge(mock_session)
    
    assert result == "Nie udało się pobrać wyzwania."

@pytest.mark.asyncio
async def test_add_daily_challenge_success(mock_session):
    mock_response = AsyncMock()
    mock_response.status = 201
    
    mock_session.post.return_value.__aenter__.return_value = mock_response

    await add_daily_challenge_to_database("Wypij szklankę wody", mock_session)
    
    mock_session.post.assert_called_once_with(
        'http://127.0.0.1:8000/daily-challenge',
        json={"content": "Wypij szklankę wody"}
    )

@pytest.mark.asyncio
async def test_get_random_quote_success(mock_session):
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {"author": "Jan", "content": "Testowy cytat"}
    
    mock_session.get.return_value.__aenter__.return_value = mock_response

    result = await get_random_quote(mock_session)
    
    assert result == {"author": "Jan", "content": "Testowy cytat"}

@pytest.mark.asyncio
async def test_add_challenge_to_database(mock_session):
    mock_response = AsyncMock()
    mock_response.status = 201
    
    mock_session.post.return_value.__aenter__.return_value = mock_response

    challenge_data = {"author": "Filip", "content": "Naucz się testów", "end_at": "jutro"}
    await add_challenge_to_database(challenge_data, mock_session)
    
    mock_session.post.assert_called_once_with(
        'http://127.0.0.1:8000/challenge',
        json=challenge_data
    )

@pytest.mark.asyncio
async def test_add_quote_to_database_success(mock_session):
    # Mocking obiektu discord.Message i jego referencji
    mock_message = AsyncMock(spec=discord.Message)
    mock_message.reference = MagicMock()
    mock_message.reference.message_id = 123456
    
    mock_cached_msg = AsyncMock(spec=discord.Message)
    mock_cached_msg.author.display_name = "Sigma"
    mock_cached_msg.content = "To jest zajebisty cytat"
    
    mock_message.reference.cached_message = mock_cached_msg
    mock_message.reply = AsyncMock()

    mock_response = AsyncMock()
    mock_response.status = 201
    mock_session.post.return_value.__aenter__.return_value = mock_response

    await add_quote_to_database(mock_message, mock_session)

    mock_session.post.assert_called_once_with(
        'http://127.0.0.1:8000/quotes',
        json={"author": "Sigma", "content": "To jest zajebisty cytat"}
    )
    mock_message.reply.assert_called_once_with("🗿 Dodano cytat\n**Autor:** Sigma")

@pytest.mark.asyncio
async def test_add_quote_missing_reference(mock_session):
    mock_message = AsyncMock(spec=discord.Message)
    mock_message.reference = None  # Brak odpowiedzi na inną wiadomość
    mock_message.reply = AsyncMock()

    await add_quote_to_database(mock_message, mock_session)

    mock_message.reply.assert_called_once_with("Musisz odpowiedzieć na wiadomość, którą chcesz dodać jako cytat!")
    mock_session.post.assert_not_called()
