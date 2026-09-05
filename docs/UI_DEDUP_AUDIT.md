# Audyt deduplikacji UI hostów — wykonane zmiany

BOM pozostaje bez zmian: `app-factory v0.6.22`, `my-auth v0.5.4`,
`my-usermanager v0.6.5`. Nie dodano nowego komponentu ani release platformy.

## Zakres i rezultat

Przejrzano 10 rzeczywistych hostów: Anonimizator3000, PunkRecords, PlnFlr,
rnkstr, Wolny Rolnik, Emitype, Lokay, Argus, Hermes i Rudy/MSDS Portal.
Worktree i kopie nie są osobnymi produktami.

Wszystkie sześć zaakceptowanych zmian jest na `main` hostów:

| Host | Commity | Zmiana |
|---|---|---|
| Anonimizator3000 | `e6d1f50`, `42de1ed` | Usunięte prywatne theme/body i komponentowe overrides; layout ma nazwę `document-layout`, SVG nie zmienia ikon shella. |
| Rudy | `83defcc`, `d17344e` | Statyczne gradienty/status colors i stare badge/button aliases zastąpione rzeczywistymi wariantami; poprawione zagnieżdżenie alertów. |
| rnkstr | `00b7414` | Usunięty `smart_template_response`; jawne wywołania biblioteki w routes, hostowy `page_context` bez renderowania. |
| Wolny Rolnik | `3322dbd` | Jak wyżej; usunięte nieużywane renderer redirects login/register i fallback pokazujący wyjątek. |
| Emitype | `283e67da` | Usunięty renderer z legacy fallbackami; jawne page/fragment responses i hostowy kontekst błędów; cztery `<style>` usunięte z fragmentów. |

Wcześniej Emitype `749bb319` usunął wrappery pagination/loading/form.
Pagination importuje shared macro bezpośrednio. `components/card.html` zostaje:
ma realnych konsumentów i normalizuje semantyczny markup Basecoat.

## Porównywalne pomiary zmienionych hostów

Liczby HTML to pliki, CSS to fizyczne linie w hostowych arkuszach;
`style=` i `<style>` to wystąpienia w szablonach, nie liczba reguł CSS.

| Host | HTML teraz | CSS przed → po | Inline `style` przed → po | `<style>` przed → po |
|---|---:|---:|---:|---:|
| Anonimizator3000 | 4 | 351 → 272 LOC | 0 → 0 | 0 → 0 |
| Rudy | 20 | 0 → 0 LOC | 39 → 21 | 1 → 1 |
| Emitype | 46 | 569 → 753 LOC | 14 → 14 | 4 → 0 |

Wzrost CSS Emitype wynika z przeniesienia stylów z HTML, nie z nowego systemu
komponentów. Bundle nie ma `.prose`: Markdown artykułów i opisu wideo używa
jednego scoped `.emitype-markdown` w `static/css/product-content.css`, z tokenami
Basecoat zamiast niepoprawnego `hsl(var(--...))`. Ten sam arkusz zachowuje
produktowe SVG/fullscreen. Formularz korzysta z natywnego `hidden` zamiast
prywatnej klasy `is-collapsed`; disabled/inert/ARIA i prefill zostają.

## Renderowanie i granice odpowiedzialności

Trzy hosty importują `app_factory.template_response` bezpośrednio. Routes
jawnie podają `base.html`, `content_template` i `fragment_template` (Emitype
błędy: `pages/error.html` + `partials/error.html`). Nie ma lokalnego renderera,
zgadywania legacy fallbacków ani ujawniania wyjątków Jinja w odpowiedzi.

Hostowy `page_context` nadal odpowiada za sesję, grants/menu i domenowe dane.
Nie mutuje wejściowego słownika ani `Environment.globals`. Emitype zachowuje
przekazane request-scoped produkty oraz status-keyed error actions.

To redukcja ukrytej mechaniki, **nie redukcja całkowitego LOC**: jawne argumenty
w call sites i nowe testy zwiększają liczbę linii. Nie przedstawiamy tego jako
oszczędności netto kodu.

## Weryfikacja

| Host | Wynik |
|---|---|
| Anonimizator3000 | `65 passed, 1 deselected` (`not real_anonymizer`). |
| Rudy | Pełny pytest zielony po poprawce HTML; 143 testy (141 wcześniejszych + 2 kontrakty). |
| rnkstr | `176 passed`. |
| Wolny Rolnik | `42 passed`. |
| Emitype | `1057 passed, 2 skipped, 5 deselected` bez `tests/test_ui`; osobno `26 passed` w `test_ui/test_templates.py`. |
| Emitype browser | `2 passed`: prawdziwy Chromium, desktop/light i mobile/dark, odpowiedzi aplikacji oraz lokalne assety przez TestClient; toggle drugiej osoby, hidden/inert/ARIA, brak poziomego overflow. |

`uv lock --check` i `git diff --check` przeszły dla pięciu hostów. Focused Ruff
przeszedł dla nowych testów i context helpers; zmienione pliki Python Emitype
przeszły dodatkowo I/F. Pełny Ruff Rudy oraz istniejące TRY203 w `main.py`
rnkstr/Wolnego Rolnika nie są zielonym gate'em — nie naprawiano niezwiązanych
problemów przy zmianach UI.

Nie wykonano pełnej wizualnej regresji wszystkich hostów ani deployu/restartu
produkcji. Browser smoke Emitype nie obejmuje całego istniejącego zestawu
Playwright zależnego od serwera `localhost:8000`. Anonimizator nie uruchamiał
lokalnych modeli GLiNER/Presidio.

## Co prawidłowo zostaje lokalne

- PlnFlr: SVG rooms/gaps/zones/labels/clipping; arkusz zawiera też małe reguły
  x-cloak/HTMX, więc nie jest dosłownie w całości domenowy.
- rnkstr: Leaflet i map/ranking interactions.
- Emitype: SVG/report/Markdown i produktowy choice card.
- Argus: landing/client workflow; nadal lokalne listowanie i mapowanie users.
- PunkRecords: Chart.js boot.
- Dynamiczne progress widths i dane wizualizacji; nie usuwano ich mechanicznie.
- Hermes: brak osobnych plików HTML/CSS/JS nie dowodzi braku inline HTML w Python.

Nie dodawać wrapper frameworka dla card/button/badge/input/alert. Bundle ma
`destructive`, `secondary`, `outline`, **nie** ma `success`/`warning`. Rudy
używa neutralnych wariantów, zachowując słowa i symbole oznaczające wynik.
