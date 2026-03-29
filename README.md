# SigmaQuotes 🚀

SigmaQuotes to kompleksowy projekt łączący bota Discord opartego na sztucznej inteligencji, backend w NestJS, bazę danych PostgreSQL oraz frontend w React.

## 🏗️ Struktura Repozytorium

Projekt został podzielony na trzy główne moduły (monorepo):

- `/bots` - Bot Discord działający w Pythonie (korzystający z bibliotek `discord.py` i `google-genai`). Obsługuje pobieranie i wysyłanie manifestów oraz generuje agresywno-pomocne odpowiedzi opierając się na promptach AI.
- `/backend` - Serwer napisany w TypeScript przy użyciu frameworka NestJS. Używa Prisma ORM do komunikacji z bazą PostgreSQL.
- `/frontend` - Interfejs użytkownika zbudowany w React i TypeScript (uruchamiany przez Vite).

## 🚀 Technologie

- **Bot:** Python 3.12, `discord.py`, `google-genai`
- **Backend:** Node.js 20, NestJS, Prisma, PostgreSQL
- **Frontend:** React, TypeScript, Vite, TailwindCSS (opcjonalnie)
- **Deployment:** Docker Compose, PM2, GitHub Actions (CI/CD)

## 🛠️ Uruchomienie lokalne

### 1. Klonowanie repozytorium

```bash
git clone https://github.com/Veresek/sigmaquotes.git
cd sigmaquotes
```

### 2. Środowisko zmiennych

Musisz utworzyć odpowiednie pliki `.env`:

**W głównym folderze (`./.env`)** - dla Docker Compose i backendu:

```env
DB_USER=root
DB_PASSWORD=haslo
DB_NAME=sigmaquotes
DATABASE_URL="postgresql://root:haslo@localhost:5432/sigmaquotes?schema=public"
```

**W folderze bota (`./bots/.env`)**:

```env
SIGMA_TOKEN=twoj_token_bota_discord
GEMINI_API_KEY=twoje_api_od_google
CWEL_MANIFESTO_ID=id_kanalu_discord
```

### 3. Aplikacje (Backend + DB + Frontend)

Uruchom kontenery Dockera:

```bash
docker compose up -d --build
```

### 4. Uruchomienie Bota

Zalecane jest uruchamianie bota przez Menadżera Procesów PM2:

```bash
cd bots
pip install -r requirements.txt
pm2 start sigmaquotes.py --name "sigmaquotes" --interpreter python
```

## 🔄 Deployment (CI/CD)

Wdrażanie odbywa się automatycznie za pomocą **GitHub Actions** za każdym razem, gdy kod zostanie wypchnięty na gałąź `main`. Workflow zajmuje się:

1. Pobieraniem kodu na VPS przez SSH.
2. Tworzeniem plików `.env` z GitHub Secrets (`MAIN_ENV_FILE`, `BOTS_ENV_FILE`).
3. Budowaniem i odpalaniem kontenerów aplikacji (Docker Compose).
4. Restartowaniem procesu bota Discordowego (PM2).

## 📝 Zespół i Wkład

Właścicielem repozytorium i głównym autorem jest [Veresek](https://github.com/Veresek).
