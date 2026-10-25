package de.briefverwaltung.handy.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Email
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import de.briefverwaltung.handy.Bilder
import de.briefverwaltung.handy.DRINGLICHKEIT
import de.briefverwaltung.handy.HandyViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

/** Ein Foto verkleinert anzeigen; wird im Hintergrund geladen. */
@Composable
fun Foto(datei: File, groesse: Dp, modifier: Modifier = Modifier, maxPixel: Int = 400) {
    val bild by produceState<ImageBitmap?>(null, datei.path, datei.lastModified()) {
        value = withContext(Dispatchers.IO) { Bilder.laden(datei, maxPixel)?.asImageBitmap() }
    }
    Box(
        modifier
            .size(groesse)
            .clip(RoundedCornerShape(8))
            .background(MaterialTheme.colorScheme.surfaceVariant),
    ) {
        val geladen = bild
        if (geladen != null) {
            Image(geladen, contentDescription = null, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize())
        } else {
            Icon(Icons.Default.Email, contentDescription = null, tint = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.align(Alignment.Center))
        }
    }
}

@Composable
fun DringlichkeitText(stufe: Int, modifier: Modifier = Modifier) {
    Text(
        DRINGLICHKEIT[stufe] ?: "",
        color = dringlichkeitFarbe(stufe, isSystemInDarkTheme()),
        style = MaterialTheme.typography.labelMedium,
        fontWeight = FontWeight.Bold,
        modifier = modifier,
    )
}

/** Zeigt Meldungen des ViewModels als Snackbar unten am Bildschirm. */
@Composable
fun MeldungenAnzeigen(vm: HandyViewModel, snackbar: SnackbarHostState) {
    LaunchedEffect(vm.meldung) {
        val text = vm.meldung ?: return@LaunchedEffect
        vm.meldung = null
        snackbar.showSnackbar(text)
    }
}
