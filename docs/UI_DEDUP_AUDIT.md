# Audyt deduplikacji UI hostów

Stan po wspólnym BOM-ie `app-factory v0.6.22`, `my-auth v0.5.4`,
`my-usermanager v0.6.5` i migracji standardowych UserManager hooks.

## Zakres

Przejrzano rzeczywiste hosty: Anonimizator3000, PunkRecords, PlnFlr, rnkstr,
Wolny Rolnik, Emitype, Lokay, Argus, Hermes i Rudy/MSDS Portal. Pominięto
worktree, vendored dependencies i `.venv`.

## Wynik ilościowy

| Host | HTML | CSS hosta | JS hosta | Inline `style` | `<style>` | Ocena |
|---|---:|---:|---:|---:|---:|---|
| Anonimizator3000 | 4 | 351 LOC | 0 | 0 | 0 | CSS częściowo duplikuje Basecoat. |
| PunkRecords | 7 | 0 | inline chart boot | 1 | 1 | UI czyste; chart boot jest domenowy. |
| PlnFlr | 5 | 76 LOC | 0 | 0 | 0 | CSS jest domenowym rendererem planu. |
| rnkstr | 20 | Leaflet vendor | 26 plików | 2 | 1 | CSS prawie wyłącznie vendor; następny cel to renderer i duże skrypty domenowe. |
| Wolny Rolnik | 11 | 0 | inline | 1 | 0 | Brak zbędnego hostowego CSS. |
| Emitype | 49 | 569 LOC | inline | 14 | 4 | CSS produktowy; pozostało dużo inline CSS i lokalny renderer. |
| Lokay | 1 | 0 | 0 | 0 | 0 | Wzorcowy bez-CSS host Basecoat. |
| Argus | 23 | 147 LOC | 5 plików | 0 | 1 | `landing.css` i client UI są produktowe; brak kopii komponentów. |
| Rudy | 20 | 0 | 0 | 39 | 1 | Brak arkusza CSS, ale dużo inline stylowania statusów i tabel. |

## Co usunięto od razu

Emitype commit `749bb319` usunął 141 linii martwych lub delegujących wrapperów:

- `components/pagination.html` — delegował 1:1 do
  `app_factory/components/pagination.html`; importy wskazują teraz bezpośrednio
  shared macro;
- `components/loading-indicator.html` — nie miał konsumentów;
- `components/form-components.html` — definiował nieużywane makra i był jedynym
  konsumentem martwego spinnera.

Weryfikacja: `1054 passed, 2 skipped`; pięć testów Playwright pozostaje poza
lokalnym środowiskiem.

## Kandydaci do usunięcia lub zastąpienia Basecoat

### 1. Anonimizator3000 — najwyższy zwrot CSS

`src/anonimizator3000/static/app.css` nadal ustawia własne globalne tokeny,
`body`, `.btn`, `.badge`, `.alert` i powierzchnie kart. Basecoat już posiada te
komponenty i theme tokens. Do pozostawienia są wyłącznie layout i produktowe
stany: dwukolumnowy upload/result, disclosure, progress/job metadata oraz
responsywność. Nie należy przenosić tych reguł do `app-factory`; należy usunąć
hostowe redefinicje Basecoat i użyć jego markup/data variants.

### 2. Rudy — zamiana inline status CSS na Basecoat variants

Największe skupiska są w `run_detail.html`, `track.html` i
`project_runs_table_partial.html`: ręczne czerwone/zielone/żółte gradienty,
obramowania i kolory tekstu. Powinny używać `.alert` / `.badge` z
`data-variant="destructive|success|warning|secondary"` tam, gdzie Basecoat ma
wariant. Dynamiczne szerokości progress barów i kolumn tabel pozostają inline —
to dane, nie komponent CSS.

### 3. Emitype — przenieść `<style>` z fragmentów, nie centralizować domeny

`article_content.html`, `video_content.html`, `emitype_form_unified.html` i
`svg_result_content.html` zawierają lokalne `<style>`. Reguły powtarzające card,
input, button, alert lub zwykły spacing należy zastąpić Basecoat/classes.
Specyficzne style SVG/raportu i `emi-choice-card` są domenowe i mogą zostać w
`emi-raport.css` albo małym product CSS. Lokalny `card.html` jest realnie używany
w 11 miejscach i tylko normalizuje semantyczny markup Basecoat — obecnie nie ma
wartości w przenoszeniu go do `app-factory`.

### 4. Renderery page/fragment

Pozostają trzy lokalne `smart_template_response`:

- rnkstr: 179 LOC;
- Wolny Rolnik: 256 LOC;
- Emitype: 239 LOC.

To większy wspólny koszt niż CSS w dwóch hostach bez arkuszy. Migrować kolejno
na `app_factory.template_response`, zachowując hostowe session/domain context.

## Co jest prawidłowo lokalne

- PlnFlr `app.css`: SVG rooms, gaps, zones, labels i clipping;
- rnkstr Leaflet CSS oraz map/ranking interactions;
- Emitype SVG/report visualization i produktowy choice card;
- Argus landing/client workflow presentation;
- PunkRecords Chart.js konfiguracja;
- dynamiczne progress widths, wykresy i kolory pochodzące z danych.

## Czego nie dodawać do app-factory

- wrapperów `card`, `button`, `badge`, `input`, `alert` — Basecoat już je ma;
- generycznego spinner macro bez realnych konsumentów;
- domenowych wariantów report/ranking/map/plan;
- globalnego Alpine store ani wspólnego chart boot.

## Zalecana kolejność następnych zmian

1. Anonimizator3000: usunąć redefinicje `.btn/.badge/.alert/card` i globalne
   theme/body CSS, zostawić product layout; testy + wizualny smoke.
2. Rudy: zastąpić statyczne inline status colors wariantami Basecoat; zostawić
   dynamiczne `width`.
3. rnkstr: usunąć lokalny renderer page/fragment.
4. Wolny Rolnik: usunąć lokalny renderer; brak CSS do centralizacji.
5. Emitype: usunąć renderer, potem rozdzielić cztery `<style>` na Basecoat vs
   domenowy CSS.
6. Dopiero po tych zmianach rozważyć nowy release `app-factory`; obecny audyt
   nie znalazł nowego wspólnego komponentu wymagającego dodania do biblioteki.
