package de.briefverwaltung.analyse

import java.math.BigDecimal
import java.text.DecimalFormat
import java.text.DecimalFormatSymbols
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit
import java.util.Locale

/**
 * Was aus dem Text eines Briefes herausgelesen wurde. Leerer Text bzw. null = nicht gefunden.
 *
 * Dieser Teil ist reines Kotlin (ohne Android), damit er sich mit normalen Unit-Tests prüfen lässt.
 */
data class Ergebnis(
    val art: String = "Brief",
    val betreff: String = "",
    val absender: String = "",
    val absenderStrasse: String = "",
    val absenderPlz: String = "",
    val absenderOrt: String = "",
    val absenderTelefon: String = "",
    val absenderEmail: String = "",
    val absenderWebseite: String = "",
    val kundennummer: String = "",
    val ansprechpartner: String = "",
    val ansprechpartnerTelefon: String = "",
    val ansprechpartnerEmail: String = "",
    val briefdatum: LocalDate? = null,
    val frist: LocalDate? = null,
    val betrag: BigDecimal? = null,
    val iban: String = "",
    val bic: String = "",
    val aktenzeichen: String = "",
    val dringlichkeit: Int = 2,
    val gruende: List<String> = emptyList(),
)

/** Arten von Schreiben, die erkannt werden (für die Auswahl in der App). */
val ARTEN = listOf("Brief", "Rechnung", "Mahnung", "Bescheid", "Kündigung", "Vertrag", "Termin",
    "Kontoauszug", "Lohnabrechnung", "Werbung")

private val DEUTSCH = DateTimeFormatter.ofPattern("dd.MM.yyyy")

fun datumText(datum: LocalDate?): String = datum?.format(DEUTSCH) ?: ""

/** „8.10.2026“, „08.10.26“, „2026-10-08“ → Datum; sonst null. */
fun datumLesen(text: String): LocalDate? {
    val t = text.trim()
    if (t.isEmpty()) return null
    Regex("""^(\d{4})-(\d{1,2})-(\d{1,2})$""").find(t)?.let { m ->
        return datum(m.groupValues[3], m.groupValues[2], m.groupValues[1])
    }
    Regex("""^(\d{1,2})\.(\d{1,2})\.(\d{2}|\d{4})$""").find(t)?.let { m ->
        return datum(m.groupValues[1], m.groupValues[2], m.groupValues[3])
    }
    return null
}

/** Deutscher Betrag „1.234,56“ → 1234.56 */
fun betragLesen(text: String): BigDecimal? {
    var t = text.replace("€", "").replace("EUR", "", ignoreCase = true).replace(" ", "").trim()
    if (t.isEmpty()) return null
    t = if (t.contains(',')) t.replace(".", "").replace(',', '.') else t
    return t.toBigDecimalOrNull()?.setScale(2, java.math.RoundingMode.HALF_UP)
}

fun betragText(betrag: BigDecimal?): String {
    if (betrag == null) return ""
    val format = DecimalFormat("#,##0.00", DecimalFormatSymbols(Locale.GERMANY))
    return format.format(betrag)
}

private fun datum(tag: String, monat: String, jahr: String): LocalDate? {
    val j = jahr.toIntOrNull() ?: return null
    val volljahr = if (jahr.length == 2) 2000 + j else j
    return runCatching { LocalDate.of(volljahr, monat.toInt(), tag.toInt()) }.getOrNull()
}

object Iban {
    private val LAENGE = mapOf(
        "DE" to 22, "AT" to 20, "CH" to 21, "LI" to 21, "LU" to 20, "NL" to 18, "BE" to 16, "FR" to 27,
        "IT" to 27, "ES" to 24, "PT" to 25, "PL" to 28, "CZ" to 24, "DK" to 18, "SE" to 24, "NO" to 15,
        "FI" to 18, "GB" to 22, "IE" to 22, "HU" to 28, "HR" to 21, "SI" to 19, "SK" to 24, "GR" to 27,
    )

    fun laenge(land: String): Int? = LAENGE[land]

    fun gueltig(text: String): Boolean {
        val iban = text.replace(" ", "").uppercase()
        if (!Regex("[A-Z]{2}\\d{2}[A-Z0-9]{11,30}").matches(iban)) return false
        LAENGE[iban.substring(0, 2)]?.let { if (iban.length != it) return false }
        var rest = 0
        for (zeichen in iban.substring(4) + iban.substring(0, 4)) {
            val wert = if (zeichen.isDigit()) zeichen - '0' else zeichen - 'A' + 10
            rest = if (wert >= 10) (rest * 100 + wert) % 97 else (rest * 10 + wert) % 97
        }
        return rest == 1
    }

    fun formatieren(text: String): String = text.replace(" ", "").uppercase().chunked(4).joinToString(" ")
}

object Analyse {
    // ------------------------------------------------------------------ Muster

