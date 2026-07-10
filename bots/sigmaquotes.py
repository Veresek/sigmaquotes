import os
import datetime
import asyncio
import json
import time
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
        self.conversation_memory = {}  # {channel_id: {"entries": [...], "last_activity": timestamp}}

    async def setup_hook(self):
        # Inicjalizacja zadań w tle i sesji HTTP
        self.session = aiohttp.ClientSession()
        self.announce_balance.start()
        # self.daily_challenge.start()

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

    # === Pamięć konwersacji ===

    MEMORY_TTL = 1800  # 30 minut
    MEMORY_MAX_ENTRIES = 20

    def _update_memory(self, channel_id: int, user_msg: str, user_name: str, bot_response: str):
        """Zapisuje ostatnią wymianę do pamięci krótkoterminowej."""
        now = time.time()
        if channel_id not in self.conversation_memory:
            self.conversation_memory[channel_id] = {"entries": [], "last_activity": now}

        mem = self.conversation_memory[channel_id]
        mem["last_activity"] = now
        mem["entries"].append({
            "user": user_name,
            "content": user_msg[:600],
            "bot_response": bot_response[:600],
            "time": now
        })

        if len(mem["entries"]) > self.MEMORY_MAX_ENTRIES:
            mem["entries"] = mem["entries"][-self.MEMORY_MAX_ENTRIES:]

    def _get_memory(self, channel_id: int) -> list:
        """Pobiera aktywną pamięć konwersacji dla kanału (TTL 30 min)."""
        now = time.time()
        mem = self.conversation_memory.get(channel_id)
        if not mem or (now - mem["last_activity"]) > self.MEMORY_TTL:
            if channel_id in self.conversation_memory:
                del self.conversation_memory[channel_id]
            return []
        return mem["entries"]

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
                model="gemini-3.1-flash-lite",
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

    async def generate_content_async(self, message: discord.Message, history: list, memory: list = None, context_type: str = "mention", old_reply_text: str = None) -> str:
        """Generuje odpowiedź konwersacyjną (czat) z pełnym kontekstem."""
        # Formatowanie historii ze strukturą reply i oznaczeniem bota
        history_lines = []
        for msg in history:
            prefix = "🤖 " if msg.get("is_bot") else ""
            reply_tag = f"[↩ do {msg['reply_to']}] " if "reply_to" in msg else ""
            history_lines.append(f"{prefix}{reply_tag}{msg['username']}: {msg['content']}")
        history_text = "\n".join(history_lines)

        # Formatowanie pamięci sesyjnej
        memory_text = ""
        if memory:
            memory_lines = []
            for entry in memory:
                memory_lines.append(f"  {entry['user']}: {entry['content']}")
                memory_lines.append(f"  🤖 SigmaQuotesBot: {entry['bot_response']}")
            memory_text = "\n".join(memory_lines)

        # Oczyszczenie treści z raw mentionów bota
        user_content = message.content.replace(f'<@{self.user.id}>', '').strip()
        if not user_content:
            user_content = "[Użytkownik zaczepia Cię bez słowa]"

        now = datetime.datetime.now(ZoneInfo("Europe/Warsaw"))
        is_thread = isinstance(message.channel, discord.Thread)

        contents = f"Kontekst ostatnich wiadomości na kanale (od najstarszej do najnowszej):\n{history_text}\n\n"
        if memory_text:
            contents += f"Twoja pamięć wcześniejszych rozmów na tym kanale (starsze, spoza widocznej historii):\n{memory_text}\n\n"
        if old_reply_text:
            contents += f"Użytkownik odpowiada (reply) na Twoją BARDZO STARĄ wiadomość (sprzed historii), która brzmiała:\n{old_reply_text}\n\n"
        contents += f"Odpowiedz na tę wiadomość: '{user_content}' (autor: {message.author.display_name})"

        context_desc = {
            "mention": "Użytkownik oznaczył cię @mention w wiadomości.",
            "reply": "Użytkownik odpowiedział (reply) na twoją wcześniejszą wiadomość — kontynuuj rozmowę naturalnie.",
        }

        system_instruction = (
            "Nazywasz się SigmaQuotesBot. Jesteś po prostu ziomkiem z serwera Discord, kumplem do pogadania na luzie. "
            "Reaguj adekwatnie do sytuacji, miej własne zdanie i normalnie dyskutuj z użytkownikami. Możesz też czasem użyć jakiejś emotikony.\n\n"
            f"<kontekst>\n"
            f"Aktualna data i czas: {now.strftime('%Y-%m-%d %H:%M:%S')} ({now.strftime('%A')})\n"
            f"Typ interakcji: {context_desc.get(context_type, context_desc['mention'])}\n"
            f"{'Jesteś w wątku (thread) — kontynuuj temat wątku.' if is_thread else 'Jesteś na kanale ogólnym.'}\n"
            f"</kontekst>\n\n"
            "<charakter>\n"
            f"{self.cwel_manifesto}\n"
            "</charakter>\n\n"
            "Ten manifest to Twoje poglądy na świat, ale traktuj je jako swoją podświadomość. Nie cytuj go, nie wspominaj o nim "
            "ani nie wymuszaj ciągłej motywacji czy 'lecenia do roboty' na siłę w każdej wiadomości. "
            "Bądź po prostu normalnym, spoko gościem, z którym można o wszystkim pogadać.\n\n"
            "<zasady_osobowosci>\n"
            "- Zachowuj się niezwykle naturalnie, używaj slangu i luźnego języka. Nie bądź sztywny ani formalny.\n"
            "- Odpowiadaj zwięźle (max 3 zdania), chyba że ktoś faktycznie potrzebuje pomocy i musisz coś wytłumaczyć.\n"
            "- Pisz ZAWSZE po polsku, na inne języki przełączaj się tylko na wyraźne żądanie.\n"
            "- Nie jesteś asystentem od programowania. Nie generuj kodu bez absolutnej konieczności.\n"
            "- NIGDY nikogo nie oznaczaj (żadnych @username ani <@id>). To co piszesz to już automatycznie odpowiedź.\n"
            "- Absolutnie nigdy nie pytaj 'W czym mogę pomóc?' ani nie przedstawiaj się.\n"
            "</zasady_osobowosci>\n\n"
            "<zasady_konwersacji>\n"
            "- Jeśli ktoś kontynuuje z tobą rozmowę (reply lub ponowny mention), KONTYNUUJ wątek. Nie zaczynaj od nowa.\n"
            "- Pamiętaj o kontekście wcześniejszych wiadomości. Jeśli ktoś nawiązuje do czegoś co było powiedziane wcześniej, reaguj na to.\n"
            "- Wiadomości oznaczone 🤖 to twoje własne wcześniejsze wypowiedzi. Bądź spójny z tym co mówiłeś.\n"
            "- Rozróżniaj rozmowy z różnymi osobami. Nie mieszaj kontekstów.\n"
            "- Jeśli ktoś cię trolluje, możesz trollować z powrotem. Nie bądź potulny.\n"
            "- Nie powtarzaj się. Nie mów tego samego co powiedziałeś wcześniej w tej konwersacji.\n"
            "</zasady_konwersacji>"
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

    async def scrape_channel_history(self, channel: discord.abc.Messageable, limit=15) -> list:
        """Pobiera historię kanału z rozwiązywaniem reply w obrębie pobranego zakresu."""
        raw_messages = []
        async for msg in channel.history(limit=limit, oldest_first=False):
            if msg.type != discord.MessageType.default:
                continue
            if not msg.content.strip():
                continue
            raw_messages.append(msg)

        raw_messages.reverse()

        # Lookup do rozwiązywania reply bez dodatkowych zapytań API
        msg_lookup = {msg.id: msg for msg in raw_messages}

        history = []
        for msg in raw_messages:
            entry = {
                "id": msg.id,
                "username": msg.author.display_name,
                "content": msg.content.strip(),
                "is_bot": msg.author == self.user,
            }
            if msg.reference and msg.reference.message_id:
                ref = msg.reference.cached_message or msg_lookup.get(msg.reference.message_id)
                if ref:
                    entry["reply_to"] = ref.author.display_name
            history.append(entry)

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

    async def handle_bot_conversation(self, message: discord.Message, context_type: str = "mention"):
        """Obsługa konwersacji z botem (mention lub reply)."""
        print(f"Received {context_type}, length: {len(message.content)}")

        # Dodawanie cytatu — tylko gdy ktoś oznaczy bota samym @ na czyjejś wiadomości
        if context_type == "mention" and message.reference and message.reference.message_id and message.content.strip().lower() == f'<@{self.user.id}>':
            await add_quote_to_database(message, self.session)
            return

        is_thread = isinstance(message.channel, discord.Thread)
        history_limit = 25 if is_thread else 15

        history = await self.scrape_channel_history(message.channel, limit=history_limit)
        memory = self._get_memory(message.channel.id)

        old_reply_text = None
        if context_type == "reply" and message.reference and message.reference.message_id:
            if not any(msg.get("id") == message.reference.message_id for msg in history):
                try:
                    ref_msg = message.reference.cached_message
                    if not ref_msg:
                        ref_msg = await message.channel.fetch_message(message.reference.message_id)
                    if ref_msg:
                        old_reply_text = ref_msg.content.strip()
                except Exception:
                    pass

        try:
            response = await self.generate_content_async(message, history=history, memory=memory, context_type=context_type, old_reply_text=old_reply_text)

            if response and response.strip():
                await message.reply(response)
                clean_content = message.content.replace(f'<@{self.user.id}>', '').strip() or message.content
                self._update_memory(message.channel.id, clean_content, message.author.display_name, response)
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
        # if message.channel.id == DAILY_CHALLENGE_CHANNEL_ID:
        #     await self.handle_daily_challenge(message)

        # if message.channel.id == CHALLENGE_CHANNEL_ID:
        #     await self.handle_challenge(message)

        # Jeśli bot został otagowany
        if self.user and self.user.mentioned_in(message):
            await self.handle_bot_conversation(message, context_type="mention")
            return

        # Jeśli ktoś odpowiedział (reply) na wiadomość bota
        if message.reference and message.reference.message_id:
            try:
                ref_msg = message.reference.cached_message
                if ref_msg is None:
                    ref_msg = await message.channel.fetch_message(message.reference.message_id)
                if ref_msg and ref_msg.author == self.user:
                    await self.handle_bot_conversation(message, context_type="reply")
                    return
            except Exception:
                pass

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
        # try:
        #     challange = await get_random_daily_challenge(self.session)
        # except Exception as e:
        #     print(f"Error fetching daily challenge: {e}")
        #     challange = "Nie udało się pobrać dziennego challange'a."
            
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
            # await channel.send(f"<@{minio_id}> <@{veresek_id}> Dzienny challange: {challange}")
            await channel.send(f"Aktualne wyzwania:\n{active_challenges_text}")
            await channel.send(f"Cytat dnia:\n**{quote['content']}**\n- *{quote['author']}*")

if __name__ == "__main__":
    if not TOKEN_DISCORD:
        print("Error: SIGMA_TOKEN brakujacy w zmirnnych środowiskowych (.env).")
    else:
        bot = SigmaQuotesBot()
        bot.run(TOKEN_DISCORD)
