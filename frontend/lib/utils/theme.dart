import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'constants.dart';

class AppTheme {
  // Thème clair
  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      primarySwatch: AppConstants.primaryColor.materialColor,
      primaryColor: AppConstants.primaryColor,
      scaffoldBackgroundColor: AppConstants.backgroundLight,
      
      // AppBar Theme
      appBarTheme: AppBarTheme(
        backgroundColor: AppConstants.primaryColor,
        foregroundColor: Colors.white,
        elevation: 2,
        centerTitle: true,
        titleTextStyle: GoogleFonts.lato(
          fontSize: AppConstants.fontSizeExtraLarge,
          fontWeight: FontWeight.w600,
          color: Colors.white,
        ),
      ),
      
      // Card Theme
      cardTheme: CardThemeData(
        color: AppConstants.surfaceLight,
        elevation: 2,
        shadowColor: Colors.black26,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppConstants.radiusMedium),
        ),
      ),
      
      // Button Themes
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AppConstants.primaryColor,
          foregroundColor: Colors.white,
          elevation: 2,
          padding: const EdgeInsets.symmetric(
            horizontal: AppConstants.paddingLarge,
            vertical: AppConstants.paddingMedium,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppConstants.radiusMedium),
          ),
          textStyle: GoogleFonts.lato(
            fontSize: AppConstants.fontSizeLarge,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: AppConstants.primaryColor,
          textStyle: GoogleFonts.lato(
            fontSize: AppConstants.fontSizeMedium,
            fontWeight: FontWeight.w500,
          ),
        ),
      ),
      
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: AppConstants.primaryColor,
          side: const BorderSide(color: AppConstants.primaryColor),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppConstants.radiusMedium),
          ),
          textStyle: GoogleFonts.lato(
            fontSize: AppConstants.fontSizeMedium,
            fontWeight: FontWeight.w500,
          ),
        ),
      ),
      
      // Input Decoration Theme
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppConstants.surfaceLight,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppConstants.radiusMedium),
          borderSide: BorderSide(color: Colors.grey.shade300),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppConstants.radiusMedium),
          borderSide: BorderSide(color: Colors.grey.shade300),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppConstants.radiusMedium),
          borderSide: const BorderSide(color: AppConstants.primaryColor, width: 2),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppConstants.radiusMedium),
          borderSide: const BorderSide(color: AppConstants.errorColor),
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: AppConstants.paddingMedium,
          vertical: AppConstants.paddingMedium,
        ),
        labelStyle: GoogleFonts.lato(
          color: AppConstants.textSecondary,
          fontSize: AppConstants.fontSizeMedium,
        ),
        hintStyle: GoogleFonts.lato(
          color: AppConstants.textHint,
          fontSize: AppConstants.fontSizeMedium,
        ),
      ),
      
      // Text Theme
      textTheme: GoogleFonts.latoTextTheme().copyWith(
        displayLarge: GoogleFonts.lato(
          fontSize: 32,
          fontWeight: FontWeight.bold,
          color: AppConstants.textPrimary,
        ),
        displayMedium: GoogleFonts.lato(
          fontSize: 28,
          fontWeight: FontWeight.bold,
          color: AppConstants.textPrimary,
        ),
        displaySmall: GoogleFonts.lato(
          fontSize: AppConstants.fontSizeHeading,
          fontWeight: FontWeight.w600,
          color: AppConstants.textPrimary,
        ),
        headlineLarge: GoogleFonts.lato(
          fontSize: AppConstants.fontSizeTitle,
          fontWeight: FontWeight.w600,
          color: AppConstants.textPrimary,
        ),
        headlineMedium: GoogleFonts.lato(
          fontSize: AppConstants.fontSizeExtraLarge,
          fontWeight: FontWeight.w500,
          color: AppConstants.textPrimary,
        ),
        titleLarge: GoogleFonts.lato(
          fontSize: AppConstants.fontSizeLarge,
          fontWeight: FontWeight.w500,
          color: AppConstants.textPrimary,
        ),
        bodyLarge: GoogleFonts.lato(
          fontSize: AppConstants.fontSizeLarge,
          color: AppConstants.textPrimary,
        ),
        bodyMedium: GoogleFonts.lato(
          fontSize: AppConstants.fontSizeMedium,
          color: AppConstants.textPrimary,
        ),
        bodySmall: GoogleFonts.lato(
          fontSize: AppConstants.fontSizeSmall,
          color: AppConstants.textSecondary,
        ),
      ),
      
      // Icon Theme
      iconTheme: const IconThemeData(
        color: AppConstants.textSecondary,
        size: 24,
      ),
      
      // Divider Theme
      dividerTheme: const DividerThemeData(
        color: Colors.grey,
        thickness: 1,
        space: 1,
      ),
      
      // Snackbar Theme
      snackBarTheme: SnackBarThemeData(
        backgroundColor: AppConstants.textPrimary,
        contentTextStyle: GoogleFonts.lato(
          color: Colors.white,
          fontSize: AppConstants.fontSizeMedium,
        ),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppConstants.radiusMedium),
        ),
        behavior: SnackBarBehavior.floating,
      ),
      
      // Floating Action Button Theme
      floatingActionButtonTheme: const FloatingActionButtonThemeData(
        backgroundColor: AppConstants.primaryColor,
        foregroundColor: Colors.white,
        elevation: 4,
      ),
    );
  }
  
  // Thème sombre
  static ThemeData get darkTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      primarySwatch: AppConstants.primaryColor.materialColor,
      primaryColor: AppConstants.primaryColor,
      scaffoldBackgroundColor: AppConstants.backgroundDark,
      
      // AppBar Theme
      appBarTheme: AppBarTheme(
        backgroundColor: AppConstants.surfaceDark,
        foregroundColor: Colors.white,
        elevation: 2,
        centerTitle: true,
        titleTextStyle: GoogleFonts.lato(
          fontSize: AppConstants.fontSizeExtraLarge,
          fontWeight: FontWeight.w600,
          color: Colors.white,
        ),
      ),
      
      // Card Theme
      cardTheme: CardThemeData(
        color: AppConstants.surfaceDark,
        elevation: 2,
        shadowColor: Colors.black54,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppConstants.radiusMedium),
        ),
      ),
      
      // Button Themes
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AppConstants.primaryColor,
          foregroundColor: Colors.white,
          elevation: 2,
          padding: const EdgeInsets.symmetric(
            horizontal: AppConstants.paddingLarge,
            vertical: AppConstants.paddingMedium,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppConstants.radiusMedium),
          ),
          textStyle: GoogleFonts.lato(
            fontSize: AppConstants.fontSizeLarge,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: AppConstants.primaryColor,
          textStyle: GoogleFonts.lato(
            fontSize: AppConstants.fontSizeMedium,
            fontWeight: FontWeight.w500,
          ),
        ),
      ),
      
      // Input Decoration Theme
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppConstants.surfaceDark,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppConstants.radiusMedium),
          borderSide: BorderSide(color: Colors.grey.shade600),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppConstants.radiusMedium),
          borderSide: BorderSide(color: Colors.grey.shade600),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppConstants.radiusMedium),
          borderSide: const BorderSide(color: AppConstants.primaryColor, width: 2),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppConstants.radiusMedium),
          borderSide: const BorderSide(color: AppConstants.errorColor),
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: AppConstants.paddingMedium,
          vertical: AppConstants.paddingMedium,
        ),
        labelStyle: GoogleFonts.lato(
          color: Colors.grey.shade300,
          fontSize: AppConstants.fontSizeMedium,
        ),
        hintStyle: GoogleFonts.lato(
          color: Colors.grey.shade500,
          fontSize: AppConstants.fontSizeMedium,
        ),
      ),
      
      // Text Theme pour le mode sombre
      textTheme: GoogleFonts.latoTextTheme(ThemeData.dark().textTheme).copyWith(
        displayLarge: GoogleFonts.lato(
          fontSize: 32,
          fontWeight: FontWeight.bold,
          color: Colors.white,
        ),
        displayMedium: GoogleFonts.lato(
          fontSize: 28,
          fontWeight: FontWeight.bold,
          color: Colors.white,
        ),
        displaySmall: GoogleFonts.lato(
          fontSize: AppConstants.fontSizeHeading,
          fontWeight: FontWeight.w600,
          color: Colors.white,
        ),
        headlineLarge: GoogleFonts.lato(
          fontSize: AppConstants.fontSizeTitle,
          fontWeight: FontWeight.w600,
          color: Colors.white,
        ),
        headlineMedium: GoogleFonts.lato(
          fontSize: AppConstants.fontSizeExtraLarge,
          fontWeight: FontWeight.w500,
          color: Colors.white,
        ),
        titleLarge: GoogleFonts.lato(
          fontSize: AppConstants.fontSizeLarge,
          fontWeight: FontWeight.w500,
          color: Colors.white,
        ),
        bodyLarge: GoogleFonts.lato(
          fontSize: AppConstants.fontSizeLarge,
          color: Colors.white,
        ),
        bodyMedium: GoogleFonts.lato(
          fontSize: AppConstants.fontSizeMedium,
          color: Colors.white,
        ),
        bodySmall: GoogleFonts.lato(
          fontSize: AppConstants.fontSizeSmall,
          color: Colors.grey.shade300,
        ),
      ),
      
      // Icon Theme
      iconTheme: const IconThemeData(
        color: Colors.grey,
        size: 24,
      ),
      
      // Snackbar Theme
      snackBarTheme: SnackBarThemeData(
        backgroundColor: AppConstants.surfaceDark,
        contentTextStyle: GoogleFonts.lato(
          color: Colors.white,
          fontSize: AppConstants.fontSizeMedium,
        ),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppConstants.radiusMedium),
        ),
        behavior: SnackBarBehavior.floating,
      ),
      
      // Floating Action Button Theme
      floatingActionButtonTheme: const FloatingActionButtonThemeData(
        backgroundColor: AppConstants.primaryColor,
        foregroundColor: Colors.white,
        elevation: 4,
      ),
    );
  }
}

// Utilitaires pour les thèmes
class ThemeUtils {
  static bool isDarkMode(BuildContext context) {
    return Theme.of(context).brightness == Brightness.dark;
  }
  
  static Color getBackgroundColor(BuildContext context) {
    return isDarkMode(context) 
        ? AppConstants.backgroundDark 
        : AppConstants.backgroundLight;
  }
  
  static Color getSurfaceColor(BuildContext context) {
    return isDarkMode(context) 
        ? AppConstants.surfaceDark 
        : AppConstants.surfaceLight;
  }
  
  static Color getTextColor(BuildContext context) {
    return isDarkMode(context) 
        ? Colors.white 
        : AppConstants.textPrimary;
  }
}