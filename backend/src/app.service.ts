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

  async getManifesto(): Promise<
    { content: string; created_at?: Date } | { content: string }
  > {
    const manifesto = await prisma.manifest.findFirst({
      orderBy: {
        created_at: 'desc',
      },
    });
    return manifesto || { content: '' };
  }

  async updateManifesto(content: string) {
    return await prisma.manifest.create({
      data: {
        content,
      },
    });
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