    private val PLZ_ORT = Regex("""^(?:D-)?(\d{5})\s+([A-ZÄÖÜ][\wäöüßÄÖÜ.()/\- ]{1,40})$""")
    private val STRASSE = Regex(
        """^([A-ZÄÖÜ][\wäöüßÄÖÜ.\- ]{1,40}(?:straße|strasse|str\.|weg|platz|allee|gasse|ring|damm|ufer|chaussee|pfad|markt|hof|berg|feld|anlage|park)\s*\d+\s*[a-zA-Z]?(?:\s*-\s*\d+)?|[A-ZÄÖÜ][\wäöüßÄÖÜ.\- ]{2,40}\s\d{1,4}\s?[a-zA-Z]?)$""",
        RegexOption.IGNORE_CASE)
    private val POSTFACH = Regex("""^Postfach\s+[\d ]+$""", RegexOption.IGNORE_CASE)
    private val DATUM_ZAHL = Regex("""(?<![\d.])(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{4}|\d{2})(?![\d])""")
    private val DATUM_TEXT = Regex(
        """(?<!\d)(\d{1,2})\.?\s+(Januar|Februar|März|Maerz|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember|Jan|Feb|Mär|Mrz|Apr|Jun|Jul|Aug|Sept|Sep|Okt|Nov|Dez)\.?\s+(\d{4})(?!\d)""",
        RegexOption.IGNORE_CASE)
    private val MONATE = mapOf("jan" to 1, "feb" to 2, "mär" to 3, "mae" to 3, "mrz" to 3, "apr" to 4, "mai" to 5,
        "jun" to 6, "jul" to 7, "aug" to 8, "sep" to 9, "okt" to 10, "nov" to 11, "dez" to 12)
    private val BETRAG = Regex("""(?<![\d.,])(-?\d{1,3}(?:\.\d{3})+|-?\d+),(\d{2})(?![\d,%])""")
    private val IBAN = Regex("""\b([A-Z]{2}\s?\d{2}(?:\s?[A-Z0-9]{4}){2,7}(?:\s?[A-Z0-9]{1,4})?)""")
    private val BIC = Regex("""\b(?:BIC|SWIFT)(?:-Code)?\s*[:.]?\s*([A-Z]{4}\s?[A-Z]{2}\s?[A-Z0-9]{2}(?:\s?[A-Z0-9]{3})?)\b""")
    private val TELEFON = Regex(
        """\b(?i:tel(?:efon)?|fon|phone|durchwahl|rufnummer|hotline|service-?hotline)\b\.?(?:\s*-?\s*nr\.?)?\s*:?\s*(\+?\(?\d[\d /()\-–]{4,}\d)""")
    private val EMAIL = Regex("""[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}""")
    private val WEB = Regex("""(?i)\b(?:https?://)?(www\.[a-z0-9\-]+(?:\.[a-z0-9\-]+)+)""")
    private val ANREDE = Regex("""^(sehr geehrte|guten tag|hallo|liebe |lieber |moin|grüß gott)""", RegexOption.IGNORE_CASE)
    private val EMPFAENGER = Regex("""^(herrn?|frau|familie|eheleute|firma|an)\b""", RegexOption.IGNORE_CASE)
    private val BETREFF = Regex("""^(?:betreff|betr\.|betrifft|bzgl\.|bezüglich|thema)\s*:?\s*(.+)$""", RegexOption.IGNORE_CASE)
    private val GRUSS = Regex("""^(mit freundlichen grüßen|mit freundlichem gruß|mit freundlichen grüssen|freundliche grüße|viele grüße|beste grüße|mit besten grüßen|hochachtungsvoll)""",
        RegexOption.IGNORE_CASE)
    private val AP_LABEL = Regex(
        """^(?:ihr(?:e)?\s+)?(?:ansprechpartner(?:in)?|ansprechperson|sachbearbeiter(?:in)?|bearbeiter(?:in)?|kontaktperson|es schreibt ihnen|bearbeitet von|auskunft erteilt|kontakt)\s*:?\s*(.*)$""",
        RegexOption.IGNORE_CASE)

    private val RECHTSFORM = Regex("""(?i)\b(gmbh|ag|kg|kgaa|e\.\s?v\.|eg|mbh|ohg|ug|se|gbr|ltd\.?|inc\.?)\b""")
    private val ORGANISATION = listOf("stadtwerke", "finanzamt", "amt ", "amt für", "stadtverwaltung", "stadt ",
        "gemeinde", "kreisverwaltung", "landkreis", "jobcenter", "agentur für arbeit", "krankenkasse", "aok",
        "barmer", "techniker", "dak", "ikk", "bkk", "versicherung", "bank", "sparkasse", "volksbank", "raiffeisen",
        "verwaltung", "gericht", "polizei", "schule", "universität", "hochschule", "verein", "verband", "kanzlei",
        "rechtsanwält", "notar", "praxis", "klinik", "telekom", "vodafone", "deutsche post", "rundfunk",
        "beitragsservice", "inkasso", "bundesagentur", "rentenversicherung", "familienkasse", "zoll", "ministerium",
        "hausverwaltung", "immobilien", "energie", "wasser", "versorgung", "werke", "service", "behörde", "landesamt")

