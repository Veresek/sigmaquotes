import discord
from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

raw_id = os.getenv('CWEL_MANIFESTO_ID')

TOKEN_DISCORD = os.getenv('SIGMA_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
CWEL_MANIFESTO_ID = int(raw_id) if raw_id and raw_id.isdigit() else None

client = discord.Client(intents=intents)
gemini = genai.Client(api_key=GEMINI_API_KEY)

cwel_manifesto = ""

def generate_content(prompt):
    response = gemini.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=f"Nazywasz się SigmaQuotesBot i jesteś botem na discordzie, który odpowiada na wiadomości. Jeżeli wiadomość którą dostałeś wyzywa cie od cweli też go zwyzywaj, nie oszczędź pocisków, jeżeli nie wyzywa pomóż tak jak chce użytkownik. Tutaj wiadomość którą dostałeś: {prompt}. Odpowiedz w max 2/3 zdaniach po polsku. Nie próbuj nikogo oznaczać to co wyślesz automatycznie będzie odpowiedzią na wiadomość, którą dostałeś. Jeżeli ktoś będzie miał jakieś pytania do bycia cwelem, albo będziesz chciał komuś wytłumaczyć posłuż się punktami z tego manifestu: {cwel_manifesto}"
    )
    return response.text

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

@client.event
async def on_ready():
    print(f'Zalogowano jako {client.user}')
    await cwel_manifesto_scraper()
    print("Manifest wczytany pomyślnie")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if "zasady serwera" in message.content.lower():
        if cwel_manifesto:
            await message.channel.send(cwel_manifesto)
        else:
            await message.channel.send("Niestety manifest jest pusty lub nie został wczytany.")
        return

    if client.user and client.user.mentioned_in(message):
        print(f"Otrzymano wzmiankę, długość: {len(message.content)}")
        if len(message.content) > 10:
            response = generate_content(message.content)
            if response and response.strip():
                await message.reply(response)
            else:
                await message.reply("Nie wiem co powiedzieć, zatkało mnie.")
        else:
            await message.reply("Szkoda prądu na takie gówno")

client.run(str(TOKEN_DISCORD))
