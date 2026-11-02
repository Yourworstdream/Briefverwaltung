plugins {
    id("com.android.library")
}

// Was beide Apps gemeinsam haben: Anzeige der Seite, Brücke zur Partner-App, Datenschnittstelle.
android {
    namespace = "de.waslese.gemeinsam"
    compileSdk = 35

    defaultConfig {
        minSdk = 24
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    lint {
        abortOnError = false
    }
}