    private val ART_WOERTER = listOf(
        "Lohnabrechnung" to listOf("lohnabrechnung", "gehaltsabrechnung", "entgeltabrechnung", "verdienstabrechnung"),
        "Kontoauszug" to listOf("kontoauszug"),
        "Mahnung" to listOf("mahnung", "zahlungserinnerung", "letzte erinnerung", "inkasso", "vollstreckung",
            "pfändung", "zahlungsaufforderung", "mahnbescheid"),
        "Kündigung" to listOf("kündigung", "kündigen wir"),
        "Bescheid" to listOf("bescheid", "festsetzung"),
        "Rechnung" to listOf("rechnung", "abrechnung", "zahlbetrag"),
        "Vertrag" to listOf("vertragsbestätigung", "auftragsbestätigung", "vertrag"),
        "Termin" to listOf("einladung", "termin am", "vorladung", "terminvereinbarung"),
        "Werbung" to listOf("gewinnspiel", "sonderangebot", "jetzt bestellen", "gutschein", "rabatt", "angebot nur"),
    )

    private val ZAHLWOERTER = mapOf("eins" to 1, "einer" to 1, "einem" to 1, "eines" to 1, "zwei" to 2, "drei" to 3, "vier" to 4,
        "fünf" to 5, "sechs" to 6, "sieben" to 7, "acht" to 8, "zehn" to 10, "vierzehn" to 14,
        "einundzwanzig" to 21, "dreißig" to 30, "dreissig" to 30)

    private data class Fund<T>(val wert: T, val zeile: Int, val anfang: Int)

    // ------------------------------------------------------------------ Einstieg

    fun analysieren(text: String, heute: LocalDate = LocalDate.now()): Ergebnis {
        val zeilen = text.lines().map { it.trim().replace(Regex("\\s+"), " ") }.filter { it.isNotEmpty() }
        val ganz = zeilen.joinToString("\n")
        val klein = ganz.lowercase()
        val empfaenger = empfaengerZeilen(zeilen)

        val betreff = betreffFinden(zeilen, empfaenger)
        val art = artFinden(betreff.lowercase()) ?: artFinden(klein) ?: "Brief"
        val daten = datenFinden(zeilen)
        val briefdatum = briefdatumFinden(zeilen, daten, heute)
        val frist = fristFinden(zeilen, daten, briefdatum, heute)
        val absender = absenderFinden(zeilen, empfaenger)
        val ap = ansprechpartnerFinden(zeilen, absender.name)
        val (absTelefon, apTelefon) = telefonFinden(zeilen, ap.zeile)
        val emails = EMAIL.findAll(ganz).map { it.value.trimEnd('.') }.distinct().toList()
        val apEmail = if (ap.name.isNotEmpty()) emails.firstOrNull { passtZuPerson(it, ap.name) } ?: "" else ""
        val absEmail = emails.firstOrNull { it != apEmail } ?: ""

        var ergebnis = Ergebnis(
            art = art,
            betreff = betreff,
            absender = absender.name,
            absenderStrasse = absender.strasse,
            absenderPlz = absender.plz,
            absenderOrt = absender.ort,
            absenderTelefon = absTelefon,
            absenderEmail = absEmail,
            absenderWebseite = WEB.find(ganz)?.groupValues?.get(1)?.lowercase() ?: "",
            kundennummer = nummerFinden(ganz, KUNDENNUMMER),
            ansprechpartner = ap.name,
            ansprechpartnerTelefon = apTelefon,
            ansprechpartnerEmail = apEmail,
            briefdatum = briefdatum,
            frist = frist,
            betrag = betragFinden(zeilen),
            iban = ibanFinden(zeilen),
            bic = BIC.find(ganz.uppercase())?.groupValues?.get(1)?.replace(" ", "") ?: "",
            aktenzeichen = AKTENZEICHEN.firstNotNullOfOrNull { nummerFinden(ganz, it).ifEmpty { null } } ?: "",
        )
        ergebnis = dringlichkeitBewerten(ergebnis, klein, heute)
        return ergebnis
    }

    /** Ein Satz wie „Rechnung von Stadtwerke Kaiserslautern über 184,32 € – zu zahlen bis 20.10.2026 (in 5 Tagen).“ */
    fun zusammenfassung(e: Ergebnis, heute: LocalDate = LocalDate.now()): String {
        val teile = StringBuilder(e.art)
        if (e.absender.isNotEmpty()) teile.append(" von ").append(e.absender)
        if (e.betrag != null) teile.append(" über ").append(betragText(e.betrag)).append(" €")
        e.frist?.let { frist ->
            teile.append(if (e.betrag != null) " – zu zahlen bis " else " – Frist: ").append(datumText(frist))
            teile.append(" (").append(fristText(frist, heute)).append(")")
        }
        return teile.append('.').toString()
    }

