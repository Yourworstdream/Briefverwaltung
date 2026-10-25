package de.briefverwaltung.handy

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID

/** Wohin die Briefe gehen: Adresse(n) des PCs im WLAN und der Zugangscode aus dem PC-Programm. */
data class PcVerbindung(val name: String, val token: String, val adressen: List<String>) {
    fun speichern(context: Context) {
        context.getSharedPreferences("verbindung", Context.MODE_PRIVATE).edit()
            .putString("name", name)
            .putString("token", token)
            .putString("adressen", adressen.joinToString("\n"))
            .apply()
    }

    companion object {
        fun laden(context: Context): PcVerbindung? {
            val p = context.getSharedPreferences("verbindung", Context.MODE_PRIVATE)
            val token = p.getString("token", null) ?: return null
            val adressen = (p.getString("adressen", "") ?: "").lines().filter { it.isNotBlank() }
            if (adressen.isEmpty()) return null
            return PcVerbindung(p.getString("name", "PC") ?: "PC", token, adressen)
        }

        /** Inhalt des QR-Codes aus „Handy verbinden …“ im PC-Programm. */
        fun ausQr(text: String): PcVerbindung? {
            val j = runCatching { JSONObject(text) }.getOrNull() ?: return null
            if (j.optString("app") != "briefverwaltung") return null
            val liste = j.optJSONArray("adressen") ?: return null
            val adressen = (0 until liste.length()).map { liste.optString(it) }.filter { it.startsWith("http") }
            val token = j.optString("token")
            if (adressen.isEmpty() || token.isBlank()) return null
            return PcVerbindung(j.optString("name", "PC"), token, adressen)
        }

        /** Von Hand eingetippt: „192.168.178.23“ wird zu „http://192.168.178.23:8765“. */
        fun vonHand(adresse: String, code: String): PcVerbindung? {
            var a = adresse.trim().trimEnd('/')
            if (a.isEmpty() || code.isBlank()) return null
            if (!a.startsWith("http://") && !a.startsWith("https://")) a = "http://$a"
            if (!Regex(""":\d+$""").containsMatchIn(a)) a += ":8765"
            return PcVerbindung("PC", code.trim().uppercase(), listOf(a))
        }
    }
}

class PcFehler(meldung: String) : IOException(meldung)

data class PcAntwort(val briefId: Int, val neu: Boolean, val meldung: String)

/** Spricht mit dem Handy-Empfang des PC-Programms (siehe briefe_app/empfang.py). */
object PcClient {
    private fun oeffnen(url: String, token: String, lesenMs: Int): HttpURLConnection =
        (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = 4000
            readTimeout = lesenMs
            setRequestProperty("X-Briefe-Token", token)
            setRequestProperty("Accept", "application/json")
        }

    private fun antwort(verbindung: HttpURLConnection): Pair<Int, JSONObject> {
        val code = verbindung.responseCode
        val strom = if (code in 200..299) verbindung.inputStream else verbindung.errorStream
        val text = strom?.bufferedReader()?.use { it.readText() } ?: ""
        return code to (runCatching { JSONObject(text) }.getOrNull() ?: JSONObject())
    }

    /** Findet die Adresse, unter der der PC antwortet. Sie steht danach vorne in der Liste. */
    suspend fun testen(v: PcVerbindung): PcVerbindung = withContext(Dispatchers.IO) {
        var letzterFehler = "Der PC antwortet nicht."
        for (adresse in v.adressen) {
            try {
                val verbindung = oeffnen("$adresse/api/info", v.token, 4000)
                val (code, json) = antwort(verbindung)
                verbindung.disconnect()
                when (code) {
                    200 -> return@withContext v.copy(
                        name = json.optString("name", v.name),
                        adressen = listOf(adresse) + (v.adressen - adresse),
                    )
                    401 -> throw PcFehler("Der Code stimmt nicht. Bitte den QR-Code im PC-Programm neu scannen.")
                    else -> letzterFehler = "Der PC meldet Fehler $code."
                }
            } catch (fehler: PcFehler) {
                throw fehler
            } catch (fehler: Exception) {
                letzterFehler = "Der PC ist nicht erreichbar. Läuft das Programm und ist das Handy im selben WLAN?"
            }
        }
        throw PcFehler(letzterFehler)
    }

    /** Schickt einen Brief: Teil „daten“ (JSON) und die Fotos als „seite1“, „seite2“ … */
    suspend fun senden(v: PcVerbindung, daten: JSONObject, fotos: List<File>): PcAntwort = withContext(Dispatchers.IO) {
        val adresse = v.adressen.first()
        val grenze = "----briefe" + UUID.randomUUID().toString().replace("-", "")
        val zeilenende = "\r\n".toByteArray()
        val datenTeil = ("--$grenze\r\nContent-Disposition: form-data; name=\"daten\"\r\n" +
                "Content-Type: application/json; charset=utf-8\r\n\r\n").toByteArray() +
                daten.toString().toByteArray(Charsets.UTF_8) + zeilenende
        val koepfe = fotos.mapIndexed { i, _ ->
            ("--$grenze\r\nContent-Disposition: form-data; name=\"seite${i + 1}\"; filename=\"seite${i + 1}.jpg\"\r\n" +
                    "Content-Type: image/jpeg\r\n\r\n").toByteArray()
        }
        val ende = "--$grenze--\r\n".toByteArray()
        val laenge: Long = datenTeil.size.toLong() + koepfe.sumOf { it.size.toLong() } +
                fotos.sumOf { it.length() } + fotos.size.toLong() * zeilenende.size + ende.size

        val verbindung = oeffnen("$adresse/api/briefe", v.token, 120_000)
        try {
            verbindung.requestMethod = "POST"
            verbindung.doOutput = true
            verbindung.setFixedLengthStreamingMode(laenge)
            verbindung.setRequestProperty("Content-Type", "multipart/form-data; boundary=$grenze")
            verbindung.outputStream.use { aus ->
                aus.write(datenTeil)
                fotos.forEachIndexed { i, foto ->
                    aus.write(koepfe[i])
                    foto.inputStream().use { it.copyTo(aus) }
                    aus.write(zeilenende)
                }
                aus.write(ende)
            }
            val (code, json) = antwort(verbindung)
            if (code != 200 || !json.optBoolean("ok")) {
                throw PcFehler(json.optString("meldung").ifBlank { "Der PC meldet Fehler $code." })
            }
            PcAntwort(json.optInt("brief_id"), json.optBoolean("neu"), json.optString("meldung"))
        } finally {
            verbindung.disconnect()
        }
    }
}
