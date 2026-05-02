import { IsString, IsNotEmpty, MaxLength, IsOptional, IsDateString } from 'class-validator';

export class CreateQuoteDto {
  @IsString()
  @IsNotEmpty({ message: 'Autor nie może być pusty.' })
  @MaxLength(100, { message: 'Autor nie może mieć więcej niż 100 znaków.' })
  author: string;

  @IsString()
  @IsNotEmpty({ message: 'Treść cytatu nie może być pusta.' })
  content: string;
}

export class UpdateManifestoDto {
  @IsString()
  @IsNotEmpty({ message: 'Treść manifestu nie może być pusta.' })
  content: string;
}

export class CreateDailyChallengeDto {
  @IsString()
  @IsNotEmpty({ message: 'Treść wyzwania nie może być pusta.' })
  content: string;
}

export class CreateChallengeDto {
  @IsString()
  @IsNotEmpty({ message: 'Autor nie może być pusty.' })
  @MaxLength(100, { message: 'Autor nie może mieć więcej niż 100 znaków.' })
  author: string;

  @IsString()
  @IsNotEmpty({ message: 'Treść wyzwania nie może być pusta.' })
  content: string;

  @IsOptional()
  @IsDateString({}, { message: 'start_at musi być w formacie ISO 8601.' })
  start_at?: string;

  @IsDateString({}, { message: 'end_at musi być w formacie ISO 8601.' })
  end_at: string;
}
