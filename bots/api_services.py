import aiohttp
import discord

async def cwel_manifesto_scraper(client: discord.Client, manifesto_channel_id: int, session: aiohttp.ClientSession) -> str | None:
    """
    Pobiera wszystkie wiadomości z kanału manifestu i wysyła je do backendu.
    Zwraca złożoną treść manifestu jako tekst (str).
    """
    if not manifesto_channel_id:
        print("Error: CWEL_MANIFESTO_CHANNEL_ID is not provided.")
        return None
        
    channel = client.get_channel(manifesto_channel_id)

    if not isinstance(channel, discord.TextChannel):
        print(f"Error: Channel {manifesto_channel_id} is not a text channel or was not found.")
        return None

    content_lines = []

    async for message in channel.history(limit=None, oldest_first=True):
        if message.type != discord.MessageType.default:
            continue
        content_lines.append(message.content)
    
    # Sklejamy wszystkie wiadomości
    cwel_manifesto = "\n".join(content_lines).strip()
    
    if not cwel_manifesto:
        print(f"Warning: Scraped manifesto from channel {manifesto_channel_id} is empty")

    backend_url = 'http://127.0.0.1:8000/manifesto'

    try:
        async with session.post(backend_url, json={"content": cwel_manifesto}) as resp:
            if resp.status in (200, 201):
                print("Manifest updated in database.")
            else:
                print(f"Failed to update manifest in database: {resp.status} - {await resp.text()}")
    except Exception as e:
        print(f"Error during manifest update: {e}")
        
    return cwel_manifesto
    
async def add_quote_to_database(message: discord.Message, session: aiohttp.ClientSession):
    """
    Pobiera wiadomość, na którą odpowiedziano oznaczając bota, i zapisuje ją w backendzie jako cytat.
    """
    if not message.reference or not message.reference.message_id:
        await message.reply("Musisz odpowiedzieć na wiadomość, którą chcesz dodać jako cytat!")
        return

    try:
        # Pobieranie odniesionej wiadomości z cache, lub za pomocą API (jeśli jej tam nie ma)
        replied_msg = message.reference.cached_message or await message.channel.fetch_message(message.reference.message_id)
        author_name = replied_msg.author.display_name
        quote_content = replied_msg.content.strip()

        if not quote_content:
            await message.reply("Gościuuu, ta wiadomość jest pusta (pewnie to tylko obrazek lub plik).")
            return

        backend_url = 'http://127.0.0.1:8000/quotes'
        
        async with session.post(backend_url, json={"author": author_name, "content": quote_content}) as resp:
            if resp.status in (200, 201):
                await message.reply(f"🗿 Dodano cytat\n**Autor:** {author_name}")
            else:
                error_text = await resp.text()
                await message.reply(f"Niepowodzenie, backend zwrócił błąd: {resp.status}")
                print(f"Failed to add quote to database: {resp.status} - {error_text}")
                    
    except discord.NotFound:
        await message.reply("Nie udało się znaleźć wiadomości bazowej (może została usunięta).")
    except Exception as e:
        print(f"Error during quote saving: {e}")
        await message.reply("Wystąpił błąd – nie udało się pobrać wiadomości lub połączyć z bazą danych.")

async def get_random_daily_challenge(session: aiohttp.ClientSession):
    backend_url = 'http://127.0.0.1:8000/daily-challenge'
    try:
        async with session.get(backend_url) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("content", "Brak treści wyzwania.")
            else:
                print(f"Failed to fetch daily challenge: {resp.status} - {await resp.text()}")
                return "Nie udało się pobrać wyzwania."
    except Exception as e:
        print(f"Error fetching daily challenge: {e}")
        return "Wystąpił błąd podczas pobierania wyzwania."

async def get_random_quote(session: aiohttp.ClientSession):
    backend_url = 'http://127.0.0.1:8000/random-quote'
    try:
        async with session.get(backend_url) as resp:
            if resp.status == 200:
                data = await resp.json()
                return {"author": data.get("author", "Nieznany"), "content": data.get("content", "Brak treści cytatu.")}
            else:
                print(f"Failed to fetch random quote: {resp.status} - {await resp.text()}")
                return {"author": "Nieznany", "content": "Nie udało się pobrać cytatu."}
    except Exception as e:
        print(f"Error fetching random quote: {e}")
        return {"author": "Nieznany", "content": "Wystąpił błąd podczas pobierania cytatu."}

async def get_active_challenges(session: aiohttp.ClientSession):
    backend_url = 'http://127.0.0.1:8000/active-challenges'
    try:
        async with session.get(backend_url) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data
            else:
                print(f"Failed to fetch active challenges: {resp.status} - {await resp.text()}")
                return []
    except Exception as e:
        print(f"Error fetching active challenges: {e}")
        return []

async def add_challenge_to_database(challenge: dict, session: aiohttp.ClientSession):
    backend_url = 'http://127.0.0.1:8000/challenge'
    try:
        async with session.post(backend_url, json=challenge) as resp:
            if resp.status in (200, 201):
                print("Challenge added to database.")
            else:
                print(f"Failed to add challenge to database: {resp.status} - {await resp.text()}")
    except Exception as e:
        print(f"Error adding challenge to database: {e}")

async def add_daily_challenge_to_database(challenge: str, session: aiohttp.ClientSession):
    backend_url = 'http://127.0.0.1:8000/daily-challenge'
    try:
        async with session.post(backend_url, json={"content": challenge}) as resp:
            if resp.status in (200, 201):
                print("Daily challenge added to database.")
            else:
                print(f"Failed to add daily challenge to database: {resp.status} - {await resp.text()}")
    except Exception as e:
        print(f"Error adding daily challenge to database: {e}")