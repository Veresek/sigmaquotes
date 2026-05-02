import { NestFactory } from '@nestjs/core';
import { ValidationPipe } from '@nestjs/common';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  // Globalna walidacja DTO — automatycznie odrzuca requesty z nieprawidłowymi danymi
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true, // Usuwa pola spoza DTO
      forbidNonWhitelisted: true, // Zwraca błąd jeśli wysłano nieznane pola
      transform: true, // Automatyczna transformacja typów
    }),
  );

  await app.listen(process.env.PORT ?? 8000, '0.0.0.0');
}
bootstrap();
