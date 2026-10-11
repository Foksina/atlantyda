# Atlantyda

**System monitorowania środowiska podwodnej stacji badawczej**

Aplikacja internetowa służąca do zbierania, walidowania i wizualizacji pomiarów środowiskowych pochodzących z fikcyjnej podwodnej stacji badawczej Atlantyda.

## Technologie

- **Frontend:** Angular, TypeScript, SCSS
- **Backend:** Django, Django REST Framework
- **Baza danych:** PostgreSQL
- **Generator pomiarów:** Python
- **Aktualizacje wykresów w czasie rzeczywistym:** Server-Sent Events (SSE)
- **Automatyzacja testów i integracji:** GitHub Actions

## Struktura repozytorium

- `frontend/` — aplikacja frontendowa Angular
- `backend/` — backend Django udostępniający REST API
- `generator/` — generator wysyłający pomiary do API
- `database/` — dokumentacja bazy danych i diagram ERD
- `docs/` — dokumentacja projektu oraz kontrakt API
- `tests/contract/` — testy kontraktowe dostarczone przez prowadzącego

## Uruchomienie lokalne

Instrukcja instalacji zależności, konfiguracji środowiska i uruchamiania poszczególnych części aplikacji zostanie uzupełniona w trakcie realizacji projektu.

## Bezpieczeństwo

- Nie należy umieszczać haseł, kluczy API ani innych sekretów w repozytorium.
- Plik `.env` zawierający lokalną konfigurację powinien być wykluczony z kontroli wersji.
- Plik `.env.example` powinien zawierać wyłącznie przykładowe wartości zmiennych środowiskowych.