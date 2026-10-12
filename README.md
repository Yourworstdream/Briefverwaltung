# ✉ Briefverwaltung

Ein Desktop-Programm (Python), das deine Briefe in einer **MySQL-Datenbank** verwaltet. Du fotografierst Briefe mit dem Handy, kopierst die Fotos auf einen USB-Stick in den Ordner `Briefe`, steckst den Stick ein – und die Briefe sind **sofort und von selbst** im Programm.

![Übersicht](docs/uebersicht.png)

## Was es kann

- **Automatischer Import vom USB-Stick:** Sobald ein Stick mit dem Ordner `Briefe` steckt, werden alle neuen Fotos in die Datenbank übernommen. Schon importierte Fotos werden erkannt und übersprungen, auf dem Stick wird nichts verändert oder gelöscht.
- **Mehrseitige Briefe:** Ein Unterordner auf dem Stick (z. B. `Briefe/Stromrechnung/`) wird *ein* Brief mit mehreren Seiten. Seiten lassen sich später umsortieren, drehen, abtrennen oder mit „Zusammenfassen“ zu einem Brief vereinen.
- **Leicht eintippen:** Zu jedem Brief Absender, **Ansprechpartner mit Kontaktdaten**, **Bankverbindung** (IBAN wird geprüft), Anlass, **Dringlichkeit** (niedrig, normal, hoch, sehr dringend), Status, Frist, Betrag und Notizen. Neue Absender und Anlässe werden beim Eintippen automatisch angelegt. Datumsfelder verstehen auch `heute`, `morgen`, `+14` (in 14 Tagen) oder `+1m`.
- **Gruppieren nach Absender oder Anlass:** Die Briefliste ordnet nach Absender, Anlass, Dringlichkeit, Status oder Monat. Mehrere Briefe markieren und mit **„Gruppieren …“** auf einmal einem Absender oder Anlass zuordnen.
- **Telefonate, Treffen, Zahlungen & Co. dokumentieren:** E-Mails, verschickte Briefe und Notizen gehören auch dazu, jeweils zu einem Brief, Absender oder Anlass. Bei Telefonaten werden Nummer und Dauer gespeichert, bei Treffen der Ort, bei Zahlungen Betrag, Zahlungsart und Bankverbindung. Eine **Wiedervorlage** erinnert dich an den nächsten Schritt.
- **Übersicht:** Neue, offene und dringende Briefe, überschrittene Fristen, noch zu zahlende Beträge, Wiedervorlagen und offene Briefe je Absender auf einen Blick.
- **SQL-Fenster:** Eigene MySQL-Abfragen schreiben, mit Beispielen und dem Ergebnis als Tabelle. Ergebnisse lassen sich als CSV für Excel speichern.

![Briefe](docs/briefe.png)

## Installation

Du brauchst:

1. **Python 3.8 oder neuer** von [python.org](https://www.python.org/downloads/). Unter Windows bei der Installation „Add Python to PATH“ anhaken.
2. **MySQL 8** oder **MariaDB 10.5+**, die einfachste Möglichkeit unter Windows ist [XAMPP](https://www.apachefriends.org/de/) (MariaDB).
3. Die Python-Pakete:

   ```bash
   pip install -r requirements.txt
   ```

   Unter Linux fehlt manchmal tkinter: `sudo apt install python3-tk`.

### Datenbank vorbereiten

| System | So geht's |
|---|---|
| **Windows mit XAMPP** | XAMPP Control Panel öffnen, bei „MySQL“ auf **Start** klicken. Im Programm Benutzer `root`, Passwort leer. Fertig. |
| **Windows mit MySQL** | [MySQL Installer](https://dev.mysql.com/downloads/installer/) ausführen. Du kannst den Root-Benutzer verwenden oder mit [`sql/benutzer_anlegen.sql`](sql/benutzer_anlegen.sql) einen eigenen anlegen. |
| **Linux** | `sudo apt install mysql-server`, dann im Ordner des Programms `sudo mysql < sql/benutzer_anlegen.sql`. Vorher in der Datei das Passwort ändern. Unter Linux darf sich `root` nur per `sudo` anmelden, darum braucht es einen eigenen Benutzer. |

Die Datenbank `briefverwaltung` und alle Tabellen legt das Programm beim ersten Start selbst an.

## Starten

```bash
python briefverwaltung.py
```

Unter Windows geht auch ein Doppelklick auf **`Briefverwaltung starten.pyw`** (ohne schwarzes Konsolenfenster). Beim ersten Start fragt das Programm nach den Zugangsdaten zur Datenbank. Sie stehen danach in `~/.briefverwaltung/einstellungen.json` und lassen sich unter **Datei → Einstellungen** ändern.

## Briefe vom Handy auf den Stick

```
USB-Stick
└── Briefe/                          ← der Ordner muss direkt auf dem Stick liegen
    ├── IMG_20261008_101500.jpg      ← ein Foto = ein Brief
    ├── Mahnung_Telekom.jpg          ← Dateiname wird zum Betreff („Mahnung Telekom“)
    └── Stromrechnung 2025/          ← ein Unterordner = EIN Brief mit mehreren Seiten
        ├── Seite 1.jpg
        └── Seite 2.jpg
```

- Erlaubt sind JPG, PNG, HEIC (iPhone, mit `pip install pillow-heif`), WEBP, TIFF, BMP, GIF und PDF.
- Der Ordnername (`Briefe`) ist einstellbar, Groß- und Kleinschreibung sind egal.
- Kommt später eine weitere Seite in einen Unterordner, wird sie an den schon importierten Brief angehängt.
- Nach dem Import erscheint unten rechts eine Meldung. Danach kannst du den Stick abziehen. Die neuen Briefe findest du über **„Neue Briefe ansehen“** oder **Anzeigen → Neu**.

### Wie der Stick erkannt wird

Solange das Programm läuft, schaut es alle 2 Sekunden nach neuen Laufwerken, ganz ohne Zusatzprogramme:

- **Windows:** neue Laufwerksbuchstaben (USB-Sticks, SD-Karten, USB-Festplatten)
- **Linux:** eingehängte Wechseldatenträger und alles unter `/media`, `/run/media` und `/mnt`
- **macOS:** alles unter `/Volumes`

Klappt es einmal nicht: **Datei → USB-Stick jetzt prüfen**, oder **Fotos importieren …** und den Ordner von Hand wählen.

### Beim Hochfahren automatisch starten (optional)

- **Windows:** `Win + R` → `shell:startup` → dort eine Verknüpfung zu `Briefverwaltung starten.pyw` anlegen.
- **Linux:** Datei `~/.config/autostart/briefverwaltung.desktop` mit diesem Inhalt anlegen (Pfad anpassen):

  ```ini
  [Desktop Entry]
  Type=Application
  Name=Briefverwaltung
  Exec=python3 /pfad/zu/briefverwaltung/briefverwaltung.py
  ```

Wer nur den Import im Hintergrund möchte, ohne Fenster: `python briefverwaltung.py --waechter`.

## Bedienung

| Reiter | Was du dort machst |
|---|---|
| **Übersicht** | Kennzahlen anklicken öffnet die passenden Briefe. Dazu Fristen, Wiedervorlagen, offene Briefe je Absender und die letzten Importe. |
| **Briefe** | Links die gruppierte Liste, in der Mitte die Fotos (Doppelklick = groß mit Zoom), rechts das Formular. Mehrere Briefe mit Strg/Shift markieren → **Gruppieren …**, **Zusammenfassen**, **Erledigt**. Rechtsklick für Dringlichkeit und Status. |
| **Absender & Kontakte** | Adresse, Kundennummer, **Ansprechpartner** und **Bankverbindungen** pflegen. Dazu alle Briefe und Aktivitäten dieses Absenders. |
| **Anlässe** | Themen wie „Autounfall März 2026“ oder „Nebenkosten 2026“, auch mit Briefen von verschiedenen Absendern. |
| **Telefonate, Treffen, Zahlungen** | Alles Dokumentierte in einer Liste, filterbar nach Art, mit Summe der Zahlungen und Telefonminuten. |
| **SQL** | Eigene Abfragen. Tabellen und Spalten stehen links. Befehle, die etwas ändern (UPDATE, DELETE …), musst du vorher bestätigen. |

Tastenkürzel: `Strg+S` speichern · `Strg+N` neuer Brief · `Strg+F` suchen · `Strg+I` Ordner importieren · `F1` Kurzanleitung · im SQL-Fenster `Strg+Enter` ausführen.

Änderungen an einem Brief werden mit **Speichern** gesichert, und beim Wechsel zu einem anderen Brief speichert das Programm sie automatisch.

## Die Datenbank

Das komplette Schema steht in [`briefe_app/schema.sql`](briefe_app/schema.sql) (ausgeben mit `python briefverwaltung.py --schema`).

```mermaid
erDiagram
    absender ||--o{ ansprechpartner : "hat"
    absender ||--o{ bankverbindung : "hat"
    absender |o--o{ brief : "schickt"
    anlass |o--o{ brief : "fasst zusammen"
    ansprechpartner |o--o{ brief : "zuständig für"
    bankverbindung |o--o{ brief : "bezahlen an"
    brief ||--o{ foto : "Seiten"
    foto ||--|{ foto_teil : "Bildinhalt"
    brief |o--o{ aktivitaet : "Telefonat, Zahlung …"
    absender |o--o{ aktivitaet : "mit"
    ansprechpartner |o--o{ aktivitaet : "mit"
    anlass |o--o{ aktivitaet : "zu"
```

| Tabelle | Inhalt |
|---|---|
| `absender` | Behörden, Firmen, Banken, Versicherungen, Privatpersonen … (Name ist eindeutig) |
| `ansprechpartner` | Personen eines Absenders mit Telefon, Mobil, E-Mail, Erreichbarkeit |
| `bankverbindung` | IBAN, BIC, Bank und Kontoinhaber eines Absenders |
| `anlass` | Thema, das Briefe zusammenfasst |
| `brief` | Betreff, Daten, Frist, Dringlichkeit 1–4, Status, Betrag, Aktenzeichen, Notizen |
| `foto` | eine Seite eines Briefes: Dateiname, Größe, Aufnahmedatum, Drehung, kleines Vorschaubild. Ein SHA-256-Wert verhindert doppelte Importe |
| `foto_teil` | der Bildinhalt in Stücken, damit der Import auch mit kleinem `max_allowed_packet` klappt (XAMPP: 1 MB) |
| `aktivitaet` | Telefonate, Treffen, Zahlungen, E-Mails, Notizen, mit Richtung, Dauer, Ort, Betrag, Wiedervorlage |
| `import_protokoll` | wann was von welchem Stick importiert wurde |

Die Sichten **`v_briefe`** (Brief mit Absender, Anlass, Seitenzahl und bereits bezahltem Betrag) und **`v_aktivitaeten`** machen eigene Abfragen einfacher. Beispiele stehen in [`briefe_app/beispiel_abfragen.sql`](briefe_app/beispiel_abfragen.sql) und im SQL-Reiter, zum Beispiel:

```sql
SELECT betreff, absender, betrag, bezahlt, betrag - bezahlt AS offen, frist
FROM v_briefe
WHERE status <> 'erledigt' AND betrag > bezahlt
ORDER BY frist;
```

Fremdschlüssel sorgen für Ordnung. Löschst du einen Brief, verschwinden auch seine Fotos. Löschst du einen Absender, bleiben seine Briefe erhalten, haben dann aber keinen Absender mehr.

### Datensicherung

Alles, auch die Fotos, steckt in der Datenbank. Eine Sicherung ist deshalb eine einzige Datei:

```bash
mysqldump -u briefe -p briefverwaltung > sicherung.sql          # sichern
mysql -u briefe -p briefverwaltung < sicherung.sql              # zurückspielen
```

In XAMPP geht das auch über phpMyAdmin → *Exportieren*.

## Kommandozeile

```bash
python briefverwaltung.py                     # Programm mit Oberfläche
python briefverwaltung.py --import E:\Briefe  # einen Ordner importieren, ohne Oberfläche
python briefverwaltung.py --waechter          # nur USB-Überwachung, ohne Oberfläche
python briefverwaltung.py --schema            # SQL-Schema ausgeben
```

## Tests

```bash
python -m unittest discover -s tests -v
```

Für die Datenbank-Tests wird ein MySQL-Server gebraucht, angegeben über `BRIEFE_TEST_MYSQL=host:port:benutzer:passwort`. Ohne diese Angabe werden sie übersprungen. Jeder Lauf legt eine eigene Test-Datenbank an und löscht sie danach wieder. Auf GitHub laufen alle Tests bei jedem Push automatisch, mit MySQL 8 und mit MariaDB.

## Aufbau

```
briefverwaltung/
├── briefverwaltung.py          Startdatei (Oberfläche oder Kommandozeile)
├── Briefverwaltung starten.pyw Start per Doppelklick unter Windows
├── briefe_app/
│   ├── schema.sql              Tabellen und Sichten (MySQL)
│   ├── beispiel_abfragen.sql   Beispiele für das SQL-Fenster
│   ├── datenbank.py            alle SQL-Zugriffe (nur mit Parametern, sicher gegen SQL-Injection)
│   ├── importer.py             Fotos aus einem Ordner übernehmen
│   ├── usb.py                  USB-Sticks erkennen (Windows, Linux, macOS)
│   ├── bilder.py               Vorschaubilder, Aufnahmedatum, Drehung (Pillow)
│   ├── hilfen.py               Datum, Beträge, IBAN, Auswahllisten
│   ├── konfig.py               Einstellungen laden und speichern
│   └── gui/                    Oberfläche (tkinter)
│       ├── app.py              Hauptfenster, Menü, USB-Überwachung, Import im Hintergrund
│       ├── tab_*.py            die Reiter
│       ├── dialoge.py          Eingabefenster
│       ├── bildanzeige.py      Fotoanzeige mit Zoom
│       └── widgets.py, stil.py Bausteine und Aussehen
├── sql/benutzer_anlegen.sql    eigenen MySQL-Benutzer anlegen
└── tests/                      python -m unittest discover -s tests
```

## Datenschutz

Alles bleibt auf deinem Rechner bzw. in deiner eigenen Datenbank, das Programm schickt nichts ins Internet. Das Datenbank-Passwort steht, wenn du „Passwort merken“ anhakst, in `~/.briefverwaltung/einstellungen.json` (unter Linux und macOS nur für deinen Benutzer lesbar). **Lade keine echten Briefe oder Einstellungen in ein öffentliches Repository hoch.** Die Beispiele und Bildschirmfotos hier sind frei erfunden.
