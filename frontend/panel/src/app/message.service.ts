import { Injectable, inject } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { ApiError } from '../../../shared/api/client.js';
import { I18nService } from './i18n.service';

@Injectable({ providedIn: 'root' })
export class MessageService {
  private readonly snackBar = inject(MatSnackBar);
  private readonly i18n = inject(I18nService);

  success(message: string): void {
    this.snackBar.open(message, this.i18n.t('app.dismiss'), { duration: 4000 });
  }

  error(error: unknown): void {
    this.snackBar.open(this.errorText(error), this.i18n.t('app.dismiss'), { duration: 6000 });
  }

  private errorText(error: unknown): string {
    if (!(error instanceof ApiError)) return this.i18n.t('error.generic');
    if (error.code === 'network_error') return this.i18n.t('error.network_error');
    if (error.code === 'not_implemented') return this.i18n.t('error.not_implemented');
    const statusKey = `error.status.${error.status}`;
    const translated = this.i18n.t(statusKey);
    if (translated !== statusKey) return translated;
    return error.message || this.i18n.t('error.generic');
  }
}
