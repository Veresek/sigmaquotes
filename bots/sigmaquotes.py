import os
import datetime
import asyncio
import json
import discord
import aiohttp
from discord.ext import tasks
from google import genai
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
from api_services import (
    cwel_manifesto_scraper, 
    add_quote_to_database, 
    get_random_quote, 
    get_random_daily_challenge, 
    get_active_challenges, 
    add_challenge_to_database, 
    add_daily_challenge_to_database
)

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
CHALLENGE_CHANNEL_ID = config.get("challenge_channel_id")
LOGS_CHANNEL_ID = config.get("logs_channel_id")

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
        self.session = None

    async def setup_hook(self):
        # Inicjalizacja zadań w tle i sesji HTTP
        self.session = aiohttp.ClientSession()
        self.announce_balance.start()
        self.daily_challenge.start()

    async def close(self):
        # Zamknięcie sesji HTTP gdy bot jest zamykany
        if self.session:
            await self.session.close()
        await super().close()

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        await self.update_manifest()
        print("Manifest loaded successfully")

    async def update_manifest(self):
        """Pobieranie i aktualizacja manifestu z dedykowanego kanału."""
        new_manifesto = await cwel_manifesto_scraper(self, CWEL_MANIFESTO_CHANNEL_ID, self.session)
        if new_manifesto:
            self.cwel_manifesto = new_manifesto

    # === Logika LLM (Gemini) ===
    
    async def _call_gemini(self, prompt: str, system_instruction: str = None, json_mode: bool = False, max_retries: int = 3, base_delay: int = 2) -> str:
        """Centralna metoda do asynchronicznego wywoływania API Gemini z mechanizmem retry."""
        def generate():
            kwargs = {}
            if system_instruction:
                kwargs['system_instruction'] = system_instruction
            if json_mode:
                kwargs['response_mime_type'] = "application/json"
                
            return self.gemini.models.generate_content(
                model="gemini-3.1-flash-lite-preview",
                contents=prompt,
                config=genai.types.GenerateContentConfig(**kwargs)
            )

        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(generate)
                return response.text
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"Błąd krytyczny API Gemini po {max_retries} próbach: {e}")
                    raise
                delay = base_delay * (2 ** attempt)
                print(f"Błąd API Gemini ({e}). Ponawiam (próba {attempt + 1}/{max_retries}) za {delay} sekund...")
                await asyncio.sleep(delay)

    async def generate_content_async(self, message: discord.Message, history: list) -> str:
        """Generuje odpowiedź konwersacyjną (czat)."""
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

        return await self._call_gemini(contents, system_instruction=system_instruction)

    async def validate_daily_challenge_content(self, content: str) -> dict:
        """Walidacja dziennego wyzwania z użyciem LLM."""
        prompt = (
            f"Oceń czy poniższa wiadomość jest sensownym wyzwaniem/zadaniem dziennym do wykonania, "
            f"czy raczej bezsensownym spamem, wiadomością która nie jest zadaniem, lub czymś nierealnym.\n"
            f"Wiadomość: {content}\n\n"
            f"Zwróć sam czysty obiekt JSON (bez znaczników markdown) zawierający klucze:\n"
            f"- \"is_valid\" (boolean): true jeśli to sensowne wyzwanie, false w przeciwnym razie.\n"
            f"- \"reason\" (string): krótkie uzasadnienie decyzji po polsku."
        )
        response_text = await self._call_gemini(prompt, json_mode=True)
        return json.loads(response_text)

    async def parse_challenge_content(self, content: str, author_name: str) -> dict:
        """Parsowanie i walidacja standardowego wyzwania przy pomocy LLM."""
        now_iso = datetime.datetime.now(ZoneInfo("Europe/Warsaw")).isoformat()
        prompt = (
            f"Przeanalizuj wyzwanie opisane w wiadomości wejściowej i wyodrębnij z niego kluczowe informacje.\n"
            f"Aktualna data i czas w tej strefie: {now_iso}\n"
            f"Wiadomość wejściowa: {content}\n\n"
            f"Zwróć sam czysty obiekt JSON (bez znaczników markdown, bez dodatkowego tekstu) zawierający klucze:\n"
            f"- \"content\" (string): Treść i opis wyzwania.\n"
            f"- \"author\" (string): Autor lub osoba na którą rzucono wyzwanie. Jeśli nie jest jasno powiedziane, przypisz domyślnie: '{author_name}'.\n"
            f"- \"start_at\" (string lub null): Data i czas rozpoczęcia wyzwania (w formacie ISO 8601, np. 2026-05-02T10:00:00Z). Zgadnij z kontekstu, jeśli nie ma i rzuć null.\n"
            f"- \"end_at\" (string lub null): Data i czas zakończenia wyzwania (w formacie ISO 8601, np. 2026-05-05T23:59:59Z). Zgadnij z kontekstu (np. do jutra, do piątku), jeśli wpisano ogólnikowo lub jeśli w ogóle nie ma, rzuć null.\n"
            f"- \"is_sensible\" (boolean): true jeśli wiadomość opisuje sensowne, logiczne zadanie/wyzwanie. false jeśli to spam, głupota, lub brak logicznego zadania.\n"
            f"- \"reason\" (string): krótkie uzasadnienie decyzji dla is_sensible po polsku.\n"
        )
        response_text = await self._call_gemini(prompt, json_mode=True)
        return json.loads(response_text)

    # === Helpers ===
    
    async def _log_action(self, text: str):
        """Wysyła wiadomość do kanału logów (jeśli istnieje)."""
        logs_channel = self.get_channel(LOGS_CHANNEL_ID)
        if logs_channel:
            await logs_channel.send(text)

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

    async def create_thread(self, message: discord.Message):
        try:
            await message.create_thread(name=message.content[:100])
        except Exception as e:
            print(f"Error creating thread: {e}")

    # === Handlers ===
    
    async def handle_daily_challenge(self, message: discord.Message):
        try:
            daily_content = message.content.strip()
            if not daily_content:
                await message.delete()
                await self._log_action(f"{message.author.mention} Musisz podać treść dziennego challange'a, nie może być to obrazek.")
                return
            
            validation_data = await self.validate_daily_challenge_content(daily_content)
            
            if not validation_data.get("is_valid"):
                await message.delete()
                await self._log_action(f"{message.author.mention} Odrzucono dzienny challenge. Uzasadnienie: {validation_data.get('reason', 'To nie wygląda na sensowne zadanie.')}")
                return

            await add_daily_challenge_to_database(daily_content, self.session)
            await self._log_action(f"Dzienny challange został dodany do bazy danych przez {message.author.mention}:\n> {daily_content}")
        except Exception as e:
            print(f"Error adding daily challenge: {e}")
            await self._log_action("Wystąpił błąd podczas dodawania dziennego challange'a.")

    async def handle_challenge(self, message: discord.Message):
        try:
            challenge_content = message.content.strip()
            if not challenge_content:
                await message.delete()
                await self._log_action(f"{message.author.mention} Nie wysyłaj tu obrazków ani nie odpowiadaj na wiadomości, od tego masz thready.")
                return
            
            challenge_data = await self.parse_challenge_content(challenge_content, message.author.display_name)

            if not challenge_data.get("is_sensible"):
                await message.delete()
                await self._log_action(f"{message.author.mention} Odrzucono wyzwanie. Uzasadnienie: {challenge_data.get('reason', 'To nie jest sensowne wyzwanie.')}")
                return
            if not challenge_data.get("end_at"):
                await message.delete()
                await self._log_action(f"{message.author.mention} Odrzucono wyzwanie. Musisz podać do kiedy trwa to wyzwanie (np. 'do jutra', 'do piątku', podać konkretną datę).")
                return

            db_data = {k: v for k, v in challenge_data.items() if v is not None and k not in ["is_sensible", "reason"]}
            await add_challenge_to_database(db_data, self.session)
            
            reply_text = (
                f"✅ Wyzwanie podjęte i zapisane\n"
                f"**Dotyczy:** {challenge_data.get('content', 'Brak treści')}\n"
                f"**Autor/Kogo dotyczy:** {message.author.mention}\n"
            )
            
            def format_iso_date(iso_str):
                try:
                    return datetime.datetime.fromisoformat(iso_str.replace("Z", "+00:00")).strftime("%d-%m-%Y")
                except Exception:
                    return iso_str

            if 'start_at' in challenge_data:
                reply_text += f"**Od:** {format_iso_date(challenge_data['start_at'])}\n"
            if 'end_at' in challenge_data:
                reply_text += f"**Do:** {format_iso_date(challenge_data['end_at'])}\n"

            await self._log_action(reply_text)
        except Exception as e:
            print(f"Error adding challenge: {e}")
            await self._log_action("Wystąpił błąd podczas analizowania (Gemini) lub dodawania challange'a.")

    async def handle_bot_mention(self, message: discord.Message):
        print(f"Received mention, length: {len(message.content)}")

        # Jeśli odpisujemy tagując bota na czyjąś wiadomość (dodanie cytatu)
        if message.reference and message.reference.message_id and message.content.strip().lower() == f'<@{self.user.id}>':
            await add_quote_to_database(message, self.session)
            return
        
        # W innym wypadku zwykła konwersacja
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


    # === Zdarzenia Discord (Events) ===
    
    async def on_message(self, message: discord.Message):
        # Ignoruj wiadomości od samego siebie
        if message.author == self.user:
            return

        # Aktualizacja manifestu jeśli wpisano cokolwiek na dedykowanym kanale
        if message.channel.id == CWEL_MANIFESTO_CHANNEL_ID:
            await self.update_manifest()

        # Obsługa kanałów funkcyjnych
        if message.channel.id == DAILY_CHALLENGE_CHANNEL_ID:
            await self.handle_daily_challenge(message)      

        if message.channel.id == CHALLENGE_CHANNEL_ID:
            await self.handle_challenge(message)

        # Jeśli bot został otagowany
        if self.user and self.user.mentioned_in(message):
            await self.handle_bot_mention(message)
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


    # === Zadania okresowe (Tasks) ===
    
    @tasks.loop(time=TIME_TO_ANNOUNCE)
    async def announce_balance(self):
        print("Running scheduled balance announcement task...")
        channel = self.get_channel(BALANCE_ANNOUNCE_CHANNEL_ID)
        
        # Sprawdzanie czy jutro jest nowy miesiąc (czyli dzisiaj last day)
        today = datetime.date.today()
        next_day = today + datetime.timedelta(days=1)
        is_last_day = next_day.month != today.month

        if channel and isinstance(channel, discord.TextChannel) and is_last_day:
            await channel.send(f"<@{minio_id}> <@{veresek_id}> Dzisiaj ostatni dzień miesiąca, zapraszam do rozliczenia za przewinienia! 🗿")

    @tasks.loop(time=DAILY_CHALLENGE_TIME)
    async def daily_challenge(self):
        print("Running scheduled daily challenge task...")
        try:
            challange = await get_random_daily_challenge(self.session)
        except Exception as e:
            print(f"Error fetching daily challenge: {e}")
            challange = "Nie udało się pobrać dziennego challange'a."
            
        try:
            active_challenges = await get_active_challenges(self.session)
            if active_challenges:
                active_challenges_text = "\n".join([f"- **{c.get('author', 'Ktoś')}**: {c.get('content', '')}" for c in active_challenges])
            else:
                active_challenges_text = "Obecnie brak aktywnych wyzwań."
        except Exception as e:
            print(f"Error fetching active challenges: {e}")
            active_challenges_text = "Nie udało się pobrać aktywnych wyzwań."
            
        try:
            quote = await get_random_quote(self.session)
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
