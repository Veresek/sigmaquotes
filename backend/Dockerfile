FROM node:22-alpine

# Dodanie openssl potrzebnego dla Prisma w Alpine Linuksie
RUN apk add --no-cache openssl

WORKDIR /app

COPY package*.json ./

RUN npm install

COPY . .

# Konieczne, abysmy mieli wygenerowanego klienta dla NestJS zanim wywola builda
RUN npx prisma generate

RUN npm run build

EXPOSE 8000

# Wystawiamy komende uruchamiajacą na żywo migrację bazy danych + start aplikacji
CMD sh -c "npx prisma migrate deploy && npm run start:prod"