    fun fristText(frist: LocalDate, heute: LocalDate = LocalDate.now()): String {
        val tage = ChronoUnit.DAYS.between(heute, frist)
        return when {
            tage == 0L -> "heute"
            tage == 1L -> "morgen"
            tage > 1 -> "in $tage Tagen"
            tage == -1L -> "seit gestern vorbei"
            else -> "seit ${-tage} Tagen vorbei"
        }
    }

    // ------------------------------------------------------------------ Empfänger, Absender, Betreff

    /** Zeilen der Empfängeradresse im Sichtfenster (die gehören nicht zum Absender). */
    private fun empfaengerZeilen(zeilen: List<String>): Set<Int> {
        val ergebnis = mutableSetOf<Int>()
        for (i in 0 until minOf(zeilen.size, 25)) {
            if (!EMPFAENGER.containsMatchIn(zeilen[i]) || ANREDE.containsMatchIn(zeilen[i])) continue
            for (j in i until minOf(i + 5, zeilen.size)) {
                ergebnis += j
                if (PLZ_ORT.matches(zeilen[j])) break
            }
            break
        }
        return ergebnis
    }

    private data class Absender(val name: String = "", val strasse: String = "", val plz: String = "", val ort: String = "")

    private fun istOrganisation(zeile: String): Boolean {
        val k = zeile.lowercase()
        return RECHTSFORM.containsMatchIn(zeile) || ORGANISATION.any { k.contains(it) }
    }

    private fun bereinigen(text: String): String =
        text.replace(Regex("""^(absender|von)\s*:\s*""", RegexOption.IGNORE_CASE), "").trim(' ', ',', '·', '|', '-', '–', ':')

    private val TRENNER = Regex("""\s*[·•|]\s*|\s+[-–]\s+|,\s+""")

    /** Straße/Postfach und PLZ/Ort aus einer Zeile wie „Bismarckstr. 14 · 67655 Kaiserslautern“. */
    private fun adresseAus(zeile: String): Absender {
        var strasse = ""
        var plz = ""
        var ort = ""
        for (teil in zeile.split(TRENNER).map { it.trim() }) {
            if (strasse.isEmpty() && (STRASSE.matches(teil) || POSTFACH.matches(teil))) strasse = teil
            PLZ_ORT.find(teil)?.let { if (plz.isEmpty()) { plz = it.groupValues[1]; ort = it.groupValues[2].trim() } }
        }
        return Absender(strasse = strasse, plz = plz, ort = ort)
    }

    private fun absenderFinden(zeilen: List<String>, empfaenger: Set<Int>): Absender {
        val empfaengerStart = empfaenger.minOrNull() ?: zeilen.size
        // Rücksendezeile über dem Sichtfenster: „Stadtwerke KL · Bismarckstr. 14 · 67655 Kaiserslautern“
        var ruecksende: Absender? = null
        var rueckZeile = -1
        for (i in 0 until minOf(zeilen.size, 20)) {
            if (i in empfaenger || zeilen[i].length > 120) continue
            val teile = zeilen[i].split(TRENNER).map { it.trim() }.filter { it.isNotEmpty() }
            if (teile.size < 2 || teile.none { PLZ_ORT.matches(it) }) continue
            val adresse = adresseAus(zeilen[i])
            val name = bereinigen(teile[0])
            val nameOk = name.length >= 3 && !PLZ_ORT.matches(name) && !STRASSE.matches(name) && !POSTFACH.matches(name)
            ruecksende = adresse.copy(name = if (nameOk) name else "")
            rueckZeile = i
            break
        }
        // Briefkopf: erste Zeile mit Firmen- oder Behördennamen (vor der Empfängeradresse)
        val ende = minOf(zeilen.size, 14, maxOf(empfaengerStart, 4))
        val kopf = (0 until ende).firstOrNull {
            it !in empfaenger && it != rueckZeile && istOrganisation(zeilen[it]) && zeilen[it].length <= 70 &&
                    !ANREDE.containsMatchIn(zeilen[it]) && !zeilen[it].contains('@') && !TELEFON.containsMatchIn(zeilen[it])
        }
        if (kopf != null) {
            var adresse = ruecksende ?: Absender()
            if (adresse.plz.isEmpty()) {
                for (j in kopf + 1 until minOf(kopf + 6, zeilen.size)) {
                    if (j in empfaenger) break
                    val gefunden = adresseAus(zeilen[j])
                    if (adresse.strasse.isEmpty() && gefunden.strasse.isNotEmpty()) adresse = adresse.copy(strasse = gefunden.strasse)
                    if (gefunden.plz.isNotEmpty()) { adresse = adresse.copy(plz = gefunden.plz, ort = gefunden.ort); break }
                }
            }
            return adresse.copy(name = bereinigen(zeilen[kopf]))
        }
        if (ruecksende != null && ruecksende.name.isNotEmpty()) return ruecksende
        // sonst die allererste sinnvolle Zeile
        val erste = (0 until minOf(zeilen.size, 14)).firstOrNull {
            it !in empfaenger && zeilen[it].count { c -> c.isLetter() } >= 3 && zeilen[it].length <= 60 &&
                    !DATUM_ZAHL.containsMatchIn(zeilen[it]) && !zeilen[it].contains('@') &&
                    !zeilen[it].lowercase().startsWith("seite") && !ANREDE.containsMatchIn(zeilen[it])
        } ?: return ruecksende ?: Absender()
        return (ruecksende ?: Absender()).copy(name = bereinigen(zeilen[erste]))
    }

