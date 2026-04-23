import aiohttp
import os
import discord

async def cwel_manifesto_scraper(client, CWEL_MANIFESTO_ID):
    if CWEL_MANIFESTO_ID is None:
        print("Error: CWEL_MANIFESTO_ID is not set in .env")
        return
        
    channel = client.get_channel(CWEL_MANIFESTO_ID)

    if not isinstance(channel, discord.TextChannel):
        print(f"Error: Channel {CWEL_MANIFESTO_ID} is not a text channel or was not found.")
        return

    global cwel_manifesto
    content = ""

    async for message in channel.history(limit=None, oldest_first=True):
        if message.type != discord.MessageType.default:
            continue
        content += message.content + "\n"
    
    cwel_manifesto = content.strip()
    if not cwel_manifesto:
        print(f"Warning: Scraped manifesto from channel {CWEL_MANIFESTO_ID} is empty")

    base_url = os.getenv('BACKEND_URL', 'http://127.0.0.1:8000/quotes')
    backend_url = base_url.replace('/quotes', '/manifesto')
    if '/manifesto' not in backend_url:
        backend_url = f"{base_url.rstrip('/')}/manifesto"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(backend_url, json={"content": cwel_manifesto}) as resp:
                if resp.status in (200, 201):
                    print("Manifest updated in database.")
                else:
                    print(f"Failed to update manifest in database: {resp.status}")
    except Exception as e:
        print(f"Error during manifest update: {e}")
    
async def add_quote_to_database(message):
    try:
        replied_msg = message.reference.cached_message or await message.channel.fetch_message(message.reference.message_id)
        author_name = replied_msg.author.display_name
        quote_content = replied_msg.content

        if not quote_content.strip():
            await message.reply("Gościuuu ta wiadomość jest pusta, pewnie tylko obrazek.")
            return

        backend_url = os.getenv('BACKEND_URL', 'http://127.0.0.1:8000/quotes')
        async with aiohttp.ClientSession() as session:
            async with session.post(backend_url, json={"author": author_name, "content": quote_content}) as resp:
                if resp.status in (200, 201):
                    await message.reply(f"🗿 Dodano cytat\n**Autor:** {author_name}")
                else:
                    await message.reply(f"Niepowodzenie, backend zwrócił błąd: {resp.status}")
        return
    except Exception as e:
        print(f"Error during quote saving: {e}")
        await message.reply("Nie udało się pobrać wiadomości lub połączyć z bazą danych.")
        return