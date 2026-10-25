package de.briefverwaltung.analyse

import java.math.BigDecimal
import java.time.LocalDate
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Beispieltexte, wie sie die Texterkennung des Handys liefert (erfunden). */
class AnalyseTest {
    private val heute = LocalDate.of(2026, 10, 15)

    private val stadtwerke = """
        Stadtwerke Kaiserslautern Versorgungs-GmbH
        Bismarckstraße 14
        67655 Kaiserslautern
        Stadtwerke KL · Bismarckstr. 14 · 67655 Kaiserslautern
        Herrn
        Max Mustermann
        Beispielweg 5
        67657 Kaiserslautern
        Kundennummer: 4471120
        Rechnungsnummer: RE-2026-118422
        Ihr Ansprechpartner: Frau Sabine Krämer
        Telefon: 0631 8001-2214
        E-Mail: s.kraemer@swk-kl.de
        Kaiserslautern, 01.10.2026
        Jahresabrechnung Strom 2025
        Sehr geehrter Herr Mustermann,
        anbei erhalten Sie Ihre Jahresabrechnung für den Zeitraum 01.01.2025 bis 31.12.2025.
        Verbrauch: 2.668 kWh
        Nettobetrag 154,89 €
        zzgl. 19 % MwSt. 29,43 €
        Nachzahlung: 184,32 €
        Bitte überweisen Sie den Betrag bis zum 20.10.2026 auf unser Konto.
        Mit freundlichen Grüßen
        i. A. Sabine Krämer
        Stadtwerke Kaiserslautern Versorgungs-GmbH · Tel. 0631 8001-0 · www.swk-kl.de
        IBAN: DE89 3704 0044 0532 0130 00 BIC: COBADEFFXXX
    """.trimIndent()

    @Test
    fun rechnungDerStadtwerke() {
        val e = Analyse.analysieren(stadtwerke, heute)
        assertEquals("Rechnung", e.art)
        assertEquals("Jahresabrechnung Strom 2025", e.betreff)
        assertEquals("Stadtwerke Kaiserslautern Versorgungs-GmbH", e.absender)
        assertEquals("Bismarckstr. 14", e.absenderStrasse)
        assertEquals("67655", e.absenderPlz)
        assertEquals("Kaiserslautern", e.absenderOrt)
        assertEquals("0631 8001-0", e.absenderTelefon)
        assertEquals("www.swk-kl.de", e.absenderWebseite)
        assertEquals("4471120", e.kundennummer)
        assertEquals("RE-2026-118422", e.aktenzeichen)
        assertEquals("Frau Sabine Krämer", e.ansprechpartner)
        assertEquals("0631 8001-2214", e.ansprechpartnerTelefon)
        assertEquals("s.kraemer@swk-kl.de", e.ansprechpartnerEmail)
        assertEquals(LocalDate.of(2026, 10, 1), e.briefdatum)
        assertEquals(LocalDate.of(2026, 10, 20), e.frist)
        assertEquals(BigDecimal("184.32"), e.betrag)
        assertEquals("DE89 3704 0044 0532 0130 00", e.iban)
        assertEquals("COBADEFFXXX", e.bic)
        assertEquals(3, e.dringlichkeit)
        assertEquals("Rechnung von Stadtwerke Kaiserslautern Versorgungs-GmbH über 184,32 € – zu zahlen bis " +
                "20.10.2026 (in 5 Tagen).", Analyse.zusammenfassung(e, heute))
    }

    @Test
    fun bescheidMitWiderspruchsfrist() {
        val text = """
            Finanzamt Kaiserslautern
            Finanzamt Kaiserslautern, Postfach 3360, 67623 Kaiserslautern
            Herrn
            Max Mustermann
            Beispielweg 5
            67657 Kaiserslautern
            Steuernummer 19/123/45678
            Datum 02.10.2026
            Bescheid für 2025 über Einkommensteuer
            Die Einkommensteuer wird festgesetzt auf 1.204,00 EUR
            Erstattung 312,00 EUR
            Rechtsbehelfsbelehrung
            Der Bescheid kann mit dem Einspruch angefochten werden. Der Einspruch ist innerhalb eines Monats
            nach Bekanntgabe des Bescheids einzulegen.
        """.trimIndent()
        val e = Analyse.analysieren(text, heute)
        assertEquals("Bescheid", e.art)
        assertEquals("Finanzamt Kaiserslautern", e.absender)
        assertEquals("Postfach 3360", e.absenderStrasse)
        assertEquals("67623", e.absenderPlz)
        assertEquals("Bescheid für 2025 über Einkommensteuer", e.betreff)
        assertEquals(LocalDate.of(2026, 10, 2), e.briefdatum)
        assertEquals(LocalDate.of(2026, 11, 2), e.frist, "ein Monat ab Briefdatum")
        assertEquals(BigDecimal("312.00"), e.betrag)
        assertEquals("19/123/45678", e.aktenzeichen)
        assertEquals(3, e.dringlichkeit)
    }