    private fun betreffFinden(zeilen: List<String>, empfaenger: Set<Int>): String {
        zeilen.firstNotNullOfOrNull { BETREFF.find(it)?.groupValues?.get(1) }?.let { return kuerzen(it) }
        val anrede = zeilen.indexOfFirst { ANREDE.containsMatchIn(it) }
        if (anrede > 0) {
            for (j in anrede - 1 downTo maxOf(0, anrede - 4)) {
                val z = zeilen[j]
                if (j in empfaenger || nurDatum(z) || PLZ_ORT.matches(z) || z.length < 4 || z.endsWith(":") ||
                    Regex("""^[^:]{2,35}:\s*.*\d""").containsMatchIn(z) ||          // „Vorgangsnummer: 2026/88412“
                    Regex("""^(seite|datum|ihr zeichen|unser zeichen|ihre nachricht)""", RegexOption.IGNORE_CASE).containsMatchIn(z) ||
                    z.count { it.isDigit() } > z.length / 2) continue
                return kuerzen(z)
            }
        }
        val grenze = maxOf((zeilen.size * 0.6).toInt(), 15)
        return zeilen.take(grenze).withIndex().firstOrNull { (i, z) ->
            val k = z.lowercase()
            i !in empfaenger && z.length in 6..100 && !z.contains(':') &&
                    ART_WOERTER.any { (_, worte) -> worte.any { k.contains(it) } }
        }?.let { kuerzen(it.value) } ?: ""
    }

    private fun kuerzen(text: String) = text.trim().trimEnd('.', ',', ':').take(150)

    private fun nurDatum(zeile: String): Boolean {
        val ohne = DATUM_ZAHL.replace(DATUM_TEXT.replace(zeile, ""), "")
        return ohne.replace(Regex("""(?i)\b(den|am|datum)\b"""), "").replace(Regex("""[\s,.:]"""), "").length <= 2 ||
                Regex("""^[A-ZÄÖÜ][\wäöüß .\-/]{1,40},\s*(den\s+)?$""").matches(ohne.trim())
    }

    private fun artFinden(text: String): String? =
        ART_WOERTER.firstOrNull { (_, worte) -> worte.any { text.contains(it) } }?.first

    // ------------------------------------------------------------------ Ansprechpartner, Telefon

    private data class Person(val name: String = "", val zeile: Int = -1)

    private val KEINE_NAMEN = setOf("kundenservice", "service", "team", "ihr", "ihre", "mit", "seite", "abteilung",
        "geschäftsführer", "geschäftsführung", "vorstand", "kundencenter", "kundenbetreuung", "telefon", "anlage",
        "anlagen", "i.", "a.", "freundlichen", "grüßen", "postfach", "sachbearbeitung", "der", "die", "das")

    fun siehtAusWiePerson(text: String): Boolean {
        var worte = text.replace(Regex("""^(i\.\s?a\.|i\.\s?v\.|ppa\.)\s*""", RegexOption.IGNORE_CASE), "")
            .split(' ').filter { it.isNotEmpty() }
        var mitAnrede = false
        while (worte.isNotEmpty() && worte[0].trimEnd('.').lowercase() in setOf("frau", "herr", "herrn", "dr", "prof")) {
            if (worte[0].lowercase().startsWith("frau") || worte[0].lowercase().startsWith("herr")) mitAnrede = true
            worte = worte.drop(1)
        }
        if (worte.isEmpty() || worte.size > 4) return false
        if (worte.size == 1 && !mitAnrede) return false
        if (worte.any { it.lowercase().trimEnd('.', ',') in KEINE_NAMEN }) return false
        if (istOrganisation(text)) return false
        return worte.all { Regex("""^[A-ZÄÖÜ][a-zäöüß'\-]*\.?$""").matches(it) } && worte.any { it.trimEnd('.').length >= 3 }
    }

    private fun personBereinigen(text: String): String =
        text.replace(Regex("""^(i\.\s?a\.|i\.\s?v\.|ppa\.)\s*""", RegexOption.IGNORE_CASE), "").trim()

