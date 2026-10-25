package de.briefverwaltung.handy

import android.content.Context
import android.net.Uri
import com.google.android.gms.tasks.Task
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import kotlinx.coroutines.suspendCancellableCoroutine
import java.io.File
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/** Wartet auf das Ergebnis einer Google-Play-Aufgabe (Task), ohne die Oberfläche zu blockieren. */
suspend fun <T> Task<T>.warten(): T = suspendCancellableCoroutine { fortsetzung ->
    addOnSuccessListener { fortsetzung.resume(it) }
    addOnFailureListener { fortsetzung.resumeWithException(it) }
    addOnCanceledListener { fortsetzung.cancel() }
}

/** Texterkennung direkt auf dem Handy (Google ML Kit) – die Fotos verlassen dafür nicht das Gerät. */
class Texterkennung(private val context: Context) {
    private val erkenner by lazy { TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS) }

    suspend fun lesen(dateien: List<File>): String {
        val seiten = mutableListOf<String>()
        for (datei in dateien) {
            val bild = InputImage.fromFilePath(context, Uri.fromFile(datei))
            val text = erkenner.process(bild).warten()
            // Zeilen einzeln untereinander – so findet die Analyse Zeilenanfänge wie „Betreff:“
            seiten += text.textBlocks.joinToString("\n") { block -> block.lines.joinToString("\n") { it.text } }
        }
        return seiten.joinToString("\n\n")
    }
}
