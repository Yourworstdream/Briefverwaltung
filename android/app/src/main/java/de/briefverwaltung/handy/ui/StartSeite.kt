package de.briefverwaltung.handy.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import de.briefverwaltung.handy.HandyViewModel
import de.briefverwaltung.handy.Scan
import de.briefverwaltung.handy.Seite
import de.briefverwaltung.handy.Status
import java.text.DateFormat
import java.util.Date

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StartSeite(vm: HandyViewModel, scannen: () -> Unit, galerie: () -> Unit) {
    val snackbar = remember { SnackbarHostState() }
    MeldungenAnzeigen(vm, snackbar)
    val offen = vm.scans.filter { it.status != Status.GESENDET }
    val gesendet = vm.scans.filter { it.status == Status.GESENDET }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Briefverwaltung") },
                actions = {
                    IconButton(onClick = { vm.seite = Seite.Verbinden }) {
                        Icon(Icons.Default.Settings, contentDescription = "PC verbinden")
                    }
                },
            )
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = scannen,
                icon = { Icon(Icons.Default.Add, contentDescription = null) },
                text = { Text("Brief scannen") },
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { innen ->
        LazyColumn(
            contentPadding = PaddingValues(
                start = 16.dp, end = 16.dp,
                top = innen.calculateTopPadding() + 8.dp,
                bottom = innen.calculateBottomPadding() + 96.dp,
            ),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            item { VerbindungsKarte(vm) }
            vm.arbeitet?.let { text -> item { ArbeitetKarte(text) } }
            item {
                OutlinedButton(onClick = galerie, modifier = Modifier.fillMaxWidth()) {
                    Text("Fotos aus der Galerie nehmen")
                }
            }
            if (offen.isNotEmpty()) {
                item {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("Noch nicht am PC", style = MaterialTheme.typography.titleMedium,
                            modifier = Modifier.weight(1f))
                        TextButton(onClick = { vm.alleSenden() }) {
                            Icon(Icons.Default.Refresh, contentDescription = null)
                            Spacer(Modifier.width(4.dp))
                            Text("Alle senden")
                        }
                    }
                }
                items(offen, key = { it.id }) { scan -> ScanZeile(vm, scan) }
            }
            if (gesendet.isNotEmpty()) {
                item { Text("Gesendet", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 8.dp)) }
                items(gesendet, key = { it.id }) { scan -> ScanZeile(vm, scan) }
            }
            if (vm.scans.isEmpty() && vm.arbeitet == null) {
                item { LeerHinweis() }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun VerbindungsKarte(vm: HandyViewModel) {
    val v = vm.verbindung
    Card(
        onClick = { vm.seite = Seite.Verbinden },
        colors = CardDefaults.cardColors(
            containerColor = if (v == null) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.primaryContainer,
        ),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(if (v == null) Icons.Default.Warning else Icons.Default.CheckCircle, contentDescription = null)
            Spacer(Modifier.width(12.dp))
            Column {
                Text(if (v == null) "Noch kein PC verbunden" else "PC: ${v.name}", fontWeight = FontWeight.Bold)
                Text(
                    if (v == null) "Antippen und den QR-Code im PC-Programm scannen (Datei → Handy verbinden)."
                    else vm.verbindungsStatus.ifBlank { "Briefe werden an ${v.adressen.first()} geschickt." },
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}

@Composable
private fun ArbeitetKarte(text: String) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            CircularProgressIndicator(modifier = Modifier.size(24.dp), strokeWidth = 3.dp)
            Spacer(Modifier.width(16.dp))
            Text(text)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ScanZeile(vm: HandyViewModel, scan: Scan) {
    Card(onClick = { vm.seite = Seite.Pruefen(scan.id) }, modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Foto(vm.vorschauDatei(scan), 56.dp)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(scan.daten.titel.ifBlank { "(ohne Betreff)" }, fontWeight = FontWeight.Bold, maxLines = 2,
                    overflow = TextOverflow.Ellipsis)
                val datum = DateFormat.getDateInstance(DateFormat.MEDIUM).format(Date(scan.erstellt))
                Text("$datum · ${scan.seiten.size} ${if (scan.seiten.size == 1) "Seite" else "Seiten"}",
                    style = MaterialTheme.typography.bodySmall)
                val statusText = when (scan.status) {
                    Status.ENTWURF -> "Noch nicht geprüft"
                    Status.WARTET -> scan.meldung.ifBlank { "Wartet auf den PC" }
                    Status.FEHLER -> scan.meldung.ifBlank { "Senden fehlgeschlagen" }
                    Status.GESENDET -> scan.meldung.ifBlank { "Am PC gespeichert" }
                }
                Text(
                    statusText,
                    style = MaterialTheme.typography.bodySmall,
                    color = if (scan.status == Status.FEHLER) MaterialTheme.colorScheme.error
                    else MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2, overflow = TextOverflow.Ellipsis,
                )
            }
            Spacer(Modifier.width(8.dp))
            DringlichkeitText(scan.daten.dringlichkeit)
        }
    }
}

@Composable
private fun LeerHinweis() {
    Column(Modifier.fillMaxWidth().padding(vertical = 32.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text("Noch keine Briefe", style = MaterialTheme.typography.titleLarge)
        Spacer(Modifier.height(8.dp))
        Text(
            "Tippe auf „Brief scannen“. Die App findet die Ränder des Blattes, liest den Text " +
                    "und erkennt Absender, Frist, Betrag und IBAN. Danach prüfst du alles kurz und schickst " +
                    "den Brief an den PC.",
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}