    private fun ansprechpartnerFinden(zeilen: List<String>, absender: String): Person {
        for ((i, zeile) in zeilen.withIndex()) {
            val treffer = AP_LABEL.find(zeile) ?: continue
            var name = treffer.groupValues[1].split(Regex("""[,;]|\s(?i:tel|telefon|durchwahl|e-mail|mail)\b|\s\d""")).first().trim()
            if (name.isEmpty() && i + 1 < zeilen.size) name = zeilen[i + 1].split(',').first().trim()
            name = personBereinigen(name)
            if (siehtAusWiePerson(name)) return Person(name, i)
        }
        val gruss = zeilen.indexOfFirst { GRUSS.containsMatchIn(it) }
        if (gruss >= 0) {
            for (j in gruss + 1 until minOf(gruss + 4, zeilen.size)) {
                val name = personBereinigen(zeilen[j])
                if (name.equals(absender, ignoreCase = true)) continue
                if (siehtAusWiePerson(name)) return Person(name, j)
            }
        }
        return Person()
    }

    private fun passtZuPerson(email: String, name: String): Boolean {
        val nachname = name.split(' ').last().lowercase()
            .replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
        return nachname.length >= 3 && email.lowercase().substringBefore('@').contains(nachname)
    }

    /** Telefonnummern: (Absender, Ansprechpartner). Durchwahl oder Nummer beim Ansprechpartner zählt für ihn. */
    private fun telefonFinden(zeilen: List<String>, apZeile: Int): Pair<String, String> {
        var absender = ""
        var ap = ""
        for ((i, zeile) in zeilen.withIndex()) {
            val nummer = TELEFON.find(zeile)?.groupValues?.get(1)?.trim()?.trimEnd('-', '–', '/', ' ') ?: continue
            val fuerAp = zeile.contains("durchwahl", ignoreCase = true) || (apZeile >= 0 && i in apZeile..apZeile + 2)
            if (fuerAp && ap.isEmpty()) ap = nummer
            else if (!fuerAp && absender.isEmpty()) absender = nummer
        }
        return absender to ap
    }

    // ------------------------------------------------------------------ Nummern

    private val NUMMER = """\s*[:.]?\s*(?:Nr\.?\s*)?([A-Z0-9][A-Za-z0-9\-/.]*(?: (?:\d[A-Za-z0-9\-/.]*|[A-Z]{1,3}\b)){0,3})"""
    private val KUNDENNUMMER = Regex("""\b(?i:kunden(?:-?\s?nr\.?|nummer)|kd\.?-?\s?nr\.?|mitglieds(?:-?\s?nr\.?|nummer)|versicherten(?:-?\s?nr\.?|nummer)|vertragskonto(?:nummer)?|zählernummer)$NUMMER""")
    private val AKTENZEICHEN = listOf(
        Regex("""\b(?i:aktenzeichen|az\.|unser zeichen|geschäftszeichen|gz\.)$NUMMER"""),
        Regex("""\b(?i:rechnungs(?:-?\s?nr\.?|nummer)|re\.?-?\s?nr\.?|belegnummer)$NUMMER"""),
        Regex("""\b(?i:vorgangs(?:-?\s?nr\.?|nummer)|schaden(?:-?\s?nr\.?|nummer)|fall(?:-?\s?nr\.?|nummer)|mahn(?:-?\s?nr\.?|nummer))$NUMMER"""),
        Regex("""\b(?i:vertrags(?:-?\s?nr\.?|nummer)|versicherungsschein(?:-?\s?nr\.?|nummer)|policen(?:-?\s?nr\.?|nummer))$NUMMER"""),
        Regex("""\b(?i:steuer(?:-?\s?nr\.?|nummer)|steuer-id)$NUMMER"""),
    )

    private fun nummerFinden(text: String, muster: Regex): String =
        muster.findAll(text).map { it.groupValues[1].trim().trimEnd('.', '-', '/') }
            .firstOrNull { wert -> wert.any { it.isDigit() } } ?: ""

    // ------------------------------------------------------------------ Geld

    private val STARKE_BETRAGSWORTE = listOf("gesamtbetrag", "rechnungsbetrag", "zu zahlen", "zahlbetrag",
        "nachzahlung", "offener betrag", "offene forderung", "fälliger betrag", "endbetrag", "gesamtsumme",
        "zahlungsbetrag", "betrag von", "forderung", "mahnbetrag", "überweisen", "summe", "gesamt", "erstattung",
        "guthaben", "beitrag", "abschlag")

