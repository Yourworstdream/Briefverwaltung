-- ============================================================================
--  Beispiel-Abfragen für die Briefverwaltung
--  Im Programm unter Reiter „SQL“ → „Beispiel“ auswählbar. Jede Abfrage beginnt
--  mit einer Zeile „-- ## Name“.
-- ============================================================================

-- ## Offene Briefe nach Dringlichkeit
SELECT id, betreff, absender, anlass, frist, dringlichkeit, status
FROM v_briefe
WHERE status <> 'erledigt'
ORDER BY dringlichkeit DESC, frist;

-- ## Briefe je Absender
SELECT a.name, COUNT(b.id) AS briefe, SUM(b.status <> 'erledigt') AS offen
FROM absender a
LEFT JOIN brief b ON b.absender_id = a.id
GROUP BY a.id, a.name
ORDER BY briefe DESC;

-- ## Briefe je Anlass mit Summe
SELECT an.name AS anlass, COUNT(b.id) AS briefe, SUM(b.betrag) AS summe
FROM anlass an
JOIN brief b ON b.anlass_id = an.id
GROUP BY an.id, an.name
ORDER BY summe DESC;

-- ## Überschrittene Fristen
SELECT frist, DATEDIFF(CURDATE(), frist) AS tage_drueber, betreff, absender
FROM v_briefe
WHERE status <> 'erledigt' AND frist < CURDATE()
ORDER BY frist;

-- ## Noch offene Beträge
SELECT betreff, absender, betrag, bezahlt, betrag - bezahlt AS offen, frist
FROM v_briefe
WHERE status <> 'erledigt' AND betrag > bezahlt
ORDER BY frist;

-- ## Zahlungen je Monat
SELECT DATE_FORMAT(zeitpunkt, '%Y-%m') AS monat, richtung, COUNT(*) AS anzahl, SUM(betrag) AS summe
FROM aktivitaet
WHERE art = 'Zahlung'
GROUP BY monat, richtung
ORDER BY monat DESC;

-- ## Alle Telefonate
SELECT zeitpunkt, absender, ansprechpartner, telefonnummer, dauer_min, betreff, notizen
FROM v_aktivitaeten
WHERE art = 'Telefonat'
ORDER BY zeitpunkt DESC;

-- ## Kontaktdaten aller Ansprechpartner
SELECT a.name AS absender, ap.anrede, ap.vorname, ap.nachname, ap.telefon, ap.mobil, ap.email
FROM ansprechpartner ap
JOIN absender a ON a.id = ap.absender_id
ORDER BY a.name, ap.nachname;

-- ## Bankverbindungen
SELECT a.name AS absender, bv.kontoinhaber, bv.iban, bv.bic, bv.bank
FROM bankverbindung bv
JOIN absender a ON a.id = bv.absender_id
ORDER BY a.name;

-- ## Fotos und Speicherplatz
SELECT COUNT(*) AS fotos, ROUND(SUM(groesse) / 1024 / 1024, 1) AS megabyte,
       MIN(importiert_am) AS erster_import, MAX(importiert_am) AS letzter_import
FROM foto;

-- ## Import-Protokoll
SELECT * FROM import_protokoll ORDER BY zeitpunkt DESC LIMIT 20;
