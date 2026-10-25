import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// Auf GitHub zählt jede Erstellung die Versionsnummer hoch, damit sich die App aktualisieren lässt.
val laufnummer = System.getenv("GITHUB_RUN_NUMBER")?.toIntOrNull() ?: 1

android {
    namespace = "de.briefverwaltung.handy"
    compileSdk = 35

    defaultConfig {
        applicationId = "de.briefverwaltung.handy"
        minSdk = 26
        targetSdk = 35
        versionCode = laufnummer
        versionName = "1.0.$laufnummer"
    }

    signingConfigs {
        create("briefe") {
            // Eigener Schlüssel (optional) über GitHub-Secrets, sonst der mitgelieferte Schlüssel –
            // so bleibt die Unterschrift gleich und neue Versionen lassen sich über die alte installieren.
            val eigenerSchluessel = System.getenv("ANDROID_KEYSTORE_DATEI")
            storeFile = if (!eigenerSchluessel.isNullOrBlank()) file(eigenerSchluessel) else file("briefverwaltung.keystore")
            storePassword = System.getenv("ANDROID_KEYSTORE_PASSWORT")?.ifBlank { null } ?: "briefverwaltung"
            keyAlias = System.getenv("ANDROID_KEY_ALIAS")?.ifBlank { null } ?: "briefverwaltung"
            keyPassword = System.getenv("ANDROID_KEY_PASSWORT")?.ifBlank { null } ?: "briefverwaltung"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("briefe")
        }
        debug {
            signingConfig = signingConfigs.getByName("briefe")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
    }

    // Die Brief-Analyse ist reines Kotlin und wird separat getestet (../analyse)
    sourceSets["main"].java.srcDir("../analyse/src/main/kotlin")

    lint {
        checkReleaseBuilds = false
        abortOnError = false
    }

    packaging {
        resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }
}

kotlin {
    compilerOptions { jvmTarget.set(JvmTarget.JVM_17) }
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")

    implementation(platform("androidx.compose:compose-bom:2024.12.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-core")

    // Google ML Kit: Dokumentscanner (Kanten, Zuschnitt, mehrere Seiten), Texterkennung, QR-Code-Scanner
    implementation("com.google.android.gms:play-services-mlkit-document-scanner:16.0.0-beta1")
    implementation("com.google.mlkit:text-recognition:16.0.1")
    implementation("com.google.android.gms:play-services-code-scanner:16.1.0")
}
