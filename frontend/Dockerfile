FROM node:22-alpine

WORKDIR /app

COPY package*.json ./

RUN npm install

COPY . .

# Tworzymy produkcyjny, lekki kod, zamiast zarlocznego "dev"
RUN npm run build

EXPOSE 3000

# Wystawiamy lokalny podglad przez swiat na port 3000 dla Dockera
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "3000"]