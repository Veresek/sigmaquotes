import { Controller, Get, Post, Body } from '@nestjs/common';
import { AppService } from './app.service';

@Controller()
export class AppController {
  constructor(private readonly appService: AppService) {}

  @Get()
  getHello(): string {
    return this.appService.getHello();
  }

  @Get('quotes')
  async getQuotes() {
    return this.appService.getQuotes();
  }

  @Get('random-quote')
  async getRandomQuote() {
    return this.appService.getRandomQuote();
  }

  @Get('manifesto')
  async getManifesto() {
    return this.appService.getManifesto();
  }

  @Get('daily-challenge')
  async getDailyChallenge() {
    return this.appService.getDailyChallenge();
  }

  @Get('active-challenges')
  async getActiveChallenges() {
    return this.appService.getActiveChallenges();
  }

  @Post('manifesto')
  async updateManifesto(@Body() body: { content: string }) {
    return this.appService.updateManifesto(body.content);
  }

  @Post('quotes')
  async createQuote(@Body() body: { author: string; content: string }) {
    return this.appService.createQuote(body.author, body.content);
  }

  @Post('daily-challenge')
  async createDailyChallenge(@Body() body: { content: string }) {
    return this.appService.createDailyChallenge(body.content);
  }

  @Post('challenge')
  async createChallenge(
    @Body()
    body: {
      author: string;
      content: string;
      start_at: Date;
      end_at: Date;
    },
  ) {
    return this.appService.createChallenge(
      body.author,
      body.content,
      body.start_at,
      body.end_at,
    );
  }
}
