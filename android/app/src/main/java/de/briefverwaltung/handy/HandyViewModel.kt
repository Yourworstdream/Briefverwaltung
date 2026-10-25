package de.briefverwaltung.handy

import android.app.Application
import android.net.Uri
import android.os.Build
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import de.briefverwaltung.analyse.Analyse
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.time.LocalDate
import java.util.UUID

/** Welche Seite der App gerade zu sehen ist. */
sealed interface Seite {
    data object Start : Seite
    data class Pruefen(val id: String) : Seite
    data object Verbinden : Seite
    data class Bild(val id: String, val index: Int) : Seite
}

class HandyViewModel(app: Application) : AndroidViewModel(app) {
    private val speicher = Speicher(app)
    private val erkennung = Texterkennung(app)
    private val inArbeit = mutableSetOf<String>()

    var scans by mutableStateOf<List<Scan>>(emptyList())
        private set
    var verbindung by mutableStateOf(PcVerbindung.laden(app))
        private set
    var seite by mutableStateOf<Seite>(Seite.Start)
    var arbeitet by mutableStateOf<String?>(null)
        private set
    var meldung by mutableStateOf<String?>(null)
    var verbindungsStatus by mutableStateOf("")
        private set

    init {
        scans = speicher.alle()
    }

    fun scan(id: String): Scan? = scans.firstOrNull { it.id == id }

    fun fotoDatei(scan: Scan, index: Int) = speicher.seite(scan, scan.seiten[index])

    fun vorschauDatei(scan: Scan) = speicher.vorschau(scan)

    private fun aktualisieren(scan: Scan) {
        scans = (listOf(scan) + scans.filter { it.id != scan.id }).sortedByDescending { it.erstellt }
        viewModelScope.launch(Dispatchers.IO) { speicher.speichern(scan) }
    }

    // ------------------------------------------------------------ Neuer Brief

    /** Fotos vom Scanner, aus der Galerie oder geteilt: Text erkennen, analysieren, zum Prüfen öffnen. */
    fun fotosUebernehmen(uris: List<Uri>) {
        if (uris.isEmpty()) return
        viewModelScope.launch {
            arbeitet = "Fotos werden übernommen …"
            try {
                val id = UUID.randomUUID().toString()
                val namen = withContext(Dispatchers.IO) {
                    speicher.uebernehmen(id, uris, getApplication<Application>().contentResolver)
                }
                arbeitet = "Text wird erkannt und ausgewertet …"
                val dateien = namen.map { java.io.File(speicher.ordner(id), it) }
                val text = try {
                    erkennung.lesen(dateien)
                } catch (fehler: Exception) {
                    meldung = "Die Texterkennung hat nicht geklappt: ${fehler.message}"
                    ""
                }
                val heute = LocalDate.now()
                val ergebnis = withContext(Dispatchers.Default) { Analyse.analysieren(text, heute) }
                val scan = Scan(
                    id = id,
                    erstellt = System.currentTimeMillis(),
                    seiten = namen,
                    text = text,
                    daten = Briefdaten.aus(ergebnis),
                    status = Status.ENTWURF,
                    zusammenfassung = if (text.isBlank()) "Auf den Fotos wurde kein Text erkannt – bitte die Angaben selbst eintragen."
                    else Analyse.zusammenfassung(ergebnis, heute),
                    gruende = ergebnis.gruende,
                )
                aktualisieren(scan)
                seite = Seite.Pruefen(id)
            } catch (fehler: Exception) {
                meldung = fehler.message ?: "Die Fotos konnten nicht übernommen werden."
            } finally {
                arbeitet = null
            }
        }
    }

    fun aendern(id: String, daten: Briefdaten) {
        val scan = scan(id) ?: return
        if (scan.status == Status.GESENDET) return
        aktualisieren(scan.copy(daten = daten))
    }

    fun loeschen(id: String) {
        scans = scans.filter { it.id != id }
        viewModelScope.launch(Dispatchers.IO) { speicher.loeschen(id) }
        seite = Seite.Start
    }

    // ------------------------------------------------------------ Senden

    fun spaeterSenden(id: String) {
        scan(id)?.let { aktualisieren(it.copy(status = Status.WARTET, meldung = "Wartet auf den PC.")) }
        seite = Seite.Start
    }

    fun senden(id: String) {
        val scan = scan(id) ?: return
        aktualisieren(scan.copy(status = Status.WARTET))
        seite = Seite.Start
        viewModelScope.launch { uebertragen(id, still = false) }
    }

    /** Schickt alles, was noch nicht beim PC ist. still = keine Meldung, wenn der PC nicht erreichbar ist. */
    fun alleSenden(still: Boolean = false) {
        val offen = scans.filter { it.status == Status.WARTET || it.status == Status.FEHLER }
        if (offen.isEmpty() || verbindung == null) {
            if (!still && verbindung == null) meldung = "Bitte zuerst den PC verbinden (Zahnrad oben rechts)."
            return
        }
        viewModelScope.launch {
            for (scan in offen) {
                if (!uebertragen(scan.id, still)) break      // PC nicht erreichbar: später weiter
            }
        }
    }

    private suspend fun uebertragen(id: String, still: Boolean): Boolean {
        val v = verbindung
        if (v == null) {
            if (!still) meldung = "Noch kein PC verbunden – der Brief wartet, bis du den PC verbindest."
            return false
        }
        if (!inArbeit.add(id)) return true
        try {
            val scan = scan(id) ?: return true
            aktualisieren(scan.copy(meldung = "Wird gesendet …"))
            val erreichbar = PcClient.testen(v)
            if (erreichbar != v) {
                verbindung = erreichbar
                erreichbar.speichern(getApplication<Application>())
            }
            val daten = scan.daten.fuerPc().apply {
                put("uuid", scan.id)
                put("geraet", "${Build.MANUFACTURER} ${Build.MODEL}".trim())
                put("volltext", scan.text)
            }
            val fotos = scan.seiten.map { speicher.seite(scan, it) }.filter { it.exists() }
            val antwort = PcClient.senden(erreichbar, daten, fotos)
            val fertig = (scan(id) ?: scan).copy(status = Status.GESENDET, briefId = antwort.briefId,
                meldung = antwort.meldung.ifBlank { "Am PC als Brief Nr. ${antwort.briefId} gespeichert." })
            aktualisieren(fertig)
            withContext(Dispatchers.IO) { speicher.fotosLoeschen(fertig) }
            if (!still) meldung = "Gesendet: ${fertig.daten.titel}"
            return true
        } catch (fehler: Exception) {
            scan(id)?.let { aktualisieren(it.copy(status = Status.FEHLER, meldung = fehler.message ?: "Senden fehlgeschlagen.")) }
            if (!still) meldung = fehler.message ?: "Senden fehlgeschlagen."
            return false
        } finally {
            inArbeit.remove(id)
        }
    }

    // ------------------------------------------------------------ Verbindung

    fun verbindungSetzen(neu: PcVerbindung) {
        verbindung = neu
        neu.speichern(getApplication<Application>())
        testen(danachSenden = true)
    }

    fun testen(danachSenden: Boolean = false) {
        val v = verbindung ?: return
        viewModelScope.launch {
            verbindungsStatus = "Verbinde …"
            try {
                val erreichbar = PcClient.testen(v)
                verbindung = erreichbar
                erreichbar.speichern(getApplication<Application>())
                verbindungsStatus = "✓ Verbunden mit „${erreichbar.name}“"
                if (danachSenden) alleSenden(still = true)
            } catch (fehler: Exception) {
                verbindungsStatus = fehler.message ?: "Keine Verbindung."
            }
        }
    }
}
