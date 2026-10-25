package de.briefverwaltung.handy.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.rememberTransformableState
import androidx.compose.foundation.gestures.transformable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.KeyboardArrowLeft
import androidx.compose.material.icons.filled.KeyboardArrowRight
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import de.briefverwaltung.handy.Bilder
import de.briefverwaltung.handy.HandyViewModel
import de.briefverwaltung.handy.Seite
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Eine Seite groß ansehen – mit zwei Fingern zoomen und verschieben. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BildSeite(vm: HandyViewModel, id: String, index: Int) {
    val scan = vm.scan(id)
    if (scan == null || index !in scan.seiten.indices) {
        LaunchedEffect(id) { vm.seite = Seite.Start }
        return
    }
    BackHandler { vm.seite = Seite.Pruefen(id) }
    val datei = vm.fotoDatei(scan, index)
    val bild by produceState<ImageBitmap?>(null, datei.path) {
        value = withContext(Dispatchers.IO) { Bilder.laden(datei, 2200)?.asImageBitmap() }
    }
    var skala by remember(index) { mutableFloatStateOf(1f) }
    var verschiebung by remember(index) { mutableStateOf(Offset.Zero) }
    val gesten = rememberTransformableState { zoom, schieben, _ ->
        skala = (skala * zoom).coerceIn(1f, 6f)
        verschiebung = if (skala == 1f) Offset.Zero else verschiebung + schieben
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Seite ${index + 1} von ${scan.seiten.size}") },
                navigationIcon = {
                    IconButton(onClick = { vm.seite = Seite.Pruefen(id) }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Zurück")
                    }
                },
                actions = {
                    IconButton(onClick = { vm.seite = Seite.Bild(id, index - 1) }, enabled = index > 0) {
                        Icon(Icons.Default.KeyboardArrowLeft, contentDescription = "Vorige Seite")
                    }
                    IconButton(onClick = { vm.seite = Seite.Bild(id, index + 1) }, enabled = index < scan.seiten.size - 1) {
                        Icon(Icons.Default.KeyboardArrowRight, contentDescription = "Nächste Seite")
                    }
                },
            )
        },
    ) { innen ->
        Box(
            Modifier
                .padding(innen)
                .fillMaxSize()
                .background(Color(0xFF2B2F36))
                .transformable(gesten),
            contentAlignment = Alignment.Center,
        ) {
            val geladen = bild
            if (geladen == null) {
                CircularProgressIndicator()
            } else {
                Image(
                    geladen,
                    contentDescription = "Seite ${index + 1}",
                    contentScale = ContentScale.Fit,
                    modifier = Modifier
                        .fillMaxSize()
                        .graphicsLayer(
                            scaleX = skala, scaleY = skala,
                            translationX = verschiebung.x, translationY = verschiebung.y,
                        ),
                )
            }
        }
    }
}