    private fun betragFinden(zeilen: List<String>): BigDecimal? {
        var bester: BigDecimal? = null
        var besterWert = Int.MIN_VALUE
        for ((i, zeile) in zeilen.withIndex()) {
            val k = zeile.lowercase()
            for (m in BETRAG.findAll(zeile)) {
                val wert = betragLesen(m.value) ?: continue
                if (wert.signum() == 0) continue
                var punkte = 0
                val umfeld = k + " " + (zeilen.getOrNull(i - 1)?.lowercase() ?: "")
                if (STARKE_BETRAGSWORTE.any { k.contains(it) }) punkte += 5
                else if (STARKE_BETRAGSWORTE.any { umfeld.contains(it) }) punkte += 3
                if (k.contains("€") || k.contains("eur")) punkte += 2
                if (Regex("""mwst|ust\.|umsatzsteuer|netto|zzgl|mehrwertsteuer|%""").containsMatchIn(k)) punkte -= 3
                if (bester == null || punkte > besterWert || (punkte == besterWert && wert > bester)) {
                    bester = wert.abs()
                    besterWert = punkte
                }
            }
        }
        return bester
    }

    // ------------------------------------------------------------------ IBAN

    private fun ibanFinden(zeilen: List<String>): String {
        var beste = ""
        var bestePunkte = Int.MIN_VALUE
        for ((i, zeile) in zeilen.withIndex()) {
            val gross = zeile.uppercase()
            for (m in IBAN.findAll(gross)) {
                val iban = ibanPruefen(m.value.replace(" ", "")) ?: continue
                val k = zeile.lowercase()
                val umfeld = (zeilen.getOrNull(i - 1) ?: "").lowercase() + " " + k
                var punkte = 0
                if (umfeld.contains("iban") || umfeld.contains("bankverbindung") || umfeld.contains("konto")) punkte += 2
                if (Regex("""unsere bankverbindung|unser konto|zahlbar an|empfänger|überweisen sie""").containsMatchIn(umfeld)) punkte += 2
                // Das eigene Konto (z. B. bei Lastschrift) ist nicht die Bankverbindung des Absenders
                if (Regex("""ihre bankverbindung|ihr konto|ihrem konto|von ihrem|lastschrift|abgebucht|einzug|eingezogen""")
                        .containsMatchIn(k)) punkte -= 4
                if (punkte > bestePunkte) {
                    beste = iban
                    bestePunkte = punkte
                }
            }
        }
        return if (beste.isEmpty()) "" else Iban.formatieren(beste)
    }

    /** Prüft eine IBAN – auch wenn hinten ein Wort mitgelesen oder 0 als O erkannt wurde. */
    private fun ibanPruefen(roh: String): String? {
        val laenge = Iban.laenge(roh.take(2))
        val kandidaten = mutableListOf<String>()
        if (laenge != null && roh.length >= laenge) kandidaten += roh.take(laenge) else kandidaten += roh
        for (k in kandidaten.toList()) {
            if (k.take(2) in setOf("DE", "AT")) {
                kandidaten += k.take(2) + k.drop(2).replace('O', '0').replace('I', '1').replace('L', '1')
                    .replace('S', '5').replace('B', '8').replace('Z', '2')
            }
        }
        return kandidaten.firstOrNull { Iban.gueltig(it) }
    }

    // ------------------------------------------------------------------ Datum und Frist

    private fun datenFinden(zeilen: List<String>): List<Fund<LocalDate>> {
        val funde = mutableListOf<Fund<LocalDate>>()
        for ((i, zeile) in zeilen.withIndex()) {
            for (m in DATUM_ZAHL.findAll(zeile)) {
                datum(m.groupValues[1], m.groupValues[2], m.groupValues[3])?.let { funde += Fund(it, i, m.range.first) }
            }
            for (m in DATUM_TEXT.findAll(zeile)) {
                val monat = MONATE[m.groupValues[2].lowercase().take(3)] ?: continue
                datum(m.groupValues[1], monat.toString(), m.groupValues[3])?.let { funde += Fund(it, i, m.range.first) }
            }
        }
        return funde.sortedWith(compareBy({ it.zeile }, { it.anfang }))
    }

    private val FRIST_STARK = Regex(
        """(bis zum|bis spätestens|spätestens|zahlbar bis|zahlbar am|fällig am|fällig zum|fällig bis|fälligkeit|frist|zahlungsziel|bis einschließlich|einzureichen bis|abzugeben bis|vorzulegen bis|bitte bis)\s*:?\s*(am|zum|den)?\s*$""")
    private val FRIST_SCHWACH = Regex("""\b(bis|vor dem|termin)\s*:?\s*(am|zum|den)?\s*$""")

    private fun fristPunkte(zeilen: List<String>, fund: Fund<LocalDate>): Int {
        val davor = zeilen[fund.zeile].take(fund.anfang).lowercase().takeLast(60)
        val vorzeile = if (fund.anfang < 3) (zeilen.getOrNull(fund.zeile - 1) ?: "").lowercase().takeLast(60) else ""
        return when {
            FRIST_STARK.containsMatchIn(davor) || FRIST_STARK.containsMatchIn(vorzeile) -> 3
            FRIST_SCHWACH.containsMatchIn(davor) || FRIST_SCHWACH.containsMatchIn(vorzeile) -> 1
            Regex("""fällig|frist|spätestens|zahlbar""").containsMatchIn(davor) -> 2
            else -> 0
        }
    }

