import { Routes } from '@angular/router';

function tymczasowy(path: string, heading: string, summary: string): Routes[number] {
  return {
    path,
    loadComponent: () =>
      import('./features/tymczasowy/tymczasowy').then((module) => module.TymczasowyView),
    title: `${heading} — Atlantyda`,
    data: { heading, summary },
  };
}

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./core/layout/shell').then((module) => module.Shell),
    children: [
      { path: '', pathMatch: 'full', redirectTo: '/pomiary' },
      tymczasowy(
        'pomiary',
        'Pomiary',
        'Publiczny podgląd pomiarów nie jest jeszcze gotowy. Wykres i tabela pojawią się w kolejnym etapie.',
      ),
      tymczasowy(
        'serie',
        'Serie pomiarowe',
        'Informacje o dostępnych seriach pomiarowych nie są jeszcze pokazane w tym widoku.',
      ),
      tymczasowy(
        'admin',
        'Panel administratora',
        'Panel administratora nie jest jeszcze dostępny. Logowanie oraz zarządzanie seriami i czujnikami zostaną dodane później.',
      ),
      { path: '**', redirectTo: '/pomiary' },
    ],
  },
];
