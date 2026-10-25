package de.briefverwaltung.handy.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// Dieselben Farben wie im PC-Programm
private val Hell = lightColorScheme(
    primary = Color(0xFF2563EB),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFE7EFFF),
    onPrimaryContainer = Color(0xFF0B2A6B),
    secondary = Color(0xFF475569),
    background = Color(0xFFF6F7F9),
    surface = Color.White,
    surfaceVariant = Color(0xFFEEF1F5),
    onSurfaceVariant = Color(0xFF5B6B7C),
    error = Color(0xFFC62828),
)

private val Dunkel = darkColorScheme(
    primary = Color(0xFF8AB4FF),
    onPrimary = Color(0xFF002E6E),
    primaryContainer = Color(0xFF1E3A8A),
    onPrimaryContainer = Color(0xFFDCE7FF),
    secondary = Color(0xFFB8C4D3),
    background = Color(0xFF111418),
    surface = Color(0xFF1A1E24),
    surfaceVariant = Color(0xFF262B33),
    onSurfaceVariant = Color(0xFFAEB9C6),
    error = Color(0xFFFF8A80),
)

/** Farben der vier Dringlichkeitsstufen (wie im PC-Programm). */
fun dringlichkeitFarbe(stufe: Int, dunkel: Boolean): Color = when (stufe) {
    1 -> if (dunkel) Color(0xFF9AA9B6) else Color(0xFF6B7F8E)
    3 -> if (dunkel) Color(0xFFFFB74D) else Color(0xFFD17A00)
    4 -> if (dunkel) Color(0xFFFF8A80) else Color(0xFFC62828)
    else -> if (dunkel) Color(0xFF81C995) else Color(0xFF2F7D4F)
}

@Composable
fun BriefTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = if (isSystemInDarkTheme()) Dunkel else Hell, content = content)
}
