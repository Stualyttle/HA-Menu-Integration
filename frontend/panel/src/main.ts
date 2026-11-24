import { importProvidersFrom } from '@angular/core';
import { MatDialogModule } from '@angular/material/dialog';
import { MatSnackBarModule } from '@angular/material/snack-bar';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { bootstrapApplication } from '@angular/platform-browser';
import { provideRouter, withHashLocation } from '@angular/router';
import { AppLayoutComponent } from '@app/layouts/app-layout.component';
import { routes } from './app/app.routes';

bootstrapApplication(AppLayoutComponent, {
  providers: [
    importProvidersFrom(MatDialogModule, MatSnackBarModule),
    provideAnimationsAsync(),
    provideRouter(routes, withHashLocation()),
  ],
}).catch((error: unknown) => {
  console.error('Menu Planner could not start', error);
});
