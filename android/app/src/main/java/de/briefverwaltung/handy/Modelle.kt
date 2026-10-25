package de.briefverwaltung.handy

import de.briefverwaltung.analyse.Ergebnis
import de.briefverwaltung.analyse.Iban
import de.briefverwaltung.analyse.betragLesen
import de.briefverwaltung.analyse.betragText
import de.briefverwaltung.analyse.datumLesen
import de.briefverwaltung.analyse.datumText
import org.json.JSONArray
import org.json.JSONObject

enum class Status { ENTWURF, WARTET, GESENDET, FEHLER }

enum class Tastatur { TEXT, ZAHL, TELEFON, EMAIL, DATUM, NAME }

/** Ein Eingabefeld. Der Schlüssel ist zugleich der Name, unter dem der PC den Wert erwartet. */
data class Feld(
    val schluessel: String,
    val bezeichnung: String,
    val tastatur: Tastatur = Tastatur.TEXT,
    val mehrzeilig: Boolean = false,
)

object Felder {
    val brief = listOf(
        Feld("betreff", "Betreff"),
        Feld("absender", "Absender", Tastatur.NAME),
        Feld("briefdatum", "Briefdatum (TT.MM.JJJJ)", Tastatur.DATUM),
        Feld("frist", "Frist / fällig am (TT.MM.JJJJ)", Tastatur.DATUM),
        Feld("betrag", "Betrag in €", Tastatur.ZAHL),
        Feld("aktenzeichen", "Aktenzeichen / Rechnungsnummer"),
        Feld("anlass", "Anlass (zum Gruppieren, z. B. „Nebenkosten 2026“)"),
        Feld("notizen", "Notizen", mehrzeilig = true),
    )
    val absender = listOf(
        Feld("absender_strasse", "Straße oder Postfach"),
        Feld("absender_plz", "PLZ", Tastatur.ZAHL),
        Feld("absender_ort", "Ort", Tastatur.NAME),
        Feld("absender_telefon", "Telefon", Tastatur.TELEFON),
        Feld("absender_email", "E-Mail", Tastatur.EMAIL),
        Feld("absender_webseite", "Webseite"),
        Feld("kundennummer", "Meine Kundennummer"),
    )
    val ansprechpartner = listOf(
        Feld("ansprechpartner", "Name", Tastatur.NAME),
        Feld("ansprechpartner_telefon", "Telefon / Durchwahl", Tastatur.TELEFON),
        Feld("ansprechpartner_email", "E-Mail", Tastatur.EMAIL),
    )
    val bank = listOf(
        Feld("iban", "IBAN"),
        Feld("bic", "BIC"),
    )
    val alle = brief + absender + ansprechpartner + bank
}

val DRINGLICHKEIT = mapOf(1 to "niedrig", 2 to "normal", 3 to "hoch", 4 to "sehr dringend")

/** Die Angaben zu einem Brief, so wie sie in den Eingabefeldern stehen – alles als Text. */
data class Briefdaten(
    val werte: Map<String, String> = emptyMap(),
    val art: String = "Brief",
    val dringlichkeit: Int = 2,
) {
    operator fun get(schluessel: String): String = werte[schluessel] ?: ""

    fun mit(schluessel: String, wert: String) = copy(werte = werte + (schluessel to wert))

    val titel: String
        get() = this["betreff"].ifBlank { listOf(art, this["absender"]).filter { it.isNotBlank() }.joinToString(" – ") }

    fun json(): JSONObject = JSONObject().apply {
        put("art", art)
        put("dringlichkeit", dringlichkeit)
        put("werte", JSONObject(werte))
    }

    /** Was an den PC geht: Datum als JJJJ-MM-TT, Betrag mit Punkt; was nicht stimmt, wird weggelassen. */
    fun fuerPc(): JSONObject = JSONObject().apply {
        put("art", art)
        put("dringlichkeit", dringlichkeit)
        for ((schluessel, wert) in werte) {
            val text = wert.trim()
            if (text.isEmpty()) continue
            when (schluessel) {
                "briefdatum", "frist" -> datumLesen(text)?.let { put(schluessel, it.toString()) }
                "betrag" -> betragLesen(text)?.let { put(schluessel, it.toPlainString()) }
                "iban" -> if (Iban.gueltig(text)) put(schluessel, text.replace(" ", "").uppercase())
                else -> put(schluessel, text)
            }
        }
    }

    companion object {
        fun aus(e: Ergebnis) = Briefdaten(
            werte = mapOf(
                "betreff" to e.betreff, "absender" to e.absender, "absender_strasse" to e.absenderStrasse,
                "absender_plz" to e.absenderPlz, "absender_ort" to e.absenderOrt,
                "absender_telefon" to e.absenderTelefon, "absender_email" to e.absenderEmail,
                "absender_webseite" to e.absenderWebseite, "kundennummer" to e.kundennummer,
                "ansprechpartner" to e.ansprechpartner, "ansprechpartner_telefon" to e.ansprechpartnerTelefon,
                "ansprechpartner_email" to e.ansprechpartnerEmail, "briefdatum" to datumText(e.briefdatum),
                "frist" to datumText(e.frist), "betrag" to betragText(e.betrag), "iban" to e.iban, "bic" to e.bic,
                "aktenzeichen" to e.aktenzeichen,
            ).filterValues { it.isNotBlank() },
            art = e.art,
            dringlichkeit = e.dringlichkeit,
        )

        fun ausJson(j: JSONObject): Briefdaten {
            val werte = mutableMapOf<String, String>()
            j.optJSONObject("werte")?.let { w -> w.keys().forEach { werte[it] = w.optString(it) } }
            return Briefdaten(werte, j.optString("art", "Brief"), j.optInt("dringlichkeit", 2))
        }
    }
}

/** Ein gescannter Brief auf dem Handy: Fotos, erkannter Text, Angaben und Stand der Übertragung. */
data class Scan(
    val id: String,
    val erstellt: Long,
    val seiten: List<String>,
    val text: String,
    val daten: Briefdaten,
    val status: Status,
    val meldung: String = "",
    val briefId: Int = 0,
    val zusammenfassung: String = "",
    val gruende: List<String> = emptyList(),
) {
    fun json(): JSONObject = JSONObject().apply {
        put("id", id)
        put("erstellt", erstellt)
        put("seiten", JSONArray(seiten))
        put("text", text)
        put("daten", daten.json())
        put("status", status.name)
        put("meldung", meldung)
        put("briefId", briefId)
        put("zusammenfassung", zusammenfassung)
        put("gruende", JSONArray(gruende))
    }

    companion object {
        fun ausJson(j: JSONObject): Scan {
            fun liste(name: String): List<String> {
                val a = j.optJSONArray(name) ?: return emptyList()
                return (0 until a.length()).map { a.optString(it) }
            }
            return Scan(
                id = j.getString("id"),
                erstellt = j.optLong("erstellt"),
                seiten = liste("seiten"),
                text = j.optString("text"),
                daten = Briefdaten.ausJson(j.optJSONObject("daten") ?: JSONObject()),
                status = runCatching { Status.valueOf(j.optString("status")) }.getOrDefault(Status.WARTET),
                meldung = j.optString("meldung"),
                briefId = j.optInt("briefId"),
                zusammenfassung = j.optString("zusammenfassung"),
                gruende = liste("gruende"),
            )
        }
    }
}
