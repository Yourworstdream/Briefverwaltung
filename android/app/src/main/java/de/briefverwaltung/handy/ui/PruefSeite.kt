package de.briefverwaltung.handy.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.clickable
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import de.briefverwaltung.analyse.ARTEN
import de.briefverwaltung.analyse.Analyse
import de.briefverwaltung.analyse.Iban
import de.briefverwaltung.analyse.datumLesen
import de.briefverwaltung.handy.Briefdaten
import de.briefverwaltung.handy.DRINGLICHKEIT
import de.briefverwaltung.handy.Feld
import de.briefverwaltung.handy.Felder
import de.briefverwaltung.handy.HandyViewModel
import de.briefverwaltung.handy.Seite
import de.briefverwaltung.handy.Status
import de.briefverwaltung.handy.Tastatur

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun PruefSeite(vm: HandyViewModel, id: String) {
    val scan = vm.scan(id)
    if (scan == null) {
        LaunchedEffect(id) { vm.seite = Seite.Start }
        return
    }
    val snackbar = remember { SnackbarHostState() }
    MeldungenAnzeigen(vm, snackbar)
    val gesendet = scan.status == Status.GESENDET
    var daten by remember(id) { mutableStateOf(scan.daten) }
    var loeschenFragen by remember { mutableStateOf(false) }
    var textZeigen by rememberSaveable { mutableStateOf(false) }
    val dunkel = isSystemInDarkTheme()

    fun aendern(neu: Briefdaten) {
        daten = neu
        vm.aendern(id, neu)
    }

    BackHandler { vm.seite = Seite.Start }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(if (gesendet) "Gesendeter Brief" else "Brief prüfen") },
                navigationIcon = {
                    IconButton(onClick = { vm.seite = Seite.Start }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Zurück")
                    }
                },
                actions = {
                    IconButton(onClick = { loeschenFragen = true }) {
                        Icon(Icons.Default.Delete, contentDescription = "Löschen")
                    }
                },
            )
        },
        bottomBar = {
            if (!gesendet) {
                Surface(shadowElevation = 8.dp) {
                    Row(Modifier.fillMaxWidth().padding(16.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        OutlinedButton(onClick = { vm.spaeterSenden(id) }, modifier = Modifier.weight(1f)) {
                            Text("Später senden")
                        }
                        Button(onClick = { vm.senden(id) }, modifier = Modifier.weight(1f)) {
                            Icon(Icons.AutoMirrored.Filled.Send, contentDescription = null)
                            Spacer(Modifier.width(8.dp))
                            Text("An PC senden")
                        }
                    }
                }
            }
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { innen ->
        Column(
            Modifier
                .padding(innen)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            // Seiten
            val vorhandene = scan.seiten.indices.filter { vm.fotoDatei(scan, it).exists() }
            if (vorhandene.isNotEmpty()) {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    itemsIndexed(vorhandene) { _, index ->
                        Foto(vm.fotoDatei(scan, index), 120.dp,
                            Modifier.clickable { vm.seite = Seite.Bild(id, index) })
                    }
                }
            } else {
                Foto(vm.vorschauDatei(scan), 120.dp)
            }

            // Was erkannt wurde
            Card(
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("Erkannt", style = MaterialTheme.typography.labelLarge)
                    Text(scan.zusammenfassung, fontWeight = FontWeight.Bold)
                    scan.gruende.forEach { Text("• $it", style = MaterialTheme.typography.bodySmall) }
                    if (scan.meldung.isNotBlank() && scan.status != Status.ENTWURF) {
                        Text(
                            scan.meldung,
                            style = MaterialTheme.typography.bodySmall,
                            color = if (scan.status == Status.FEHLER) MaterialTheme.colorScheme.error else Color.Unspecified,
                        )
                    }
                    if (!gesendet) {
                        Text("Bitte kurz prüfen und bei Bedarf korrigieren.", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }

            Ueberschrift("Dringlichkeit")
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for ((stufe, name) in DRINGLICHKEIT) {
                    val farbe = dringlichkeitFarbe(stufe, dunkel)
                    FilterChip(
                        selected = daten.dringlichkeit == stufe,
                        onClick = { aendern(daten.copy(dringlichkeit = stufe)) },
                        enabled = !gesendet,
                        label = { Text(name) },
                        colors = FilterChipDefaults.filterChipColors(
                            selectedContainerColor = farbe,
                            selectedLabelColor = Color.White,
                            labelColor = farbe,
                        ),
                    )
                }
            }

            Ueberschrift("Art")
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for (art in ARTEN) {
                    FilterChip(
                        selected = daten.art == art,
                        onClick = { aendern(daten.copy(art = art)) },
                        enabled = !gesendet,
                        label = { Text(art) },
                    )
                }
            }

            Ueberschrift("Brief")
            for (feld in Felder.brief) {
                val wert = daten[feld.schluessel]
                val hinweis = when (feld.schluessel) {
                    "frist" -> datumLesen(wert)?.let { Analyse.fristText(it) }
                        ?: if (wert.isNotBlank()) "Bitte als TT.MM.JJJJ eingeben" else null
                    "briefdatum" -> if (wert.isNotBlank() && datumLesen(wert) == null) "Bitte als TT.MM.JJJJ eingeben" else null
                    else -> null
                }
                val fehler = feld.tastatur == Tastatur.DATUM && wert.isNotBlank() && datumLesen(wert) == null
                Eingabe(feld, wert, !gesendet, hinweis, fehler) { aendern(daten.mit(feld.schluessel, it)) }
            }

            Ueberschrift("Absender – Kontaktdaten")
            for (feld in Felder.absender) {
                Eingabe(feld, daten[feld.schluessel], !gesendet) { aendern(daten.mit(feld.schluessel, it)) }
            }

            Ueberschrift("Ansprechpartner")
            for (feld in Felder.ansprechpartner) {
                Eingabe(feld, daten[feld.schluessel], !gesendet) { aendern(daten.mit(feld.schluessel, it)) }
            }

            Ueberschrift("Bankverbindung")
            for (feld in Felder.bank) {
                val wert = daten[feld.schluessel]
                val ibanFeld = feld.schluessel == "iban" && wert.isNotBlank()
                val ibanOk = ibanFeld && Iban.gueltig(wert)
                Eingabe(
                    feld, wert, !gesendet,
                    hinweis = if (!ibanFeld) null else if (ibanOk) "✓ IBAN ist gültig" else "Prüfziffer stimmt nicht – bitte vergleichen",
                    fehler = ibanFeld && !ibanOk,
                ) { aendern(daten.mit(feld.schluessel, it)) }
            }

            TextButton(onClick = { textZeigen = !textZeigen }) {
                Text(if (textZeigen) "Erkannten Text ausblenden" else "Erkannten Text anzeigen")
            }
            if (textZeigen) {
                Card(modifier = Modifier.fillMaxWidth()) {
                    SelectionContainer {
                        Text(scan.text.ifBlank { "(kein Text erkannt)" }, modifier = Modifier.padding(12.dp),
                            style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            Spacer(Modifier.height(24.dp))
        }
    }

    if (loeschenFragen) {
        AlertDialog(
            onDismissRequest = { loeschenFragen = false },
            title = { Text("Brief löschen?") },
            text = {
                Text(if (gesendet) "Der Brief wird nur auf dem Handy gelöscht – am PC bleibt er erhalten."
                else "Die Fotos und Angaben werden vom Handy gelöscht. Der Brief ist noch nicht am PC!")
            },
            confirmButton = {
                TextButton(onClick = { loeschenFragen = false; vm.loeschen(id) }) { Text("Löschen") }
            },
            dismissButton = {
                TextButton(onClick = { loeschenFragen = false }) { Text("Abbrechen") }
            },
        )
    }
}

@Composable
private fun Ueberschrift(text: String) {
    Text(text, style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 8.dp))
}

@Composable
private fun Eingabe(
    feld: Feld,
    wert: String,
    aktiv: Boolean,
    hinweis: String? = null,
    fehler: Boolean = false,
    aendern: (String) -> Unit,
) {
    val tastatur = when (feld.tastatur) {
        Tastatur.ZAHL -> KeyboardOptions(keyboardType = KeyboardType.Decimal)
        Tastatur.TELEFON -> KeyboardOptions(keyboardType = KeyboardType.Phone)
        Tastatur.EMAIL -> KeyboardOptions(keyboardType = KeyboardType.Email)
        Tastatur.DATUM -> KeyboardOptions(keyboardType = KeyboardType.Text)
        Tastatur.NAME -> KeyboardOptions(capitalization = KeyboardCapitalization.Words)
        Tastatur.TEXT -> KeyboardOptions(capitalization = KeyboardCapitalization.Sentences)
    }
    OutlinedTextField(
        value = wert,
        onValueChange = aendern,
        label = { Text(feld.bezeichnung) },
        enabled = aktiv,
        singleLine = !feld.mehrzeilig,
        minLines = if (feld.mehrzeilig) 3 else 1,
        isError = fehler,
        supportingText = if (hinweis != null) {
            { Text(hinweis) }
        } else null,
        keyboardOptions = tastatur,
        modifier = Modifier.fillMaxWidth(),
    )
}
