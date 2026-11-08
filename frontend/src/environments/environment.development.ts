import type { AppEnvironment } from './environment.model';

/** Konfiguracja lokalna. Podmieniana przy `ng serve` i `ng build --configuration development`. */
export const environment: AppEnvironment = {
  production: false,
  apiUrl: 'http://localhost:8000/api',
};
