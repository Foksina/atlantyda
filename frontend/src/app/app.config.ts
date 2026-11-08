import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';
import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';

import { environment } from '../environments/environment';
import { routes } from './app.routes';
import { apiErrorInterceptor } from './core/api/api-error.interceptor';
import { API_TIMEOUT_MS, API_URL, DEFAULT_API_TIMEOUT_MS } from './core/config/api-url';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    provideHttpClient(withFetch(), withInterceptors([apiErrorInterceptor])),
    { provide: API_URL, useValue: environment.apiUrl },
    { provide: API_TIMEOUT_MS, useValue: DEFAULT_API_TIMEOUT_MS },
  ],
};
