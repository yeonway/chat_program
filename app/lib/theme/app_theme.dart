import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  AppTheme._();

  static const Color brandBlue = Color(0xFF0C4A6E);
  static const Color brandTeal = Color(0xFF0F766E);
  static const Color brandSky = Color(0xFF0284C7);
  static const Color backgroundTop = Color(0xFFF4FAFF);
  static const Color backgroundBottom = Color(0xFFE9F4FB);

  static ThemeData light() {
    final scheme =
        ColorScheme.fromSeed(
          seedColor: brandBlue,
          brightness: Brightness.light,
        ).copyWith(
          primary: brandBlue,
          secondary: brandTeal,
          tertiary: brandSky,
          surface: Colors.white,
        );

    final textTheme = GoogleFonts.dmSansTextTheme().apply(
      bodyColor: const Color(0xFF102A43),
      displayColor: const Color(0xFF102A43),
    );

    return ThemeData(
      colorScheme: scheme,
      textTheme: textTheme,
      useMaterial3: true,
      scaffoldBackgroundColor: const Color(0xFFF6FBFF),
      appBarTheme: AppBarTheme(
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        backgroundColor: Colors.transparent,
        foregroundColor: scheme.primary,
        titleTextStyle: textTheme.titleLarge?.copyWith(
          fontWeight: FontWeight.w700,
          color: scheme.primary,
        ),
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        color: Colors.white,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: scheme.outlineVariant),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: scheme.outlineVariant),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: scheme.primary, width: 1.4),
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 14,
          vertical: 12,
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(48),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
          textStyle: textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }
}
