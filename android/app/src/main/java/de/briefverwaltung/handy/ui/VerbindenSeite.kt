package de.briefverwaltung.handy.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import de.briefverwaltung.handy.HandyViewModel
import de.briefverwaltung.handy.PcVerbindung
import de.briefverwaltung.handy.Seite

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VerbindenSeite(vm: HandyViewModel, qrScannen: () -> Unit) {
    val snackbar = remember { SnackbarHostState() }
    MeldungenAnzeigen(vm, snackbar)
    val v = vm.verbindung
    var adresse by remember(v) { mutableStateOf(v?.adressen?.firstOrNull() ?: "") }
    var code by remember(v) { mutableStateOf(v?.token ?: "") }
    BackHandler { vm.seite = Seite.Start }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("PC verbinden") },
                navigationIcon = {
                    IconButton(onClick = { vm.seite = Seite.Start }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Zurück")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { innen ->
        Column(
            Modifier
                .padding(innen)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("So geht's", style = MaterialTheme.typography.titleMedium)
            Text(
                "1. Am PC die Briefverwaltung starten.\n" +
                        "2. Dort Datei → Handy verbinden … öffnen.\n" +
                        "3. Hier auf „QR-Code scannen“ tippen und den Code auf dem Bildschirm scannen.\n\n" +
                        "Handy und PC müssen im selben WLAN sein. Ist der PC aus, warten die Briefe auf dem Handy " +
                        "und werden später geschickt.",
            )
            Button(onClick = qrScannen, modifier = Modifier.fillMaxWidth()) {
                Icon(Icons.Default.Search, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("QR-Code am PC scannen")
            }

            if (v != null) {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("Verbunden mit „${v.name}“", fontWeight = FontWeight.Bold)
                        v.adressen.forEach { Text(it, style = MaterialTheme.typography.bodySmall) }
                        if (vm.verbindungsStatus.isNotBlank()) Text(vm.verbindungsStatus)
                        OutlinedButton(onClick = { vm.testen() }) {
                            Icon(Icons.Default.Refresh, contentDescription = null)
                            Spacer(Modifier.width(8.dp))
                            Text("Verbindung testen")
                        }
                    }
                }
            }

            Spacer(Modifier.height(8.dp))
            Text("Oder von Hand eintragen", style = MaterialTheme.typography.titleMedium)
            Text("Adresse und Code stehen im PC-Programm unter Datei → Handy verbinden …",
                style = MaterialTheme.typography.bodySmall)
            OutlinedTextField(
                value = adresse,
                onValueChange = { adresse = it },
                label = { Text("Adresse des PCs, z. B. 192.168.178.23") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = code,
                onValueChange = { code = it },
                label = { Text("Code, z. B. K7PX-M3QD-9TWB") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Characters),
                modifier = Modifier.fillMaxWidth(),
            )
            Button(
                onClick = {
                    val neu = PcVerbindung.vonHand(adresse, code)
                    if (neu == null) vm.meldung = "Bitte Adresse und Code eintragen."
                    else vm.verbindungSetzen(neu.copy(name = v?.name ?: "PC"))
                },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Speichern und testen") }
        }
    }
}
