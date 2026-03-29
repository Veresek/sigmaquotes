import { Injectable } from '@nestjs/common';
import { prisma } from './prisma';

@Injectable()
export class AppService {
  getHello(): string {
    return 'Hello World!';
  }

  async getQuotes() {
    return await prisma.quotes.findMany();
  }

  async createQuote(author: string, content: string) {
    return await prisma.quotes.create({
      data: {
        author,
        content,
      },
    });
  }
}
