import os
import datetime
import asyncio
import json
import discord
from discord.ext import tasks
from google import genai
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
from api_services import cwel_manifesto_scraper, add_quote_to_database, get_random_quote, get_random_daily_challenge, get_active_challenges, add_challenge_to_database, add_daily_challenge_to_database
from typing import Dict, Any

# Wczytywanie z .env
load_dotenv()

TOKEN_DISCORD = os.getenv('SIGMA_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Wczytywanie konfiguracji z pliku config.json
with open(os.path.join(os.path.dirname(__file__), 'config.json'), 'r', encoding='utf-8') as f:
    config = json.load(f)

AUTO_THREAD_CHANNELS = config.get("auto_thread_channels", [])
BALANCE_ANNOUNCE_CHANNEL_ID = config.get("balance_announce_channel_id")
CWEL_MANIFESTO_CHANNEL_ID = config.get("cwel_manifesto_channel_id")
DAILY_CHALLENGE_CHANNEL_ID = config.get("daily_challenge_channel_id")
USERS_TO_PING = config.get("users_to_ping", {})
minio_id = USERS_TO_PING.get("minio", "339884510089052160")
veresek_id = USERS_TO_PING.get("veresek", "986324349067874326")

TIME_TO_ANNOUNCE = datetime.time(hour=10, minute=0, second=0, microsecond=0, tzinfo=ZoneInfo("Europe/Warsaw"))
DAILY_CHALLENGE_TIME = datetime.time(hour=8, minute=0, second=0, microsecond=0, tzinfo=ZoneInfo("Europe/Warsaw"))

class SigmaQuotesBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        
        self.gemini = genai.Client(api_key=GEMINI_API_KEY)
        self.cwel_manifesto = ""

    async def setup_hook(self):
        # Inicjalizacja zadania w tle
        self.announce_balance.start()

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        await self.update_manifest()
        print("Manifest loaded successfully")

    async def update_manifest(self):
        # Pobieranie i aktualizacja manifestu z kanału
        new_manifesto = await cwel_manifesto_scraper(self, CWEL_MANIFESTO_CHANNEL_ID)
        if new_manifesto:
            self.cwel_manifesto = new_manifesto

    # Logika odpowiedzi (Gemini)
    async def generate_content_async(self, message: discord.Message, history: list) -> str:
        """Generuje odpowiedź od modelu w osobnym wątku, żeby nie blokować event loopa"""
        history_text = "\n".join([f"{msg['username']}: {msg['content']}" for msg in history])

        contents = (
            f"Kontekst ostatnich wiadomości (od najstarszej do najnowszej):\n{history_text}\n\n"
            f"Odpowiedz na tę wiadomość: '{message.content}' (autor: {message.author.display_name})"
        )
        system_instruction = (
            "Nazywasz się SigmaQuotesBot i jesteś botem na discordzie, który odpowiada na wiadomości. "
            "Jesteś bezpośredni, szczery, czasem sarkastyczny i nie boisz się ironizować. "
            "Odpowiedz w max 2/3 zdaniach po polsku. Chyba że sytuacja wymaga dłuższej odpowiedzi, wtedy napisz więcej. "
            "Nie próbuj nikogo oznaczać — to co wyślesz automatycznie będzie odpowiedzią na wiadomość którą dostałeś. "
            "Nie przedstawiaj się, nie mów że jesteś botem, po prostu odpowiadaj na wiadomości.\n\n"
            "<charakter>\n"
            f"{self.cwel_manifesto}\n"
            "</charakter>\n\n"
            "Powyższy manifest to Twój charakter i sposób bycia — czujesz go naturalnie, ale NIE cytujesz go, "
            "NIE odwołujesz się do niego z nazwy i NIE analizujesz go. "
            "Nie musisz w kazdej wiadomosci pisac zeby od razu leciec do roboty, ale generalnie powinieneś się do niego stosować. "
            "Motywuj do rozwijania się i bycia lepszym, ale nie bądź nachalny. "
        )

        # Uruchamiamy synchroniczną funkcję genai w oddzielnym wątku
        def generate():
            return self.gemini.models.generate_content(
                model="gemini-3.1-flash-lite-preview",
                contents=contents,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_instruction
                )
            )

        response = await asyncio.to_thread(generate)
        return response.text

    async def scrape_channel_history(self, channel: discord.abc.Messageable, limit=10) -> list:
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

    async def respond_to_message(self, message: discord.Message):
        history = await self.scrape_channel_history(message.channel, limit=10)
        try:
            async with message.channel.typing():
                response = await self.generate_content_async(message, history=history)
                
            if response and response.strip():
                await message.reply(response)
            else:
                await message.reply("Nie wiem co powiedzieć, zatkało mnie.")
        except Exception as e:
            print(f"Error generating content: {e}")
            await message.reply("Wystąpił błąd podczas generowania odpowiedzi.")

    async def create_thread(self, message: discord.Message):
        try:
            await message.create_thread(name=message.content[:100])
        except Exception as e:
            print(f"Error creating thread: {e}")


    # Zdarzenia Discord (Events)
    async def on_message(self, message: discord.Message):
        # Ignoruj wiadomości od samego siebie
        if message.author == self.user:
            return

        # Aktualizacja manifestu jeśli wpisano cokolwiek na dedykowanym kanale
        if message.channel.id == CWEL_MANIFESTO_CHANNEL_ID:
            await self.update_manifest()
        if message.content.strip().lower().startswith("!komendy"):
            commands_text = (
                "Dostępne komendy:\n"
                "- Odpowiedz na wiadomość z treścią `@SigmaQuotesBot` aby dodać ją jako cytat do bazy danych.\n"
                "- !daily - dodaje dzienny challenge do bazy danych (tresc 1:1 zapisana w bazie)\n"
                "- !challenge - dodaje challange do bazy danych (trzeba podac tresc, date zakonczenia oraz opcjonalnie date rozpoczecia)\n"
            )
            await message.reply(commands_text)
            return
        if message.content.strip().lower() == "!daily":
            try:
                daily_content = message.content.strip()[len("!daily"):].strip()
                if not daily_content:
                    await message.reply("Musisz podać treść dziennego challange'a po komendzie !daily")
                    return
                await add_daily_challenge_to_database(daily_content)
                await message.reply("Dzienny challange został dodany do bazy danych.")
            except Exception as e:
                print(f"Error adding daily challenge: {e}")
                await message.reply("Wystąpił błąd podczas dodawania dziennego challange'a.")
            return
        if message.content.strip().lower().startswith("!challenge"):
            try:
                challenge_content = message.content.strip()[len("!challenge"):].strip()
                if not challenge_content:
                    await message.reply("Musisz podać treść challange'a po komendzie !challenge")
                    return
                
                def generate_challenge_json():
                    now_iso = datetime.datetime.now(ZoneInfo("Europe/Warsaw")).isoformat()
                    prompt = (
                        f"Przeanalizuj wyzwanie opisane w wiadomości wejściowej i wyodrębnij z niego kluczowe informacje.\n"
                        f"Aktualna data i czas w tej strefie: {now_iso}\n"
                        f"Wiadomość wejściowa: {challenge_content}\n\n"
                        f"Zwróć sam czysty obiekt JSON (bez znaczników markdown, bez dodatkowego tekstu) zawierający klucze:\n"
                        f"- \"content\" (string): Treść i opis wyzwania.\n"
                        f"- \"author\" (string): Autor lub osoba na którą rzucono wyzwanie. Jeśli nie jest jasno powiedziane, przypisz domyślnie: '{message.author.display_name}'.\n"
                        f"- \"start_at\" (string lub null): Data i czas rozpoczęcia wyzwania (w formacie ISO 8601). Zgadnij z kontekstu, jeśli nie ma i rzuć null.\n"
                        f"- \"end_at\" (string lub null): Data i czas zakończenia wyzwania (w formacie ISO 8601). Zgadnij z kontekstu (np. do jutra, do piątku), jeśli wpisano ogólnikowo lub jeśli w ogóle nie ma, rzuć null.\n"
                    )
                    return self.gemini.models.generate_content(
                        model="gemini-3.1-flash-lite-preview",
                        contents=prompt,
                        config=genai.types.GenerateContentConfig(
                            response_mime_type="application/json"
                        )
                    )
                response = await asyncio.to_thread(generate_challenge_json)
                challenge_data = json.loads(response.text)

                challenge_data = {k: v for k, v in challenge_data.items() if v is not None}

                await add_challenge_to_database(challenge_data)
                
                reply_text = (
                    f"🎯 Wyzwanie podjęte i zapisane!\n"
                    f"**Dotyczy:** {challenge_data.get('content', 'Brak treści')}\n"
                    f"**Autor/Kogo dotyczy:** {challenge_data.get('author', message.author.display_name)}\n"
                )
                if 'start_at' in challenge_data:
                    reply_text += f"**Od:** {challenge_data['start_at']}\n"
                if 'end_at' in challenge_data:
                    reply_text += f"**Do:** {challenge_data['end_at']}\n"
                    
                await message.reply(reply_text)
            except Exception as e:
                print(f"Error adding challenge: {e}")
                await message.reply("Wystąpił błąd podczas analizowania (Gemini) lub dodawania challange'a.")
            return
        # Jeśli bot został otagowany
        if self.user and self.user.mentioned_in(message):
            print(f"Received mention, length: {len(message.content)}")

            # Jeśli odpisujemy tagując bota na czyjąś wiadomość (dodanie cytatu)
            if message.reference and message.reference.message_id and message.content.strip().lower() == f'<@{self.user.id}>':
                await add_quote_to_database(message)
                return
            
            # W innym wypadku zwykła konwersacja
            await self.respond_to_message(message)
            return

        # Tworzenie wątków z automatu na wybranych kanałach
        if message.channel.id in AUTO_THREAD_CHANNELS and not message.author.bot:
            await self.create_thread(message)
            
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if after.channel.id == CWEL_MANIFESTO_CHANNEL_ID:
            await self.update_manifest()

    async def on_message_delete(self, message: discord.Message):
        if message.channel.id == CWEL_MANIFESTO_CHANNEL_ID:
            await self.update_manifest()

    # Zadania okresowe (Tasks)
    @tasks.loop(time=TIME_TO_ANNOUNCE)
    async def announce_balance(self):
        print("Running scheduled balance announcement task...")
        channel = self.get_channel(BALANCE_ANNOUNCE_CHANNEL_ID)
        
        # Sprawdzanie czy jutro jest nowy miesiąc (czyli dzisiaj last day)
        today = datetime.date.today()
        next_day = today + datetime.timedelta(days=1)
        is_last_day = next_day.month != today.month

        if channel and isinstance(channel, discord.TextChannel) and is_last_day:
            minio_id = USERS_TO_PING.get("minio", "339884510089052160")
            veresek_id = USERS_TO_PING.get("veresek", "986324349067874326")
            await channel.send(f"<@{minio_id}> <@{veresek_id}> Dzisiaj ostatni dzień miesiąca, zapraszam do rozliczenia za przewinienia! 🗿")

    @tasks.loop(time=DAILY_CHALLENGE_TIME)
    async def daily_challenge(self):
        print("Running scheduled daily challenge task...")
        try:
            challange = await get_random_daily_challenge()
        except Exception as e:
            print(f"Error fetching daily challenge: {e}")
            challange = "Nie udało się pobrać dziennego challange'a."
        try:
            active_challenges = await get_active_challenges()
            if active_challenges:
                active_challenges_text = "\n".join([f"- **{c.get('author', 'Ktoś')}**: {c.get('content', '')}" for c in active_challenges])
            else:
                active_challenges_text = "Obecnie brak aktywnych wyzwań."
        except Exception as e:
            print(f"Error fetching active challenges: {e}")
            active_challenges_text = "Nie udało się pobrać aktywnych wyzwań."
        try:
            quote: Dict[str, str] = await get_random_quote()
        except Exception as e:
            print(f"Error fetching random quote: {e}")
            quote = {"author": "Nieznany", "content": "Nie udało się pobrać cytatu."}
        channel = self.get_channel(DAILY_CHALLENGE_CHANNEL_ID)
        if channel and isinstance(channel, discord.TextChannel):
            await channel.send(f"<@{minio_id}> <@{veresek_id}> Dzienny challange: {challange}")
            await channel.send(f"Aktualne wyzwania:\n{active_challenges_text}")
            await channel.send(f"Cytat dnia:\n**{quote['content']}**\n- *{quote['author']}*")

if __name__ == "__main__":
    if not TOKEN_DISCORD:
        print("Error: SIGMA_TOKEN brakujacy w zmirnnych środowiskowych (.env).")
    else:
        bot = SigmaQuotesBot()
        bot.run(TOKEN_DISCORD)

