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

  async getRandomQuote() {
    const quote = await prisma.$queryRaw<
      { id: number; content: string; author: string; created_at: Date | null }[]
    >`SELECT * FROM "quotes" ORDER BY RANDOM() LIMIT 1`;
    return quote[0] || { content: '', author: '' };
  }

  async getManifesto() {
    const manifesto = await prisma.manifest.findFirst({
      orderBy: {
        created_at: 'desc',
      },
    });
    return manifesto || { content: '' };
  }

  async getDailyChallenge() {
    const challenge = await prisma.$queryRaw<
      { id: number; content: string }[]
    >`SELECT * FROM "daily_challenges" ORDER BY RANDOM() LIMIT 1`;
    return challenge[0] || { content: '' };
  }

  async getActiveChallenges() {
    const now = new Date();
    return await prisma.active_challenges.findMany({
      where: {
        start_at: {
          lte: now,
        },
        end_at: {
          gte: now,
        },
      },
    });
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

  async createDailyChallenge(content: string) {
    return await prisma.daily_challenges.create({
      data: {
        content,
      },
    });
  }

  async createChallenge(
    author: string,
    content: string,
    start_at: Date,
    end_at: Date,
  ) {
    return await prisma.active_challenges.create({
      data: {
        author,
        content,
        start_at,
        end_at,
      },
    });
  }
}
