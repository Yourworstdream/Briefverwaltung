# Was lese ich heute?

Eine kleine Web-App für das Bücherregal: Sie führt ein Verzeichnis der Bücher
und zieht jeden Tag ein zufälliges Buch zum Lesen.

- **Heute dran:** Für jeden Tag ist ein Buch ausgewählt. „Anderes Buch ziehen“
  wählt ein neues, auf Wunsch nur aus einem Genre oder einer Epoche.
- **Im Regal:** Alle Bücher als Buchrücken, nach Epoche eingefärbt und
  chronologisch sortiert.
- **Verzeichnis:** Bücher mit **Name**, **Genre** und **Epoche** eintragen,
  bearbeiten, entfernen und durchsuchen. Wenn der Name als „Autor – Titel“
  geschrieben ist, steht der Nachname des Autors auf dem Buchrücken.

## Lesetagebuch

`tagebuch.html` ist die zweite App. Zu jedem Buch aus dem Regal trägst du dort ein:

- **Seiten:** auf welcher Seite du bist und wie viele Seiten das Buch hat. Daraus
  entstehen Fortschrittsbalken, Verlauf und Seiten pro Lesetag.
- **Gedanken:** als Stichpunkte, jeweils mit Datum.
- **Zusammenfassung:** ein freier Text, der beim Tippen gespeichert wird.
- **Fertig gelesen:** Das Buch bleibt im Verzeichnis und im Regal (blass), wird von
  „Was lese ich heute?“ aber nicht mehr vorgeschlagen.

Im Browser teilen sich beide Seiten den Speicher, auf dem Handy reden die zwei Apps miteinander. Die Bücher selbst
werden nur in „Was lese ich heute?“ eingetragen, das Tagebuch liest sie von dort.

## Benutzen

`index.html` im Browser öffnen, auch auf dem Handy. Es braucht keinen Server.
Die Bücher werden dann auf diesem Gerät gespeichert. Beim ersten Öffnen
stehen schon die Bände vom Regalfoto drin.

Die veröffentlichte Version auf claude.ai speichert das Regal online, damit es
auf allen Geräten gleich ist.

## Handy-Apps (Android)

Im Ordner `android/` liegen zwei eigenständige Android-Apps:

| App | Paket | Seite |
| --- | --- | --- |
| Was lese ich heute? | `de.waslese.heute` | `index.html` |
| Lesetagebuch | `de.waslese.tagebuch` | `tagebuch.html` |

Jede App speichert ihre eigenen Daten und gibt sie über einen ContentProvider frei.
Lesen darf ihn nur eine App mit derselben Unterschrift (Berechtigung
`de.waslese.DATEN`, Schutzstufe `signature`), also nur die Partner-App. Die Seite
erreicht das über `window.Bruecke`:

- „Was lese ich heute?“ teilt Bücher und Tagesbuch und liest vom Lesetagebuch, welche
  Bücher fertig sind und wie weit du bist.
- Das Lesetagebuch teilt seine Einträge und liest von „Was lese ich heute?“ die Bücher.
- Links springen in die andere App: `lesetagebuch://buch/<id>` und `wasleseichheute://regal`.

Beide Apps funktionieren auch allein. Ohne Partner fehlt nur der Austausch.

GitHub baut beide bei jeder Änderung und legt sie unter
**Releases → Handy-Apps (neueste Version)** als `Was-lese-ich-heute.apk` und
`Lesetagebuch.apk` bereit. Beide auf dem Handy installieren (Installation aus
unbekannten Quellen erlauben). Neue Versionen lassen sich über die alten
installieren, die Einträge bleiben erhalten.
