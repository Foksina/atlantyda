import { InjectionToken } from '@angular/core';

export const API_URL = new InjectionToken<string>('API_URL');

/** Publiczna instancja Rendera po uśpieniu może odpowiadać dopiero po kilkudziesięciu sekundach. */
export const DEFAULT_API_TIMEOUT_MS = 120_000;

export const API_TIMEOUT_MS = new InjectionToken<number>('API_TIMEOUT_MS');
