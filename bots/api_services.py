import os
import aiohttp
import discord

async def cwel_manifesto_scraper(client: discord.Client, manifesto_channel_id: int) -> str | None:
    """
    Pobiera wszystkie wiadomości z kanału manifestu i wysyła je do backendu.
    Zwraca złożoną treść manifestu jako tekst (str).
    """
    if not manifesto_channel_id:
        print("Error: CWEL_MANIFESTO_ID is not provided.")
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
        async with aiohttp.ClientSession() as session:
            async with session.post(backend_url, json={"content": cwel_manifesto}) as resp:
                if resp.status in (200, 201):
                    print("Manifest updated in database.")
                else:
                    print(f"Failed to update manifest in database: {resp.status} - {await resp.text()}")
    except Exception as e:
        print(f"Error during manifest update: {e}")
        
    return cwel_manifesto
    
async def add_quote_to_database(message: discord.Message):
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
        
        async with aiohttp.ClientSession() as session:
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