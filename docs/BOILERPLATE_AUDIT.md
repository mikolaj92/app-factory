# Audyt boilerplate’u po migracji BOM

Pomiar bazowy wykonano na checkoutach odpowiadających `origin/main`, po migracji do `app-factory v0.6.22`, `my-auth v0.5.4`, `my-usermanager v0.6.5`. Liczby są liniami fizycznymi w plikach integracyjnych, nie rozmiarem domeny aplikacji. Mają wskazywać kolejność redukcji, a nie premiować krótszy kod.

| Host | Adapter identity UI Python LOC | Lokalny renderer LOC (bez setup/context) | Wniosek |
|---|---:|---:|---|
| Anonimizator3000 | 446 | 0 | Adapter spadł z ~726 do 446 LOC przez `StandardUserManagerUiHooks`; zostały zaproszenia, sesja i CSRF. |
| PunkRecords | 0 | 0 | Brak lokalnego passkey/usermanager; chrome ogranicza się do konfiguracji platformy (90 LOC). |
| PlnFlr | 0 | 0 | Najmniejszy poprawny host chrome-only; konfiguracja platformy 109 LOC. |
| Lokay | 0 | 0 | Konsument shell/assets bez identity; brak istotnego wspólnego boilerplate’u. |
| rnkstr | 466 | 0 | Standard hooks i bezpośredni shared renderer (`00b7414`); session/menu context zostaje. |
| wolnyrolnik | 292 | 0 | Standard hooks i bezpośredni shared renderer (`3322dbd`); token CSRF i session/menu context zostają. |
| emitype | 756 | 0 | Shared renderer (`283e67da`); `svg.l*` / `report.access`, invitations, sidebar products i error actions zostają. |
| Argus | 754 | 0 | Dziedziczy `StandardUserManagerUiHooks` (PR #5680); sesja operatora, `admin.access`, firm grants i audit zostają. |
| Hermes | 365 | 0 | Passkey dla pojedynczego operatora; większość to hostowa polityka/session/storage. |
| Rudy | 370 | 0 | Cutover `um_*`/`passkey_*` + standard hooks; synchronizer-token CSRF i workflow grants zostają. |

## Co naprawdę się powtarza

Sześć hostów multi-user już dziedziczy `StandardUserManagerUiHooks`:

```text
emitype           756 LOC
Argus             754 LOC
rnkstr            466 LOC
Anonimizator3000  446 LOC
Rudy              370 LOC
wolnyrolnik       292 LOC
```

W Argusie zostały sesja operatora, `admin.access`, katalog ról/firm grants, operator audit i zaproszenia, ale również lokalne listowanie i mapowanie users. Standard hooks nie usunęły całej mechaniki adaptera.

Usunięto trzy `smart_template_response`. Routes rnkstr, Wolnego Rolnika i Emitype używają bezpośrednio `app_factory.template_response`. Setup Jinja i jawny hostowy `page_context` pozostają w `app/utils/templates.py` (odpowiednio 147, 218 i 84 LOC). Dawne 179/256/239 LOC mierzyły całe pliki, nie sam renderer — nie są porównywalne z zerem w obecnej kolumnie. Jawne call sites zwiększyły całkowity LOC; korzyścią jest brak legacy fallbacków i ukrytej mechaniki renderera. Wyniki testów i ograniczenia: [UI_DEDUP_AUDIT.md](UI_DEDUP_AUDIT.md).

## Zakończony cutover Rudy

Rudy (`msds-portal` commit `44f379c`) nie ma już runtime dual-read ani hostowej tabeli tożsamości `users`. Świeża baza tworzy domenowe klucze obce bezpośrednio do `um_users(user_id)`. Start istniejącej bazy wykonuje jednorazowo, fail-closed:

1. utworzenie kanonicznych schematów `my-auth` i `my-usermanager`;
2. skopiowanie historycznych users, credentials i workflow grants;
3. przebudowę FK `projects.owner_user_id` i `operator_reviews.reviewed_by`;
4. usunięcie tabel legacy oraz historycznych `*_retired`.

Relacje `projects -> runs -> operator_reviews` są zachowywane i sprawdzane przez `PRAGMA foreign_key_check`. Runtime tworzy i odczytuje użytkowników wyłącznie przez `my-usermanager`; passkeys i challenges należą wyłącznie do `my-auth`. Host zachował session/admin policy, synchronizer-token CSRF, invitation delivery, katalog workflow i politykę domenową. Adapter UI (`7fd0a47`) dziedziczy `StandardUserManagerUiHooks`. Pełny suite po cutoverze: `141 passed`; lock wskazuje dokładnie BOM `0.6.22 / 0.5.4 / 0.6.5`.

## Czego nie centralizować

- synchronizer-token CSRF Rudy i Wolnego Rolnika; shared Origin CSRF jest tylko dodatkową warstwą;
- role, grants, invitation delivery, first-user/operator enrollment i auditing;
- location picker, raporty Emitype, Argus live client i domenowe upload validation;
- klasy Basecoat oraz layout primitives — są już wspólnym kontraktem, nie duplikacją komponentów.

## Kolejność redukcji

1. ~~Dodać w `my-usermanager` standardowe hooks~~ — zrobione w `v0.6.5`.
2. ~~Przepnąć Argusa na `StandardUserManagerUiHooks`~~ — PR #5680, merge na `main`.
3. ~~Migrować renderery rnkstr, Wolnego Rolnika i Emitype~~ — wykonane na `main`.
4. ~~Usunąć martwe wrappery pagination/loading/form Emitype~~ — `749bb319`, kontrakty i testy przeszły; produktowe stany ładowania pozostają lokalne.
5. Używać PlnFlr jako startera chrome-only, a `examples/multi_user_bom` jako startera identity. Nie tworzyć generatora ani nowego frameworka.
