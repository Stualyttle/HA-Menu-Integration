import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
  {
    path: 'dashboard',
    loadComponent: () => import('./dashboard.component').then((module) => module.DashboardComponent),
  },
  { path: 'menu', loadComponent: () => import('./menu.component').then((module) => module.MenuComponent) },
  { path: 'items', loadComponent: () => import('./items.component').then((module) => module.ItemsComponent) },
  {
    path: 'categories',
    loadComponent: () => import('./categories.component').then((module) => module.CategoriesComponent),
  },
  { path: 'rules', loadComponent: () => import('./rules.component').then((module) => module.RulesComponent) },
  { path: 'stock', loadComponent: () => import('./stock.component').then((module) => module.StockComponent) },
  {
    path: 'settings',
    loadComponent: () => import('./settings.component').then((module) => module.SettingsComponent),
  },
  {
    path: 'import-export',
    loadComponent: () =>
      import('./import-export.component').then((module) => module.ImportExportComponent),
  },
  { path: '**', redirectTo: 'dashboard' },
];
