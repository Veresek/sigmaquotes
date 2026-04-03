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

  @Get('manifesto')
  async getManifesto() {
    return this.appService.getManifesto();
  }

  @Post('manifesto')
  async updateManifesto(@Body() body: { content: string }) {
    await this.appService.updateManifesto(body.content);
  }

  @Post('quotes')
  async createQuote(@Body() body: { author: string; content: string }) {
    return this.appService.createQuote(body.author, body.content);
  }
}
