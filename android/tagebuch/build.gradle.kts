plugins {
    id("com.android.application")
}

// Auf GitHub zählt jede Erstellung die Versionsnummer hoch, damit sich neue Versionen über die alte installieren lassen.
val laufnummer = System.getenv("GITHUB_RUN_NUMBER")?.toIntOrNull() ?: 1

android {
    namespace = "de.waslese.tagebuch"
    compileSdk = 35

    defaultConfig {
        applicationId = "de.waslese.tagebuch"
        minSdk = 24
        targetSdk = 34
        versionCode = laufnummer
        versionName = "1.0.$laufnummer"
    }

    signingConfigs {
        create("waslese") {
            // Beide Apps tragen dieselbe Unterschrift: nur dann dürfen sie gegenseitig ihre Daten lesen,
            // und Updates lassen sich über die alte Version installieren.
            storeFile = rootProject.file("heute.keystore")
            storePassword = "waslese"
            keyAlias = "heute"
            keyPassword = "waslese"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("waslese")
        }
        debug {
            signingConfig = signingConfigs.getByName("waslese")
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

dependencies {
    implementation(project(":gemeinsam"))
}

// Die App zeigt genau die Seite aus dem Hauptordner an, damit Web und Handy gleich bleiben.
abstract class WebAppKopieren : DefaultTask() {
    @get:InputFile
    abstract val quelle: RegularFileProperty

    @get:OutputDirectory
    abstract val ziel: DirectoryProperty

    @TaskAction
    fun kopieren() {
        val ordner = ziel.get().asFile
        ordner.mkdirs()
        val datei = quelle.get().asFile
        datei.copyTo(File(ordner, datei.name), overwrite = true)
    }
}

val webApp = tasks.register<WebAppKopieren>("webApp") {
    quelle.set(rootProject.file("../tagebuch.html"))
}

androidComponents {
    onVariants { variante ->
        variante.sources.assets?.addGeneratedSourceDirectory(webApp, WebAppKopieren::ziel)
    }
}
