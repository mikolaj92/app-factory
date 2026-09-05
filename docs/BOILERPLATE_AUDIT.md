# Audyt boilerplate’u po migracji BOM

Pomiar bazowy wykonano na checkoutach odpowiadających `origin/main`, po migracji do `app-factory v0.6.22`, `my-auth v0.5.4`, `my-usermanager v0.6.5`. Liczby są liniami fizycznymi w plikach integracyjnych, nie rozmiarem domeny aplikacji. Mają wskazywać kolejność redukcji, a nie premiować krótszy kod.

| Host | Identity/platform Python LOC | Lokalny renderer LOC | Wniosek |
|---|---:|---:|---|
| Anonimizator3000 | 1350 | 0 | Duży hostowy adapter identity; zaproszenia, profile i mapowanie domenowego użytkownika. |
| PunkRecords | 0 | 0 | Brak lokalnego passkey/usermanager; chrome ogranicza się do konfiguracji platformy (90 LOC). |
| PlnFlr | 0 | 0 | Najmniejszy poprawny host chrome-only; konfiguracja platformy 109 LOC. |
| Lokay | 0 | 0 | Konsument shell/assets bez identity; brak istotnego wspólnego boilerplate’u. |
| rnkstr | 1033 | 179 | Identity hooks są duże; 179 LOC lokalnego renderera page/fragment jest kandydatem do usunięcia. |
| wolnyrolnik | 941 | 256 | Identity hooks plus największa duplikacja konfiguracji Jinja/renderera; token CSRF 47 LOC jest hostową polityką. |
| emitype | 1450 | 239 | Największy adapter identity i renderer; lokalne wrappery pagination/loading wymagają osobnego cleanupu. |
| Argus | 1120 | 0 | Duży adapter, ale zawiera politykę firm, grants i auditing; nie przenosić domeny do app-factory. |
| Hermes | 365 | 0 | Passkey dla pojedynczego operatora; większość to hostowa polityka/session/storage. |
| Rudy | 1016 | 0 | Synchronizer-token CSRF pozostaje hostowy; runtime identity został całkowicie przepięty na `um_*`/`passkey_*`. |

## Co naprawdę się powtarza

W sześciu hostach multi-user powtarza się ten sam kształt callbacków `UserManagerUiHooks`: `get_current_user`, `require_admin`, `list_users`, role/capability options, enable/disable, grant/revoke, invitations, profile i mapowanie `User -> UserRow`. Sam interfejs jest już wspólny, ale hosty nadal piszą 387–797 LOC adaptera. To największy pozostały koszt.

Nie należy przenosić tych funkcji wprost do `app-factory`: operują na polityce, rolach, audycie i domenie. Następna redukcja należy do `my-usermanager` i powinna mieć formę opcjonalnego adaptera dla jego własnych standardowych stores/managera, z małymi callbackami hosta dla policy i efektów ubocznych.

Drugim powtarzalnym obszarem są lokalne `smart_template_response` (rnkstr 179 LOC, wolnyrolnik 256 LOC, emitype 239 LOC). Hosty powinny stopniowo przejść na małe `app_factory.template_response`; warianty lokalizacji, tytułu i domenowych fragmentów pozostają w hostach.

## Zakończony cutover Rudy

Rudy (`msds-portal` commit `44f379c`) nie ma już runtime dual-read ani hostowej tabeli tożsamości `users`. Świeża baza tworzy domenowe klucze obce bezpośrednio do `um_users(user_id)`. Start istniejącej bazy wykonuje jednorazowo, fail-closed:

1. utworzenie kanonicznych schematów `my-auth` i `my-usermanager`;
2. skopiowanie historycznych users, credentials i workflow grants;
3. przebudowę FK `projects.owner_user_id` i `operator_reviews.reviewed_by`;
4. usunięcie tabel legacy oraz historycznych `*_retired`.

Relacje `projects -> runs -> operator_reviews` są zachowywane i sprawdzane przez `PRAGMA foreign_key_check`. Runtime tworzy i odczytuje użytkowników wyłącznie przez `my-usermanager`; passkeys i challenges należą wyłącznie do `my-auth`. Host zachował tylko session/admin policy, synchronizer-token CSRF, invitation delivery i politykę domenową. Pełny suite po cutoverze: `141 passed`; lock wskazuje dokładnie BOM `0.6.22 / 0.5.4 / 0.6.5`.

## Czego nie centralizować

- synchronizer-token CSRF Rudy i Wolnego Rolnika; shared Origin CSRF jest tylko dodatkową warstwą;
- role, grants, invitation delivery, first-user/operator enrollment i auditing;
- location picker, raporty Emitype, Argus live client i domenowe upload validation;
- klasy Basecoat oraz layout primitives — są już wspólnym kontraktem, nie duplikacją komponentów.

## Kolejność redukcji

1. Dodać w `my-usermanager` standardowe hooks oparte o jego `UserManager`/stores; host podaje session lookup, `require_admin`, role catalog i opcjonalne side effects.
2. Migrować renderer: najpierw rnkstr, potem Wolny Rolnik, na końcu Emitype (najwięcej lokalnych wyjątków).
3. Usunąć lokalne wrappery pagination/loading dopiero po contract tests; nie centralizować produktowych stanów ładowania.
4. Używać PlnFlr jako startera chrome-only, a `examples/multi_user_bom` jako startera identity. Nie tworzyć generatora ani nowego frameworka.
