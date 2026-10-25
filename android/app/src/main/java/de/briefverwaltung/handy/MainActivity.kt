package de.briefverwaltung.handy

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.IntentSenderRequest
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.runtime.Composable
import androidx.core.content.IntentCompat
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
import com.google.mlkit.vision.documentscanner.GmsDocumentScannerOptions
import com.google.mlkit.vision.documentscanner.GmsDocumentScanning
import com.google.mlkit.vision.documentscanner.GmsDocumentScanningResult
import de.briefverwaltung.handy.ui.BildSeite
import de.briefverwaltung.handy.ui.BriefTheme
import de.briefverwaltung.handy.ui.PruefSeite
import de.briefverwaltung.handy.ui.StartSeite
import de.briefverwaltung.handy.ui.VerbindenSeite

class MainActivity : ComponentActivity() {
    private val vm: HandyViewModel by viewModels()
    private lateinit var scanner: ActivityResultLauncher<IntentSenderRequest>
    private lateinit var galerie: ActivityResultLauncher<PickVisualMediaRequest>

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        scanner = registerForActivityResult(ActivityResultContracts.StartIntentSenderForResult()) { ergebnis ->
            if (ergebnis.resultCode == RESULT_OK) {
                val scan = GmsDocumentScanningResult.fromActivityResultIntent(ergebnis.data)
                vm.fotosUebernehmen(scan?.pages?.map { it.imageUri } ?: emptyList())
            }
        }
        galerie = registerForActivityResult(ActivityResultContracts.PickMultipleVisualMedia(20)) { uris ->
            vm.fotosUebernehmen(uris)
        }
        if (savedInstanceState == null) geteilteFotos(intent)

        setContent {
            BriefTheme {
                Oberflaeche(vm, ::scannen, ::galerieOeffnen, ::qrScannen)
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        geteilteFotos(intent)
    }

    override fun onResume() {
        super.onResume()
        vm.alleSenden(still = true)          // Wartende Briefe schicken, sobald der PC erreichbar ist
    }

    /** Googles Dokumentscanner: findet die Blattränder, schneidet zu, mehrere Seiten möglich. */
    private fun scannen() {
        val optionen = GmsDocumentScannerOptions.Builder()
            .setGalleryImportAllowed(true)
            .setPageLimit(20)
            .setResultFormats(GmsDocumentScannerOptions.RESULT_FORMAT_JPEG)
            .setScannerMode(GmsDocumentScannerOptions.SCANNER_MODE_FULL)
            .build()
        GmsDocumentScanning.getClient(optionen).getStartScanIntent(this)
            .addOnSuccessListener { start -> scanner.launch(IntentSenderRequest.Builder(start).build()) }
            .addOnFailureListener {
                vm.meldung = "Der Scanner ist auf diesem Handy nicht verfügbar – nimm die Fotos aus der Galerie."
                galerieOeffnen()
            }
    }

    private fun galerieOeffnen() {
        galerie.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
    }

    private fun qrScannen() {
        val optionen = GmsBarcodeScannerOptions.Builder().setBarcodeFormats(Barcode.FORMAT_QR_CODE).build()
        GmsBarcodeScanning.getClient(this, optionen).startScan()
            .addOnSuccessListener { code ->
                val verbindung = PcVerbindung.ausQr(code.rawValue ?: "")
                if (verbindung != null) vm.verbindungSetzen(verbindung)
                else vm.meldung = "Das ist nicht der QR-Code aus der Briefverwaltung."
            }
            .addOnFailureListener { vm.meldung = "Der QR-Scanner ist nicht verfügbar: ${it.message}" }
    }

    /** Fotos, die aus der Galerie oder einer anderen App mit „Teilen“ geschickt wurden. */
    private fun geteilteFotos(intent: Intent?) {
        if (intent == null) return
        val uris: List<Uri> = when (intent.action) {
            Intent.ACTION_SEND ->
                listOfNotNull(IntentCompat.getParcelableExtra(intent, Intent.EXTRA_STREAM, Uri::class.java))
            Intent.ACTION_SEND_MULTIPLE ->
                IntentCompat.getParcelableArrayListExtra(intent, Intent.EXTRA_STREAM, Uri::class.java) ?: emptyList()
            else -> emptyList()
        }
        if (uris.isNotEmpty()) vm.fotosUebernehmen(uris)
    }
}

@Composable
fun Oberflaeche(vm: HandyViewModel, scannen: () -> Unit, galerie: () -> Unit, qrScannen: () -> Unit) {
    when (val seite = vm.seite) {
        Seite.Start -> StartSeite(vm, scannen, galerie)
        is Seite.Pruefen -> PruefSeite(vm, seite.id)
        Seite.Verbinden -> VerbindenSeite(vm, qrScannen)
        is Seite.Bild -> BildSeite(vm, seite.id, seite.index)
    }
}
