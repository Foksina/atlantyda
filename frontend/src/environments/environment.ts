import type { AppEnvironment } from './environment.model';

/** Konfiguracja produkcyjna. Używana przez `ng build` i `ng serve --configuration production`. */
export const environment: AppEnvironment = {
  production: true,
  apiUrl: 'https://atlantyda.onrender.com/api',
};
