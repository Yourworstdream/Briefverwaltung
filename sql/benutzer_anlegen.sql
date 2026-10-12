-- ============================================================================
--  Eigenen MySQL-Benutzer für die Briefverwaltung anlegen (einmalig).
--
--  Linux:    sudo mysql < sql/benutzer_anlegen.sql
--  Windows:  in der MySQL-Shell / MySQL Workbench / phpMyAdmin (XAMPP) ausführen
--
--  Vorher unten das Passwort ändern! Im Programm dann unter
--  Datei → Einstellungen den Benutzer „briefe“ und dieses Passwort eintragen.
-- ============================================================================

CREATE DATABASE IF NOT EXISTS briefverwaltung
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'briefe'@'localhost' IDENTIFIED BY 'HIER-EIN-EIGENES-PASSWORT';

GRANT ALL PRIVILEGES ON briefverwaltung.* TO 'briefe'@'localhost';
FLUSH PRIVILEGES;