    private fun briefdatumFinden(zeilen: List<String>, daten: List<Fund<LocalDate>>, heute: LocalDate): LocalDate? {
        val obererTeil = maxOf(6, (zeilen.size * 0.45).toInt())
        var bestes: LocalDate? = null
        var bestePunkte = 0
        for (fund in daten) {
            if (fund.wert.isAfter(heute.plusDays(7)) || fund.wert.isBefore(heute.minusYears(3))) continue
            if (fristPunkte(zeilen, fund) > 0) continue
            val zeile = zeilen[fund.zeile]
            val k = zeile.lowercase()
            val punkte = when {
                Regex("""geburts|liefer|leistungs|zeitraum|vom|gültig|zahlungs""").containsMatchIn(k.take(fund.anfang)) -> 0
                k.contains("datum") -> 5
                Regex("""^[A-ZÄÖÜ][\wäöüß .\-/]{1,40},\s*(den\s+)?$""").matches(zeile.take(fund.anfang)) -> 5
                nurDatum(zeile) && fund.zeile < obererTeil -> 3
                fund.zeile < obererTeil -> 1
                else -> 0
            }
            if (punkte > bestePunkte) {
                bestes = fund.wert
                bestePunkte = punkte
            }
        }
        return bestes
    }

    private fun fristFinden(zeilen: List<String>, daten: List<Fund<LocalDate>>, briefdatum: LocalDate?,
                            heute: LocalDate): LocalDate? {
        val frueheste = (briefdatum ?: heute.minusMonths(6))
        val kandidaten = daten.map { it to fristPunkte(zeilen, it) }
            .filter { (fund, punkte) -> punkte > 0 && !fund.wert.isBefore(frueheste) && fund.wert.isBefore(heute.plusYears(2)) }
        if (kandidaten.isNotEmpty()) {
            val maximum = kandidaten.maxOf { it.second }
            return kandidaten.filter { it.second == maximum }.minOf { it.first.wert }
        }
        // „innerhalb von 14 Tagen“, „binnen eines Monats“ … ab dem Briefdatum
        val basis = briefdatum ?: heute
        val text = zeilen.joinToString(" ").lowercase()
        Regex("""(?:innerhalb|binnen)\s+(?:von\s+)?(\d{1,3}|[a-zäöüß]+)\s+(tag|tage|tagen|woche|wochen|monat|monate|monaten|monats)\b""")
            .find(text)?.let { m ->
                val zahl = m.groupValues[1].toIntOrNull() ?: ZAHLWOERTER[m.groupValues[1]] ?: return@let
                val einheit = m.groupValues[2]
                return when {
                    einheit.startsWith("tag") -> basis.plusDays(zahl.toLong())
                    einheit.startsWith("woche") -> basis.plusWeeks(zahl.toLong())
                    else -> basis.plusMonths(zahl.toLong())
                }
            }
        return null
    }

    // ------------------------------------------------------------------ Dringlichkeit

    private fun dringlichkeitBewerten(e: Ergebnis, klein: String, heute: LocalDate): Ergebnis {
        val gruende = mutableListOf<String>()
        var stufe = when (e.art) {
            "Mahnung" -> { gruende += "Es ist eine Mahnung."; 4 }
            "Bescheid" -> { gruende += "Bei Bescheiden gibt es meist eine Widerspruchsfrist."; 3 }
            "Kündigung" -> { gruende += "Es geht um eine Kündigung."; 3 }
            "Werbung", "Kontoauszug", "Lohnabrechnung" -> 1
            else -> 2
        }
        if (Regex("""letzte mahnung|letzte aufforderung|vollstreckung|gerichtlich|inkasso|pfändung|mahnbescheid|sperrung""")
                .containsMatchIn(klein)) {
            if (stufe < 4) gruende += "Es drohen Folgen (Inkasso, Sperre oder Gericht)."
            stufe = 4
        }
        if (Regex("""\b(sofort|umgehend|unverzüglich)\b""").containsMatchIn(klein) && stufe < 3) {
            stufe = 3
            gruende += "Im Brief steht „sofort“ bzw. „umgehend“."
        }
        e.frist?.let { frist ->
            val tage = ChronoUnit.DAYS.between(heute, frist)
            when {
                tage < 0 -> { stufe = 4; gruende += "Die Frist ist schon vorbei." }
                tage <= 3 -> { stufe = 4; gruende += "Die Frist endet ${fristText(frist, heute)}." }
                tage <= 14 && stufe < 3 -> { stufe = 3; gruende += "Die Frist endet ${fristText(frist, heute)}." }
                else -> {}
            }
        }
        return e.copy(dringlichkeit = stufe, gruende = gruende)
    }
}
