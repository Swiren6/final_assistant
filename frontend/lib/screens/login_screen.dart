import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import '../services/auth_service.dart';
import '../utils/constants.dart';
import '../screens/chat_screen.dart';

class LoginScreen extends StatelessWidget {
  const LoginScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final bool isSmallScreen = MediaQuery.of(context).size.width < 600;

    return Scaffold(
      backgroundColor: Theme.of(context).scaffoldBackgroundColor,
      body: SafeArea(
        child: Center(
          child: isSmallScreen
              ? const Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    _Logo(),
                    SizedBox(height: AppConstants.paddingLarge),
                    _FormContent(),
                  ],
                )
              : Container(
                  padding: const EdgeInsets.all(AppConstants.paddingExtraLarge),
                  constraints: const BoxConstraints(maxWidth: 800),
                  child: const Row(
                    children: [
                      Expanded(child: _Logo()),
                      Expanded(child: Center(child: _FormContent())),
                    ],
                  ),
                ),
        ),
      ),
    );
  }
}

class _Logo extends StatelessWidget {
  const _Logo();

  @override
  Widget build(BuildContext context) {
    final bool isSmallScreen = MediaQuery.of(context).size.width < 600;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // Logo avec animation
        AnimatedContainer(
          duration: AppConstants.animationDurationMedium,
          child: Container(
            padding: const EdgeInsets.all(AppConstants.paddingLarge),
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  AppConstants.primaryColor,
                  AppConstants.primaryColorDark,
                ],
              ),
              boxShadow: [
                BoxShadow(
                  color: AppConstants.primaryColor.withOpacity(0.3),
                  blurRadius: 20,
                  offset: const Offset(0, 10),
                ),
              ],
            ),
            child: Image.asset(
              "assets/logo.png",
              height: isSmallScreen ? 60 : 100,
              width: isSmallScreen ? 60 : 100,
              color: Colors.white,
              errorBuilder: (context, error, stackTrace) => Icon(
                Icons.school,
                size: isSmallScreen ? 60 : 80,
                color: Colors.white,
              ),
            ),
          ),
        ),

        const SizedBox(height: AppConstants.paddingLarge),

        // Titre de l'application
        Text(
          AppConstants.appName,
          textAlign: TextAlign.center,
          style: GoogleFonts.lato(
            fontSize: isSmallScreen ? 24 : 32,
            fontWeight: FontWeight.bold,
            color: AppConstants.primaryColor,
          ),
        ),

        const SizedBox(height: AppConstants.paddingSmall),

        // Sous-titre
        Text(
          'Votre assistant intelligent',
          textAlign: TextAlign.center,
          style: GoogleFonts.lato(
            fontSize: isSmallScreen ? 14 : 16,
            color: AppConstants.textSecondary,
          ),
        ),
      ],
    );
  }
}

class _FormContent extends StatefulWidget {
  const _FormContent();

  @override
  State<_FormContent> createState() => _FormContentState();
}