    @Test
    fun mahnungVomInkassobuero() {
        val text = """
            Creditreform Inkasso GmbH
            Musterallee 1 · 10115 Berlin
            Frau
            Erika Musterfrau
            Hauptstr. 3
            12345 Musterstadt
            Berlin, 3. Oktober 2026
            Letzte Mahnung vor Einleitung gerichtlicher Schritte
            Vorgangsnummer: 2026/88412
            Sehr geehrte Frau Musterfrau,
            trotz unserer Zahlungserinnerung ist die Forderung noch offen.
            Hauptforderung 89,90 €
            Mahngebühren 5,00 €
            Gesamtforderung 94,90 €
            Bitte zahlen Sie den Gesamtbetrag spätestens am 10.10.2026.
            Bankverbindung: IBAN DE02 1203 0000 0000 2020 51
        """.trimIndent()
        val e = Analyse.analysieren(text, heute)
        assertEquals("Mahnung", e.art)
        assertEquals("Creditreform Inkasso GmbH", e.absender)
        assertEquals("Musterallee 1", e.absenderStrasse)
        assertEquals("10115", e.absenderPlz)
        assertEquals("Berlin", e.absenderOrt)
        assertEquals("Letzte Mahnung vor Einleitung gerichtlicher Schritte", e.betreff)
        assertEquals(LocalDate.of(2026, 10, 3), e.briefdatum)
        assertEquals(LocalDate.of(2026, 10, 10), e.frist)
        assertEquals(BigDecimal("94.90"), e.betrag)
        assertEquals("2026/88412", e.aktenzeichen)
        assertEquals("DE02 1203 0000 0000 2020 51", e.iban)
        assertEquals(4, e.dringlichkeit)
        assertTrue(e.gruende.any { it.contains("vorbei") })
    }

    @Test
    fun krankenkasseMitUnterschrift() {
        val text = """
            AOK Rheinland-Pfalz/Saarland
            Die Gesundheitskasse
            AOK · Postfach 1560 · 67605 Kaiserslautern
            Herrn
            Max Mustermann
            Beispielweg 5
            67657 Kaiserslautern
            Ihre Versichertennummer: A123456789
            Datum: 05.10.2026
            Betreff: Antrag auf Haushaltshilfe
            Sehr geehrter Herr Mustermann,
            für die Bearbeitung Ihres Antrags benötigen wir noch eine ärztliche Bescheinigung.
            Bitte senden Sie uns diese innerhalb von 14 Tagen zu.
            Bei Fragen erreichen Sie mich unter der Durchwahl 0631 3602-118.
            Mit freundlichen Grüßen
            Thomas Becker
            Kundenberater
        """.trimIndent()
        val e = Analyse.analysieren(text, heute)
        assertEquals("Brief", e.art)
        assertEquals("AOK Rheinland-Pfalz/Saarland", e.absender)
        assertEquals("Postfach 1560", e.absenderStrasse)
        assertEquals("67605", e.absenderPlz)
        assertEquals("Antrag auf Haushaltshilfe", e.betreff)
        assertEquals("A123456789", e.kundennummer)
        assertEquals(LocalDate.of(2026, 10, 5), e.briefdatum)
        assertEquals(LocalDate.of(2026, 10, 19), e.frist, "14 Tage ab Briefdatum")
        assertEquals("Thomas Becker", e.ansprechpartner)
        assertEquals("0631 3602-118", e.ansprechpartnerTelefon)
        assertNull(e.betrag)
        assertEquals("", e.iban)
        assertEquals(3, e.dringlichkeit)
    }

    @Test
    fun werbungIstNichtDringend() {
        val e = Analyse.analysieren("MEGA SONDERANGEBOT\nNur diese Woche: 30% Rabatt auf alles!\n" +
                "Jetzt bestellen unter www.beispiel-shop.de", heute)
        assertEquals("Werbung", e.art)
        assertEquals(1, e.dringlichkeit)
        assertNull(e.frist)
    }

    @Test
    fun ibanMitLesefehlernUndEigenesKonto() {
        val text = """
            Wir buchen den Betrag per Lastschrift von Ihrem Konto DE89 3704 0044 0532 0130 00 ab.
            Unsere Bankverbindung: IBAN DE02 12O3 0000 0000 2020 51
        """.trimIndent()
        assertEquals("DE02 1203 0000 0000 2020 51", Analyse.analysieren(text, heute).iban)
    }

    @Test
    fun leererText() {
        val e = Analyse.analysieren("", heute)
        assertEquals("Brief", e.art)
        assertEquals("", e.absender)
        assertEquals(2, e.dringlichkeit)
    }

    @Test
    fun hilfsfunktionen() {
        assertTrue(Iban.gueltig("DE89 3704 0044 0532 0130 00"))
        assertFalse(Iban.gueltig("DE88 3704 0044 0532 0130 00"))
        assertFalse(Iban.gueltig("DE89 3704"))
        assertEquals(LocalDate.of(2026, 10, 8), datumLesen("8.10.2026"))
        assertEquals(LocalDate.of(2026, 10, 8), datumLesen("08.10.26"))
        assertEquals(LocalDate.of(2026, 10, 8), datumLesen("2026-10-08"))
        assertNull(datumLesen("31.02.2026"))
        assertEquals(BigDecimal("1234.50"), betragLesen("1.234,5 €"))
        assertEquals("1.234,50", betragText(BigDecimal("1234.5")))
        assertEquals("in 3 Tagen", Analyse.fristText(heute.plusDays(3), heute))
        assertEquals("seit 2 Tagen vorbei", Analyse.fristText(heute.minusDays(2), heute))
        assertTrue(Analyse.siehtAusWiePerson("Frau Dr. Sabine Krämer"))
        assertTrue(Analyse.siehtAusWiePerson("i. A. Thomas Becker"))
        assertFalse(Analyse.siehtAusWiePerson("Kundenservice"))
        assertFalse(Analyse.siehtAusWiePerson("Stadtwerke Kaiserslautern GmbH"))
    }
}
