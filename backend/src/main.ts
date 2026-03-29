import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  // Dodajemy '0.0.0.0' aby aplikacja wewnątrz Dockera nasłuchiwała na zewnątrz sieci kontenera
  await app.listen(process.env.PORT ?? 8000, '0.0.0.0');
  app.enableCors({
    origin: [
      'http://localhost:3000',
      'http://localhost:3002',
      process.env.FRONTEND_URL || 'http://localhost:3000',
    ],
    credentials: true,
  });
}
const a = bootstrap();
console.log(a);
