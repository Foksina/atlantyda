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

## Wdrożenie

Publiczny adres API: https://atlantyda.onrender.com

Pierwsze wdrożenie: 1 listopada 2026. Aplikacja stoi na darmowym planie Render i jest utrzymywana do 1 grudnia 2026.

Darmowa instancja usypia się po okresie bezczynności - 15 minut. Render podaje: „Your free instance will spin down with inactivity, which can delay requests by 50 seconds or more.” Pierwsze żądanie po uśpieniu może więc zająć około 50 sekund lub dłużej. Kolejne żądania, gdy instancja już działa, odpowiadają od razu. Sprawdzenie, czy usługa wstała: https://atlantyda.onrender.com/api/health

## Uruchomienie lokalne

Instrukcja instalacji zależności, konfiguracji środowiska i uruchamiania poszczególnych części aplikacji zostanie uzupełniona w trakcie realizacji projektu.

## Bezpieczeństwo

- Nie należy umieszczać haseł, kluczy API ani innych sekretów w repozytorium.
- Plik `.env` zawierający lokalną konfigurację powinien być wykluczony z kontroli wersji.
- Plik `.env.example` powinien zawierać wyłącznie przykładowe wartości zmiennych środowiskowych.