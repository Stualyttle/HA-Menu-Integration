import { Component, inject } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { I18nService } from './i18n.service';

export interface ConfirmationDialogData {
  title: string;
  message: string;
  confirmLabel: string;
}

@Component({
  selector: 'mp-confirmation-dialog',
  standalone: true,
  imports: [MatButtonModule, MatDialogModule],
  template: `
    <h2 mat-dialog-title>{{ data.title }}</h2>
    <mat-dialog-content>{{ data.message }}</mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" [mat-dialog-close]="false">
        {{ i18n.t('common.cancel') }}
      </button>
      <button mat-flat-button color="warn" type="button" [mat-dialog-close]="true">
        {{ data.confirmLabel }}
      </button>
    </mat-dialog-actions>
  `,
})
export class ConfirmationDialogComponent {
  readonly data = inject<ConfirmationDialogData>(MAT_DIALOG_DATA);
  readonly i18n = inject(I18nService);
  readonly dialogRef = inject(MatDialogRef<ConfirmationDialogComponent, boolean>);
}
