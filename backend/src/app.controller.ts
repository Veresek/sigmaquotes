import { Controller, Get, Post, Body, UseGuards } from '@nestjs/common';
import { AppService } from './app.service';
import { ApiKeyGuard } from './api-key.guard';
import {
  CreateQuoteDto,
  UpdateManifestoDto,
  CreateDailyChallengeDto,
  CreateChallengeDto,
} from './dto';

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
  @UseGuards(ApiKeyGuard)
  async updateManifesto(@Body() body: UpdateManifestoDto) {
    return this.appService.updateManifesto(body.content);
  }

  @Post('quotes')
  @UseGuards(ApiKeyGuard)
  async createQuote(@Body() body: CreateQuoteDto) {
    return this.appService.createQuote(body.author, body.content);
  }

  @Post('daily-challenge')
  @UseGuards(ApiKeyGuard)
  async createDailyChallenge(@Body() body: CreateDailyChallengeDto) {
    return this.appService.createDailyChallenge(body.content);
  }

  @Post('challenge')
  @UseGuards(ApiKeyGuard)
  async createChallenge(@Body() body: CreateChallengeDto) {
    return this.appService.createChallenge(
      body.author,
      body.content,
      body.start_at ? new Date(body.start_at) : new Date(),
      new Date(body.end_at),
    );
  }
}
