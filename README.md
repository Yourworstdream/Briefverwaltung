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

## Benutzen

`index.html` im Browser öffnen, auch auf dem Handy. Es braucht keinen Server.
Die Bücher werden dann auf diesem Gerät gespeichert. Beim ersten Öffnen
stehen schon die Bände vom Regalfoto drin.

Die veröffentlichte Version auf claude.ai speichert das Regal online, damit es
auf allen Geräten gleich ist.

## Handy-App (Android)

Im Ordner `android/` liegt eine kleine Android-App, die genau diese `index.html`
anzeigt. GitHub baut sie bei jeder Änderung automatisch und legt die APK unter
**Releases → Handy-App (neueste Version)** zum Herunterladen bereit.

1. Die Datei `Was-lese-ich-heute.apk` auf dem Handy herunterladen.
2. Öffnen und die Installation aus unbekannten Quellen erlauben.

Neue Versionen lassen sich über die alte installieren, die eingetragenen Bücher
bleiben dabei erhalten. Nur wer die App deinstalliert, verliert das Verzeichnis.
