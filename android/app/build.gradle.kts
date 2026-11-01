plugins {
    id("com.android.application")
}

// Auf GitHub zählt jede Erstellung die Versionsnummer hoch, damit sich neue Versionen über die alte installieren lassen.
val laufnummer = System.getenv("GITHUB_RUN_NUMBER")?.toIntOrNull() ?: 1

android {
    namespace = "de.waslese.heute"
    compileSdk = 35

    defaultConfig {
        applicationId = "de.waslese.heute"
        minSdk = 24
        targetSdk = 34
        versionCode = laufnummer
        versionName = "1.0.$laufnummer"
    }

    signingConfigs {
        create("heute") {
            // Immer derselbe Schlüssel: So bleibt die Unterschrift gleich und Updates behalten die eingetragenen Bücher.
            storeFile = file("heute.keystore")
            storePassword = "waslese"
            keyAlias = "heute"
            keyPassword = "waslese"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("heute")
        }
        debug {
            signingConfig = signingConfigs.getByName("heute")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    lint {
        checkReleaseBuilds = false
        abortOnError = false
    }
}

// Die Apps zeigen genau die HTML-Seiten aus dem Hauptordner an, damit Web und Handy gleich bleiben.
abstract class WebAppKopieren : DefaultTask() {
    @get:InputFiles
    abstract val quellen: ConfigurableFileCollection

    @get:OutputDirectory
    abstract val ziel: DirectoryProperty

    @TaskAction
    fun kopieren() {
        val ordner = ziel.get().asFile
        ordner.mkdirs()
        quellen.files.forEach { it.copyTo(File(ordner, it.name), overwrite = true) }
    }
}

val webApp = tasks.register<WebAppKopieren>("webApp") {
    quellen.from(rootProject.file("../index.html"), rootProject.file("../tagebuch.html"))
}

androidComponents {
    onVariants { variante ->
        variante.sources.assets?.addGeneratedSourceDirectory(webApp, WebAppKopieren::ziel)
    }
}
