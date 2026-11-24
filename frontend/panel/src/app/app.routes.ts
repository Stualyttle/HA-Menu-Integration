import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
  {
    path: 'dashboard',
    loadComponent: () =>
      import('@app/pages/dashboard/dashboard.component').then((module) => module.DashboardComponent),
  },
  {
    path: 'menu',
    loadComponent: () => import('@app/pages/menu/menu.component').then((module) => module.MenuComponent),
  },
  {
    path: 'items',
    loadComponent: () => import('@app/pages/items/items.component').then((module) => module.ItemsComponent),
  },
  {
    path: 'categories',
    loadComponent: () =>
      import('@app/pages/categories/categories.component').then((module) => module.CategoriesComponent),
  },
  {
    path: 'rules',
    loadComponent: () => import('@app/pages/rules/rules.component').then((module) => module.RulesComponent),
  },
  {
    path: 'stock',
    loadComponent: () => import('@app/pages/stock/stock.component').then((module) => module.StockComponent),
  },
  {
    path: 'settings',
    loadComponent: () =>
      import('@app/pages/settings/settings.component').then((module) => module.SettingsComponent),
  },
  {
    path: 'import-export',
    loadComponent: () =>
      import('@app/pages/import-export/import-export.component').then(
        (module) => module.ImportExportComponent,
      ),
  },
  { path: '**', redirectTo: 'dashboard' },
];
