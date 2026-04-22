import discord
import aiohttp
from google import genai
from dotenv import load_dotenv
import os
from discord.ext import tasks
import datetime

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

TOKEN_DISCORD = os.getenv('SIGMA_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
client = discord.Client(intents=intents)
gemini = genai.Client(api_key=GEMINI_API_KEY)

AUTO_THREAD_CHANNELS = [1488573012801486989, 1479407068661288990, 1460589191732924567, 1491376568931586218, 1466657754616827914, 1488562360229822536] 
BALANCE_ANNOUNCE_CHANNEL_ID = 1455924587912233109
CWEL_MANIFESTO_ID = 1470102957042303057

time_to_announce = datetime.time(hour=10, minute=0, second=0, microsecond=0)

cwel_manifesto = ""

def generate_content(message, history=None):
    if history is None:
        history = []

    history_text = "\n".join([f"{msg['username']}: {msg['content']}" for msg in history])

    contents = (
        f"Kontekst ostatnich wiadomości (od najstarszej do najnowszej):\n{history_text}\n\n"
        f"Odpowiedz na tę wiadomość: '{message.content}' (autor: {message.author.display_name})"
    )
    response = gemini.models.generate_content(
        model="gemini-3.1-flash-lite-preview",
        contents=contents,
        config=genai.types.GenerateContentConfig(
            system_instruction=(
                "Nazywasz się SigmaQuotesBot i jesteś botem na discordzie, który odpowiada na wiadomości. "
                "Jeżeli wiadomość którą dostałeś wyzywa cię od cweli też go zwyzywaj, nie oszczędź pocisków, "
                "jeżeli nie wyzywa pomóż tak jak chce użytkownik. "
                "Odpowiedz w max 2/3 zdaniach po polsku. "
                "Nie próbuj nikogo oznaczać — to co wyślesz automatycznie będzie odpowiedzią na wiadomość którą dostałeś. "
                "Nie przedstawiaj się, nie mów że jesteś botem, po prostu odpowiadaj na wiadomości.\n\n"
                "<charakter>\n"
                f"{cwel_manifesto}\n"
                "</charakter>\n\n"
                "Powyższy manifest to Twój charakter i sposób bycia — czujesz go naturalnie, ale NIE cytujesz go, "
                "NIE odwołujesz się do niego z nazwy i NIE analizujesz go. "
                "Używasz go tylko gdy ktoś bezpośrednio pyta o bycie cwelem lub o zasady."
            )
        )
    )
    return response.text

async def scrape_channel_history(channel, limit=10):
    history = []
    async for msg in channel.history(limit=limit, oldest_first=True):
        if msg.type != discord.MessageType.default:
            continue

        content = msg.content.strip()
        if not content:
            continue

        history.append({
            "username": msg.author.display_name,
            "content": content,
        })

    return history

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

def is_last_day_of_month():
    today = datetime.date.today()
    next_day = today.replace(day=today.day + 1)
    return next_day.month != today.month

async def cwel_manifesto_scraper():
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

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    await cwel_manifesto_scraper()
    print("Manifest loaded successfully")
    if not announce_balance.is_running():
        announce_balance.start()

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.channel.id == CWEL_MANIFESTO_ID:
        await cwel_manifesto_scraper()

    # Dodawanie cytatu do bazy danych, jeśli bot został wspomniany i wiadomość jest odpowiedzią na inną wiadomość
    if client.user and client.user.mentioned_in(message):
        print(f"Received mention, length: {len(message.content)}")

        if message.reference and message.reference.message_id and message.content.strip().lower() == f'<@{client.user.id}>':
            await add_quote_to_database(message)
            return
        # Jeśli wiadomość nie jest odpowiedzią, ale nadal wspomina bota, generujemy odpowiedź
        history = await scrape_channel_history(message.channel, limit=10)
        try:
            response = generate_content(message, history=history)
            if response and response.strip():
                await message.reply(response)
            else:
                await message.reply("Nie wiem co powiedzieć, zatkało mnie.")
        except Exception as e:
            print(f"Error generating content: {e}")
            await message.reply("Wystąpił błąd podczas generowania odpowiedzi.")
    # Automatyczne tworzenie wątku, jeśli wiadomość została wysłana na określonych kanałach i nie jest od bota
    if message.channel.id in AUTO_THREAD_CHANNELS and not message.author.bot:
        thread_name = message.content
        try:
            await message.create_thread(name=thread_name)

        except Exception as e:
            print(f"Error creating thread: {e}")
@client.event
async def on_message_edit(before, after):
    # Aktualizuj manifest, jeśli wiadomość została edytowana w kanale manifestu
    if after.channel.id == CWEL_MANIFESTO_ID:
        await cwel_manifesto_scraper()

@client.event
async def on_message_delete(message):
    # Aktualizuj manifest, jeśli wiadomość została usunięta w kanale manifestu
    if message.channel.id == CWEL_MANIFESTO_ID:
        await cwel_manifesto_scraper()

@tasks.loop(time=time_to_announce)
async def announce_balance():
    print("Running scheduled balance announcement task...")
    channel = client.get_channel(BALANCE_ANNOUNCE_CHANNEL_ID)
    if channel and isinstance(channel, discord.TextChannel) and is_last_day_of_month():
        minio_id = "339884510089052160" 
        veresek_id = "986324349067874326"
        await channel.send(f"<@{minio_id}> <@{veresek_id}> Dzisiaj ostatni dzień miesiąca, zapraszam do rozliczenia za przewinienia! 🗿")
        

client.run(str(TOKEN_DISCORD))
