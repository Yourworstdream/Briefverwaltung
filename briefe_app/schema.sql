-- ============================================================================
--  Briefverwaltung – Datenbankschema
--  Läuft mit MySQL 8.0+ und MariaDB 10.5+ (z. B. aus XAMPP).
--  Das Programm führt diese Datei beim Start selbst aus; alle Befehle sind so
--  geschrieben, dass sie mehrfach laufen dürfen (IF NOT EXISTS / OR REPLACE).
-- ============================================================================

-- Absender: Behörden, Firmen, Banken, Versicherungen, Privatpersonen …
CREATE TABLE IF NOT EXISTS absender (
    id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(200) NOT NULL,
    art           VARCHAR(50)  NULL,
    strasse       VARCHAR(200) NULL,
    plz           VARCHAR(10)  NULL,
    ort           VARCHAR(100) NULL,
    telefon       VARCHAR(50)  NULL,
    email         VARCHAR(200) NULL,
    webseite      VARCHAR(200) NULL,
    kundennummer  VARCHAR(100) NULL,
    notizen       TEXT         NULL,
    erstellt_am   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_absender_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Ansprechpartner gehören immer zu einem Absender
CREATE TABLE IF NOT EXISTS ansprechpartner (
    id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    absender_id    INT UNSIGNED NOT NULL,
    anrede         VARCHAR(20)  NULL,
    titel          VARCHAR(50)  NULL,
    vorname        VARCHAR(100) NULL,
    nachname       VARCHAR(100) NOT NULL DEFAULT '',
    funktion       VARCHAR(100) NULL,
    telefon        VARCHAR(50)  NULL,
    mobil          VARCHAR(50)  NULL,
    email          VARCHAR(200) NULL,
    erreichbarkeit VARCHAR(200) NULL,
    notizen        TEXT         NULL,
    CONSTRAINT fk_ansprechpartner_absender FOREIGN KEY (absender_id)
        REFERENCES absender (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Bankverbindungen eines Absenders (wohin bezahlt wird)
CREATE TABLE IF NOT EXISTS bankverbindung (
    id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    absender_id   INT UNSIGNED NOT NULL,
    kontoinhaber  VARCHAR(200) NULL,
    iban          VARCHAR(34)  NOT NULL,
    bic           VARCHAR(11)  NULL,
    bank          VARCHAR(200) NULL,
    bemerkung     VARCHAR(200) NULL,
    UNIQUE KEY uq_bank_iban (absender_id, iban),
    CONSTRAINT fk_bank_absender FOREIGN KEY (absender_id)
        REFERENCES absender (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Anlass: fasst Briefe zu einem Thema zusammen (z. B. „Nebenkosten 2026“, „Kfz-Unfall“)
CREATE TABLE IF NOT EXISTS anlass (
    id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(200) NOT NULL,
    beschreibung  TEXT         NULL,
    status        ENUM('offen', 'erledigt') NOT NULL DEFAULT 'offen',
    erstellt_am   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_anlass_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Der Brief selbst; die Fotos der Seiten stehen in der Tabelle foto
CREATE TABLE IF NOT EXISTS brief (
    id                 INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    betreff            VARCHAR(300) NOT NULL DEFAULT '',
    absender_id        INT UNSIGNED NULL,
    ansprechpartner_id INT UNSIGNED NULL,
    bankverbindung_id  INT UNSIGNED NULL,
    anlass_id          INT UNSIGNED NULL,
    briefdatum         DATE         NULL,
    eingangsdatum      DATE         NULL,
    frist              DATE         NULL,
    dringlichkeit      TINYINT UNSIGNED NOT NULL DEFAULT 2,
    status             ENUM('neu', 'in_bearbeitung', 'wartet', 'erledigt') NOT NULL DEFAULT 'neu',
    betrag             DECIMAL(12, 2) NULL,
    aktenzeichen       VARCHAR(100) NULL,
    notizen            TEXT         NULL,
    erstellt_am        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    geaendert_am       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT chk_brief_dringlichkeit CHECK (dringlichkeit BETWEEN 1 AND 4),
    KEY ix_brief_status (status),
    KEY ix_brief_frist (frist),
    CONSTRAINT fk_brief_absender FOREIGN KEY (absender_id)
        REFERENCES absender (id) ON DELETE SET NULL,
    CONSTRAINT fk_brief_ansprechpartner FOREIGN KEY (ansprechpartner_id)
        REFERENCES ansprechpartner (id) ON DELETE SET NULL,
    CONSTRAINT fk_brief_bank FOREIGN KEY (bankverbindung_id)
        REFERENCES bankverbindung (id) ON DELETE SET NULL,
    CONSTRAINT fk_brief_anlass FOREIGN KEY (anlass_id)
        REFERENCES anlass (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Ein Foto = eine Seite eines Briefes. sha256 verhindert, dass ein Foto doppelt importiert wird.
CREATE TABLE IF NOT EXISTS foto (
    id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    brief_id       INT UNSIGNED NOT NULL,
    seite          SMALLINT UNSIGNED NOT NULL DEFAULT 1,
    dateiname      VARCHAR(255) NOT NULL,
    mime           VARCHAR(100) NULL,
    groesse        INT UNSIGNED NOT NULL DEFAULT 0,
    sha256         CHAR(64)     NOT NULL,
    breite         INT UNSIGNED NULL,
    hoehe          INT UNSIGNED NULL,
    drehung        SMALLINT     NOT NULL DEFAULT 0,
    aufgenommen_am DATETIME     NULL,
    importiert_am  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    quelle         VARCHAR(500) NULL,
    vorschau       MEDIUMBLOB   NULL,
    UNIQUE KEY uq_foto_sha256 (sha256),
    KEY ix_foto_brief (brief_id, seite),
    CONSTRAINT fk_foto_brief FOREIGN KEY (brief_id)
        REFERENCES brief (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Der Bildinhalt in Stücken. So klappt der Import auch, wenn der Server nur kleine
-- Pakete erlaubt (XAMPP: max_allowed_packet = 1M).
CREATE TABLE IF NOT EXISTS foto_teil (
    foto_id  INT UNSIGNED      NOT NULL,
    nr       SMALLINT UNSIGNED NOT NULL,
    daten    MEDIUMBLOB        NOT NULL,
    PRIMARY KEY (foto_id, nr),
    CONSTRAINT fk_foto_teil_foto FOREIGN KEY (foto_id)
        REFERENCES foto (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Telefonate, Treffen, Zahlungen, E-Mails, Notizen … – jeweils zu Brief, Absender und/oder Anlass
CREATE TABLE IF NOT EXISTS aktivitaet (
    id                 INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    art                VARCHAR(30)  NOT NULL,
    zeitpunkt          DATETIME     NOT NULL,
    betreff            VARCHAR(300) NOT NULL DEFAULT '',
    notizen            TEXT         NULL,
    brief_id           INT UNSIGNED NULL,
    absender_id        INT UNSIGNED NULL,
    ansprechpartner_id INT UNSIGNED NULL,
    anlass_id          INT UNSIGNED NULL,
    richtung           ENUM('eingehend', 'ausgehend') NULL,
    dauer_min          SMALLINT UNSIGNED NULL,
    ort                VARCHAR(200) NULL,
    telefonnummer      VARCHAR(50)  NULL,
    betrag             DECIMAL(12, 2) NULL,
    zahlungsart        VARCHAR(50)  NULL,
    bankverbindung_id  INT UNSIGNED NULL,
    wiedervorlage      DATE         NULL,
    erstellt_am        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY ix_aktivitaet_zeit (zeitpunkt),
    KEY ix_aktivitaet_art (art),
    CONSTRAINT fk_akt_brief FOREIGN KEY (brief_id)
        REFERENCES brief (id) ON DELETE SET NULL,
    CONSTRAINT fk_akt_absender FOREIGN KEY (absender_id)
        REFERENCES absender (id) ON DELETE SET NULL,
    CONSTRAINT fk_akt_ansprechpartner FOREIGN KEY (ansprechpartner_id)
        REFERENCES ansprechpartner (id) ON DELETE SET NULL,
    CONSTRAINT fk_akt_anlass FOREIGN KEY (anlass_id)
        REFERENCES anlass (id) ON DELETE SET NULL,
    CONSTRAINT fk_akt_bank FOREIGN KEY (bankverbindung_id)
        REFERENCES bankverbindung (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Jeder Import (USB-Stick oder Ordner) wird protokolliert
CREATE TABLE IF NOT EXISTS import_protokoll (
    id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    zeitpunkt  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    quelle     VARCHAR(500) NOT NULL,
    neue_briefe INT UNSIGNED NOT NULL DEFAULT 0,
    neue_fotos INT UNSIGNED NOT NULL DEFAULT 0,
    doppelt    INT UNSIGNED NOT NULL DEFAULT 0,
    fehler     INT UNSIGNED NOT NULL DEFAULT 0,
    meldung    TEXT         NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS schema_version (
    version  INT UNSIGNED NOT NULL PRIMARY KEY
) ENGINE=InnoDB;

INSERT IGNORE INTO schema_version (version) VALUES (1);

-- ---------------------------------------------------------------------------
--  Sichten (Views) – praktisch für eigene Abfragen im SQL-Fenster
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW v_briefe AS
SELECT b.id, b.betreff,
       b.absender_id, a.name AS absender,
       b.anlass_id, an.name AS anlass,
       b.ansprechpartner_id, b.bankverbindung_id,
       b.briefdatum, b.eingangsdatum, b.frist,
       b.dringlichkeit, b.status, b.betrag, b.aktenzeichen, b.notizen,
       (SELECT COUNT(*) FROM foto f WHERE f.brief_id = b.id) AS fotos,
       (SELECT COALESCE(SUM(z.betrag), 0) FROM aktivitaet z
         WHERE z.brief_id = b.id AND z.art = 'Zahlung') AS bezahlt,
       b.erstellt_am, b.geaendert_am
FROM brief b
LEFT JOIN absender a ON a.id = b.absender_id
LEFT JOIN anlass an ON an.id = b.anlass_id;

CREATE OR REPLACE VIEW v_aktivitaeten AS
SELECT t.id, t.art, t.zeitpunkt, t.betreff, t.notizen, t.richtung, t.dauer_min, t.ort,
       t.telefonnummer, t.betrag, t.zahlungsart, t.wiedervorlage,
       t.brief_id, b.betreff AS brief,
       t.absender_id, a.name AS absender,
       t.ansprechpartner_id,
       TRIM(CONCAT_WS(' ', ap.anrede, ap.titel, ap.vorname, ap.nachname)) AS ansprechpartner,
       t.anlass_id, an.name AS anlass,
       t.bankverbindung_id, bv.iban
FROM aktivitaet t
LEFT JOIN brief b ON b.id = t.brief_id
LEFT JOIN absender a ON a.id = t.absender_id
LEFT JOIN ansprechpartner ap ON ap.id = t.ansprechpartner_id
LEFT JOIN anlass an ON an.id = t.anlass_id
LEFT JOIN bankverbindung bv ON bv.id = t.bankverbindung_id;
