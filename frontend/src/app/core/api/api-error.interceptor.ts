import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError, timeout } from 'rxjs';

import { API_TIMEOUT_MS } from '../config/api-url';
import { toApiError } from './api-error';

export const apiErrorInterceptor: HttpInterceptorFn = (request, next) => {
  const timeoutMs = inject(API_TIMEOUT_MS);
  return next(request).pipe(
    timeout(timeoutMs),
    catchError((error: unknown) => throwError(() => toApiError(error))),
  );
};
