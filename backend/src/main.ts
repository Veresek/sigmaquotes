import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  // Zezwól na CORS (musi być PRED listen)
  app.enableCors({
    origin: [
      'http://localhost:3000',
      'http://localhost:3002',
      'http://localhost:5173', // Domyślny port Vite
      'http://127.0.0.1:5173',
      process.env.FRONTEND_URL || 'http://localhost:3000',
    ],
    credentials: true,
  });
  // Dodajemy '0.0.0.0' aby aplikacja wewnątrz Dockera nasłuchiwała na zewnątrz
  await app.listen(process.env.PORT ?? 8000, '0.0.0.0');
}
const a = bootstrap();
console.log(a);
