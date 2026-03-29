import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  await app.listen(process.env.PORT ?? 3001);
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
