# Talerstolen

De 12 danske partier forklaret ned i detaljen: mærkesager, holdninger emne for emne, aktuelle debatter, hvem der stemte hvad i Folketinget, og idéer til debatvideoer.

Siden ligger på https://thom899g.github.io/talerstolen/

Talerstolen er et privat projekt og er ikke tilknyttet noget parti.

## Sådan er den bygget

| Fil | Indhold |
|---|---|
| `index.html` | Hele siden: layout, stil og kode i én fil. |
| `data.js` | Partiprofilerne og det faste indhold. |
| `live/*.json` | Det, der skifter fra dag til dag: nyheder, debatter, målinger, videoidéer og Folketingets data. |
| `src/` | Kilderne siden er bygget af: research pr. parti og byggeskripterne. |

## Hvor kommer data fra?

- Afstemninger, forslag, spørgsmål, medlemmer og mandater hentes fra [Folketingets åbne data](https://www.ft.dk/da/dokumenter/aabne_data) med `src/tools/ft_update.py`.
- Partiprofiler og debatter bygger på de kilder, der står nederst på hver side.
- Skalaerne fra 1 til 5 er en forenklet redaktionel vurdering og erstatter ikke partiernes egne ord.

## Opdatering

Filerne i `live/` bliver skiftet ud én gang om dagen. Resten af siden ændres kun, når den bygges igen:

```bash
python3 src/tools/build_public.py alt .
```

Fejl eller mangler? Opret en issue her i repoet.
