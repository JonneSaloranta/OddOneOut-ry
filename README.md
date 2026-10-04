# OddOneOut ry – Laatukäsikirja

OddOneOut ry on mikkeliläinen ajoneuvoharrastajien yhdistys ([oddoneoutcrew.org](https://oddoneoutcrew.org/)).
Tämä repositorio sisältää yhdistyksen laadunhallintajärjestelmän dokumentaation, joka on jäsennelty ISO 9001:2015 -standardin mukaisesti.

## Dokumentit

| Tunnus | Dokumentti | ODT | Tila |
|---|---|---|---|
| – | [Dokumenttipohja](laatukasikirja/00_dokumenttipohja.md) | [.odt](laatukasikirja/00_dokumenttipohja.odt) | Pohja |
| MEN-01 | [Kokouksen pitäminen](laatukasikirja/MEN-01_kokouksen_pitaminen.md) | [.odt](laatukasikirja/MEN-01_kokouksen_pitaminen.odt) | Luonnos |

Dokumenttien lähde on Markdown (`.md`). Muotoillut OpenDocument-tiedostot (`.odt`, avautuvat LibreOfficessa ja Wordissa) generoidaan lähteestä.

## Uuden dokumentin tekeminen

1. Kopioi `laatukasikirja/00_dokumenttipohja.md` ja nimeä se muotoon `TUNNUS_nimi.md`.
2. Täytä hakasulkeissa olevat kohdat ja poista kursiiviset ohjetekstit.
3. Lisää dokumentti yllä olevaan taulukkoon.
4. Generoi ODT-versio: `python3 tyokalut/muunna_odt.py` (vaatii pandocin, esim. `pip install pypandoc_binary`).
5. Hallitus hyväksyy dokumentin; kirjaa hyväksyntä dokumentin muutoshistoriaan.

Muokkaa aina `.md`-tiedostoa ja generoi `.odt` uudelleen, jotta versiot pysyvät samoina. Erillinen vaakaviiva (`---`) tekee ODT-versioon sivunvaihdon.

Tunnusten etuliitteet: `POL` politiikka, `MEN` menettelyohje, `TYO` työohje, `LOM` lomake.
