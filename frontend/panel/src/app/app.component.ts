import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatListModule } from '@angular/material/list';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatToolbarModule } from '@angular/material/toolbar';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { api } from '../../../shared/api/instance.js';
import type { OnboardingStatus, Settings } from '../../../shared/api/types';
import { I18nService } from './i18n.service';
import { MessageService } from './message.service';
import { OnboardingComponent } from './onboarding.component';

interface NavigationLink {
  path: string;
  label: string;
}

@Component({
  selector: 'mp-root',
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatCardModule,
    MatListModule,
    MatProgressSpinnerModule,
    MatSidenavModule,
    MatToolbarModule,
    OnboardingComponent,
    RouterLink,
    RouterLinkActive,
    RouterOutlet,
  ],
  template: `
    @if (status() === 'loading') {
      <mat-card>
        <mat-card-content>
          <mat-spinner diameter="32" />
          {{ i18n.t('app.loading') }}
        </mat-card-content>
      </mat-card>
    } @else if (status() === 'error') {
      <mat-card>
        <mat-card-header>
          <mat-card-title>{{ i18n.t('app.loadFailed') }}</mat-card-title>
        </mat-card-header>
        <mat-card-actions>
          <button mat-flat-button type="button" (click)="load()">
            {{ i18n.t('app.retry') }}
          </button>
        </mat-card-actions>
      </mat-card>
    } @else if (setupRequired()) {
      <mp-onboarding (completed)="load()" />
    } @else {
      <mat-sidenav-container>
        <mat-sidenav mode="side" opened>
          <mat-toolbar>{{ i18n.t('app.title') }}</mat-toolbar>
          <mat-nav-list aria-label="{{ i18n.t('app.navLabel') }}">
            @for (link of links; track link.path) {
              <a
                mat-list-item
                [routerLink]="link.path"
                routerLinkActive="mdc-list-item--activated"
                [routerLinkActiveOptions]="{ exact: true }"
                [attr.aria-label]="i18n.t(link.label)"
              >
                {{ i18n.t(link.label) }}
              </a>
            }
          </mat-nav-list>
        </mat-sidenav>
        <mat-sidenav-content>
          <mat-toolbar>
            <span>{{ i18n.t('app.workspace') }}</span>
          </mat-toolbar>
          <main>
            <router-outlet />
          </main>
        </mat-sidenav-content>
      </mat-sidenav-container>
    }
  `,
})
export class AppComponent implements OnInit {
  private readonly router = inject(Router);
  readonly i18n = inject(I18nService);
  private readonly messages = inject(MessageService);
  readonly status = signal<'loading' | 'ready' | 'error'>('loading');
  readonly setupRequired = signal(false);
  readonly links: NavigationLink[] = [
    { path: '/dashboard', label: 'tabs.home' },
    { path: '/menu', label: 'tabs.menu' },
    { path: '/items', label: 'tabs.items' },
    { path: '/categories', label: 'tabs.categories' },
    { path: '/rules', label: 'tabs.rules' },
    { path: '/stock', label: 'tabs.stock' },
    { path: '/settings', label: 'tabs.settings' },
    { path: '/import-export', label: 'tabs.importExport' },
  ];

  ngOnInit(): void {
    void this.load();
  }

  async load(): Promise<void> {
    this.status.set('loading');
    try {
      const [settings, onboarding] = await Promise.all([
        api.settings.get(),
        api.onboarding.get(),
      ]);
      this.i18n.setLocale(this.resolveLanguage(settings));
      this.setupRequired.set(onboarding.required);
      this.status.set('ready');
    } catch (error) {
      this.status.set('error');
      this.messages.error(error);
    }
  }

  private resolveLanguage(settings: Settings): string {
    if (settings.language === 'auto') return navigator.language;
    return settings.language;
  }
}
