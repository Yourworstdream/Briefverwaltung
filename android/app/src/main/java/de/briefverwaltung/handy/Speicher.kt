package de.briefverwaltung.handy

import android.content.ContentResolver
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageDecoder
import android.graphics.Matrix
import android.media.ExifInterface
import android.net.Uri
import android.os.Build
import org.json.JSONObject
import java.io.File
import java.io.IOException

/** Speichert die Scans im privaten Speicher der App: scans/<id>/scan.json, seite1.jpg, … und vorschau.jpg */
class Speicher(context: Context) {
    private val wurzel = File(context.filesDir, "scans").apply { mkdirs() }

    fun ordner(id: String) = File(wurzel, id)

    fun seite(scan: Scan, name: String) = File(ordner(scan.id), name)

    fun vorschau(scan: Scan) = File(ordner(scan.id), "vorschau.jpg")

    fun alle(): List<Scan> =
        (wurzel.listFiles() ?: emptyArray()).mapNotNull { laden(it.name) }.sortedByDescending { it.erstellt }

    fun laden(id: String): Scan? = runCatching {
        Scan.ausJson(JSONObject(File(ordner(id), "scan.json").readText()))
    }.getOrNull()

    fun speichern(scan: Scan) {
        val ordner = ordner(scan.id).apply { mkdirs() }
        val tmp = File(ordner, "scan.json.tmp")
        tmp.writeText(scan.json().toString())
        if (!tmp.renameTo(File(ordner, "scan.json"))) {
            File(ordner, "scan.json").writeText(scan.json().toString())
            tmp.delete()
        }
    }

    fun loeschen(id: String) {
        ordner(id).deleteRecursively()
    }

    /** Nach dem erfolgreichen Senden: große Fotos löschen, nur das kleine Vorschaubild bleibt. */
    fun fotosLoeschen(scan: Scan) {
        scan.seiten.forEach { seite(scan, it).delete() }
    }

    /** Übernimmt Fotos (vom Scanner, aus der Galerie oder geteilt) in einen neuen Scan-Ordner. */
    fun uebernehmen(id: String, quellen: List<Uri>, resolver: ContentResolver): List<String> {
        val ordner = ordner(id).apply { mkdirs() }
        val namen = mutableListOf<String>()
        for (uri in quellen) {
            val name = "seite${namen.size + 1}.jpg"
            val ziel = File(ordner, name)
            try {
                val typ = resolver.getType(uri) ?: ""
                if (typ == "image/jpeg" || typ.isEmpty() || uri.scheme == "file") {
                    resolver.openInputStream(uri)?.use { ein -> ziel.outputStream().use { ein.copyTo(it) } }
                        ?: continue
                } else {
                    // PNG, HEIC usw. als JPEG speichern – das kann jeder PC anzeigen
                    val bild = Bilder.ausUri(resolver, uri, 3000) ?: continue
                    ziel.outputStream().use { bild.compress(Bitmap.CompressFormat.JPEG, 90, it) }
                }
                if (ziel.length() > 0) namen += name else ziel.delete()
            } catch (fehler: Exception) {
                ziel.delete()
            }
        }
        if (namen.isEmpty()) {
            ordner.deleteRecursively()
            throw IOException("Die Fotos konnten nicht gelesen werden.")
        }
        Bilder.laden(File(ordner, namen.first()), 360)?.let { klein ->
            File(ordner, "vorschau.jpg").outputStream().use { klein.compress(Bitmap.CompressFormat.JPEG, 80, it) }
        }
        return namen
    }
}

object Bilder {
    /** Lädt ein Foto verkleinert (längste Seite etwa maxPixel) und richtig gedreht. */
    fun laden(datei: File, maxPixel: Int): Bitmap? {
        if (!datei.exists()) return null
        val groesse = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(datei.path, groesse)
        if (groesse.outWidth <= 0 || groesse.outHeight <= 0) return null
        var stufe = 1
        while (maxOf(groesse.outWidth, groesse.outHeight) / (stufe * 2) >= maxPixel) stufe *= 2
        val bild = BitmapFactory.decodeFile(datei.path, BitmapFactory.Options().apply { inSampleSize = stufe })
            ?: return null
        return drehen(bild, drehungAusExif(datei))
    }

    fun ausUri(resolver: ContentResolver, uri: Uri, maxPixel: Int): Bitmap? = runCatching {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            ImageDecoder.decodeBitmap(ImageDecoder.createSource(resolver, uri)) { decoder, info, _ ->
                val laengste = maxOf(info.size.width, info.size.height)
                if (laengste > maxPixel) decoder.setTargetSampleSize((laengste / maxPixel).coerceAtLeast(1))
                decoder.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
            }
        } else {
            resolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it) }
        }
    }.getOrNull()

    private fun drehungAusExif(datei: File): Int = runCatching {
        when (ExifInterface(datei.path).getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)) {
            ExifInterface.ORIENTATION_ROTATE_90 -> 90
            ExifInterface.ORIENTATION_ROTATE_180 -> 180
            ExifInterface.ORIENTATION_ROTATE_270 -> 270
            else -> 0
        }
    }.getOrDefault(0)

    private fun drehen(bild: Bitmap, grad: Int): Bitmap {
        if (grad == 0) return bild
        val matrix = Matrix().apply { postRotate(grad.toFloat()) }
        return Bitmap.createBitmap(bild, 0, 0, bild.width, bild.height, matrix, true)
    }
}
