import { CanActivate, ExecutionContext, Injectable, UnauthorizedException } from '@nestjs/common';
import { Request } from 'express';

// Guard sprawdzający API key na endpointach POST

@Injectable()
export class ApiKeyGuard implements CanActivate {
  canActivate(context: ExecutionContext): boolean {
    const request = context.switchToHttp().getRequest<Request>();

    const apiKey = request.headers['x-api-key'];
    const expectedKey = process.env.API_KEY;

    if (!expectedKey) {
      console.warn('UWAGA: API_KEY nie jest ustawiony w zmiennych środowiskowych. Endpointy POST są niezabezpieczone!');
      return true; // Przepuszczamy, żeby nie blokować w środowisku dev bez klucza
    }

    if (apiKey !== expectedKey) {
      throw new UnauthorizedException('Nieprawidłowy lub brakujący klucz API (header x-api-key).');
    }

    return true;
  }
}