class _FormContentState extends State<_FormContent>
    with SingleTickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  final _loginController = TextEditingController();
  final _passwordController = TextEditingController();

  bool _isPasswordVisible = false;
  bool _rememberMe = false;
  late AnimationController _animationController;
  late Animation<double> _fadeAnimation;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      duration: AppConstants.animationDurationMedium,
      vsync: this,
    );
    _fadeAnimation = Tween<double>(
      begin: 0.0,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _animationController,
      curve: Curves.easeInOut,
    ));
    _animationController.forward();
  }

  @override
  void dispose() {
    _loginController.dispose();
    _passwordController.dispose();
    _animationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _fadeAnimation,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 350),
        padding: const EdgeInsets.all(AppConstants.paddingLarge),
        decoration: BoxDecoration(
          color: Theme.of(context).cardColor,
          borderRadius: BorderRadius.circular(AppConstants.radiusLarge),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.1),
              blurRadius: 20,
              offset: const Offset(0, 10),
            ),
          ],
        ),
        child: Form(
          key: _formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Titre du formulaire
              Text(
                'Connexion',
                style: GoogleFonts.lato(
                  fontSize: AppConstants.fontSizeTitle,
                  fontWeight: FontWeight.bold,
                  color: AppConstants.primaryColor,
                ),
              ),

              const SizedBox(height: AppConstants.paddingLarge),

              // Champ identifiant
              _buildTextField(
                controller: _loginController,
                label: 'Identifiant',
                hint: 'Email, username ou téléphone',
                prefixIcon: Icons.person_outline,
                keyboardType: TextInputType.text,
                validator: (value) {
                  if (value?.isEmpty ?? true) {
                    return 'Veuillez entrer votre identifiant';
                  }
                  return null;
                },
              ),

              const SizedBox(height: AppConstants.paddingMedium),

              // Champ mot de passe
              _buildTextField(
                controller: _passwordController,
                label: 'Mot de passe',
                hint: 'Entrez votre mot de passe',
                prefixIcon: Icons.lock_outline,
                obscureText: !_isPasswordVisible,
                suffixIcon: IconButton(
                  icon: Icon(
                    _isPasswordVisible
                        ? Icons.visibility_outlined
                        : Icons.visibility_off_outlined,
                    color: AppConstants.textHint,
                  ),
                  onPressed: () =>
                      setState(() => _isPasswordVisible = !_isPasswordVisible),
                ),
                validator: (value) {
                  if (value?.isEmpty ?? true) {
                    return 'Veuillez entrer votre mot de passe';
                  }
                  if (value!.length < AppConstants.minPasswordLength) {
                    return 'Au moins ${AppConstants.minPasswordLength} caractères';
                  }
                  return null;
                },
              ),

              const SizedBox(height: AppConstants.paddingMedium),

              // Case "Se souvenir de moi"
              Row(
                children: [
                  Checkbox(
                    value: _rememberMe,
                    onChanged: (value) =>
                        setState(() => _rememberMe = value ?? false),
                    activeColor: AppConstants.primaryColor,
                  ),
                  Text(
                    'Se souvenir de moi',
                    style: GoogleFonts.lato(
                      fontSize: AppConstants.fontSizeMedium,
                      color: AppConstants.textSecondary,
                    ),
                  ),
                ],
              ),

              const SizedBox(height: AppConstants.paddingLarge),

              // Bouton de connexion
              Consumer<AuthService>(
                builder: (context, authService, child) {
                  return SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: authService.isLoading ? null : _submitForm,
                      style: ElevatedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(
                          vertical: AppConstants.paddingLarge,
                        ),
                        shape: RoundedRectangleBorder(
                          borderRadius:
                              BorderRadius.circular(AppConstants.radiusMedium),
                        ),
                        elevation: 2,
                      ),
                      child: authService.isLoading
                          ? const SizedBox(
                              height: 20,
                              width: 20,
                              child: CircularProgressIndicator(
                                color: Colors.white,
                                strokeWidth: 2,
                              ),
                            )
                          : Text(
                              'SE CONNECTER',
                              style: GoogleFonts.lato(
                                fontSize: AppConstants.fontSizeLarge,
                                fontWeight: FontWeight.bold,
                                letterSpacing: 1.2,
                              ),
                            ),
                    ),
                  );
                },
              ),

              const SizedBox(height: AppConstants.paddingMedium),

              // Message d'erreur
              Consumer<AuthService>(
                builder: (context, authService, child) {
                  if (authService.errorMessage != null) {
                    return Container(
                      padding: const EdgeInsets.all(AppConstants.paddingMedium),
                      decoration: BoxDecoration(
                        color: AppConstants.errorColor.withOpacity(0.1),
                        borderRadius:
                            BorderRadius.circular(AppConstants.radiusMedium),
                        border: Border.all(
                          color: AppConstants.errorColor.withOpacity(0.3),
                        ),
                      ),
                      child: Row(
                        children: [
                          Icon(
                            Icons.error_outline,
                            color: AppConstants.errorColor,
                            size: 20,
                          ),
                          const SizedBox(width: AppConstants.paddingSmall),
                          Expanded(
                            child: Text(
                              authService.errorMessage!,
                              style: GoogleFonts.lato(
                                color: AppConstants.errorColor,
                                fontSize: AppConstants.fontSizeSmall,
                              ),
                            ),
                          ),
                        ],
                      ),
                    );
                  }
                  return const SizedBox.shrink();
                },
              ),

              const SizedBox(height: AppConstants.paddingMedium),

              // Liens supplémentaires
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  TextButton(
                    onPressed: () => _showForgotPasswordDialog(),
                    child: Text(
                      'Mot de passe oublié ?',
                      style: GoogleFonts.lato(
                        fontSize: AppConstants.fontSizeSmall,
                        color: AppConstants.primaryColor,
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTextField({
    required TextEditingController controller,
    required String label,
    required String hint,
    required IconData prefixIcon,
    Widget? suffixIcon,
    bool obscureText = false,
    TextInputType keyboardType = TextInputType.text,
    String? Function(String?)? validator,
  }) {
    return TextFormField(
      controller: controller,
      obscureText: obscureText,
      keyboardType: keyboardType,
      decoration: InputDecoration(
        labelText: label,
        hintText: hint,
        prefixIcon: Icon(prefixIcon, color: AppConstants.textHint),
        suffixIcon: suffixIcon,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppConstants.radiusMedium),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppConstants.radiusMedium),
          borderSide: BorderSide(color: Colors.grey.shade300),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppConstants.radiusMedium),
          borderSide: const BorderSide(
            color: AppConstants.primaryColor,
            width: 2,
          ),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppConstants.radiusMedium),
          borderSide: const BorderSide(color: AppConstants.errorColor),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppConstants.radiusMedium),
          borderSide: const BorderSide(
            color: AppConstants.errorColor,
            width: 2,
          ),
        ),
      ),
      validator: validator,
    );
  }

  Future<void> _submitForm() async {
    if (!_formKey.currentState!.validate()) return;

    final authService = Provider.of<AuthService>(context, listen: false);

    try {
      final success = await authService.login(
        _loginController.text.trim(),
        _passwordController.text.trim(),
      );

      if (success && mounted) {
        // Afficher le message de succès
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text('✅ Connexion réussie !'),
            backgroundColor: AppConstants.successColor,
            duration: const Duration(seconds: 2),
          ),
        );
        print('✅ Navigation réussie');
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (context) => const ChatScreen()),
        );
      } else {
        // L'erreur sera affichée automatiquement via Consumer<AuthService>
        print('❌ Connexion échouée');
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Erreur: $e'),
            backgroundColor: AppConstants.errorColor,
            duration: const Duration(seconds: 3),
          ),
        );
      }
    }
  }

  void _showForgotPasswordDialog() {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppConstants.radiusLarge),
          ),
          title: Text(
            'Mot de passe oublié',
            style: GoogleFonts.lato(fontWeight: FontWeight.bold),
          ),
          content: Text(
            'Veuillez contacter l\'administrateur pour réinitialiser votre mot de passe.',
            style: GoogleFonts.lato(),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: Text(
                'OK',
                style: GoogleFonts.lato(
                  color: AppConstants.primaryColor,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}
