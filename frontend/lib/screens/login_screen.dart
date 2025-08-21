import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
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
    final screenHeight = MediaQuery.of(context).size.height;

    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              AppConstants.primaryColor.withOpacity(0.1),
              AppConstants.primaryColorDark.withOpacity(0.05),
              Colors.white,
            ],
            stops: const [0.0, 0.5, 1.0],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              physics: const BouncingScrollPhysics(),
              child: isSmallScreen
                  ? Padding(
                      padding: const EdgeInsets.all(AppConstants.paddingLarge),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          SizedBox(height: screenHeight * 0.05),
                          const _EnhancedLogo(),
                          SizedBox(height: screenHeight * 0.08),
                          const _EnhancedFormContent(),
                          SizedBox(height: screenHeight * 0.05),
                        ],
                      ),
                    )
                  : Container(
                      padding: const EdgeInsets.all(AppConstants.paddingExtraLarge),
                      constraints: const BoxConstraints(maxWidth: 1200),
                      child: Row(
                        children: [
                          const Expanded(
                            flex: 3,
                            child: _EnhancedLogo(),
                          ),
                          SizedBox(width: AppConstants.paddingExtraLarge * 2),
                          Expanded(
                            flex: 2,
                            child: Center(
                              child: Container(
                                constraints: const BoxConstraints(maxWidth: 400),
                                child: const _EnhancedFormContent(),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
            ),
          ),
        ),
      ),
    );
  }
}

class _EnhancedLogo extends StatefulWidget {
  const _EnhancedLogo();

  @override
  State<_EnhancedLogo> createState() => _EnhancedLogoState();
}

class _EnhancedLogoState extends State<_EnhancedLogo>
    with TickerProviderStateMixin {
  late AnimationController _rotationController;
  late AnimationController _scaleController;
  late Animation<double> _rotationAnimation;
  late Animation<double> _scaleAnimation;

  @override
  void initState() {
    super.initState();
    
    _rotationController = AnimationController(
      duration: const Duration(seconds: 20),
      vsync: this,
    )..repeat();

    _scaleController = AnimationController(
      duration: AppConstants.animationDurationMedium,
      vsync: this,
    );

    _rotationAnimation = Tween<double>(
      begin: 0,
      end: 1,
    ).animate(CurvedAnimation(
      parent: _rotationController,
      curve: Curves.linear,
    ));

    _scaleAnimation = Tween<double>(
      begin: 0.5,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _scaleController,
      curve: Curves.elasticOut,
    ));

    _scaleController.forward();
  }

  @override
  void dispose() {
    _rotationController.dispose();
    _scaleController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final bool isSmallScreen = MediaQuery.of(context).size.width < 600;
    final logoSize = isSmallScreen ? 250.0 : 240.0;

    return ScaleTransition(
      scale: _scaleAnimation,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Logo simple sans cercle
          Container(
            child: Image.asset(
              "assets/logo.png",
              height: logoSize,
              width: logoSize,
              fit: BoxFit.contain,
              errorBuilder: (context, error, stackTrace) => Icon(
                Icons.psychology_outlined,
                size: logoSize,
                color: AppConstants.primaryColor,
              ),
            ),
          ),

          SizedBox(height: AppConstants.paddingLarge),

          // Titre avec effet de dégradé
          ShaderMask(
            shaderCallback: (bounds) => LinearGradient(
              colors: [
                AppConstants.primaryColor,
                AppConstants.primaryColorDark,
              ],
            ).createShader(bounds),
            child: Text(
              AppConstants.appName,
              textAlign: TextAlign.center,
              style: GoogleFonts.poppins(
                fontSize: isSmallScreen ? 32 : 42,
                fontWeight: FontWeight.bold,
                color: Colors.white,
                letterSpacing: -0.5,
              ),
            ),
          ),

          SizedBox(height: AppConstants.paddingSmall),

          // Sous-titre élégant
          Text(
            'Votre assistant intelligent',
            textAlign: TextAlign.center,
            style: GoogleFonts.inter(
              fontSize: isSmallScreen ? 16 : 18,
              color: AppConstants.textSecondary,
              fontWeight: FontWeight.w300,
              letterSpacing: 0.5,
            ),
          ),

          // Indicateurs visuels
          if (!isSmallScreen) ...[
            SizedBox(height: AppConstants.paddingLarge * 2),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                _FeatureIndicator(
                  icon: Icons.security,
                  label: 'Sécurisé',
                ),
                SizedBox(width: AppConstants.paddingLarge),
                _FeatureIndicator(
                  icon: Icons.speed,
                  label: 'Rapide',
                ),
                SizedBox(width: AppConstants.paddingLarge),
                _FeatureIndicator(
                  icon: Icons.smart_toy,
                  label: 'Intelligent',
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _FeatureIndicator extends StatelessWidget {
  final IconData icon;
  final String label;

  const _FeatureIndicator({
    required this.icon,
    required this.label,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AppConstants.primaryColor.withOpacity(0.1),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: AppConstants.primaryColor.withOpacity(0.2),
            ),
          ),
          child: Icon(
            icon,
            color: AppConstants.primaryColor,
            size: 20,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          label,
          style: GoogleFonts.inter(
            fontSize: 12,
            color: AppConstants.textSecondary,
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
    );
  }
}

class _EnhancedFormContent extends StatefulWidget {
  const _EnhancedFormContent();

  @override
  State<_EnhancedFormContent> createState() => _EnhancedFormContentState();
}

class _EnhancedFormContentState extends State<_EnhancedFormContent>
    with TickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  final _loginController = TextEditingController();
  final _passwordController = TextEditingController();

  bool _isPasswordVisible = false;
  bool _rememberMe = false;
  late AnimationController _slideController;
  late Animation<Offset> _slideAnimation;

  @override
  void initState() {
    super.initState();
    _slideController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );
    _slideAnimation = Tween<Offset>(
      begin: const Offset(0, 0.3),
      end: Offset.zero,
    ).animate(CurvedAnimation(
      parent: _slideController,
      curve: Curves.easeOutBack,
    ));
    _slideController.forward();
  }

  @override
  void dispose() {
    _loginController.dispose();
    _passwordController.dispose();
    _slideController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SlideTransition(
      position: _slideAnimation,
      child: Container(
        padding: const EdgeInsets.all(32),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(24),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.1),
              blurRadius: 30,
              offset: const Offset(0, 15),
            ),
            BoxShadow(
              color: AppConstants.primaryColor.withOpacity(0.05),
              blurRadius: 60,
              offset: const Offset(0, 30),
            ),
          ],
        ),
        child: Form(
          key: _formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // En-tête du formulaire
              Text(
                'Bon retour !',
                textAlign: TextAlign.center,
                style: GoogleFonts.poppins(
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                  color: AppConstants.primaryColor,
                  letterSpacing: -0.5,
                ),
              ),
              
              const SizedBox(height: 8),
              
              Text(
                'Connectez-vous à votre compte',
                textAlign: TextAlign.center,
                style: GoogleFonts.inter(
                  fontSize: 16,
                  color: AppConstants.textSecondary,
                  fontWeight: FontWeight.w400,
                ),
              ),

              const SizedBox(height: 40),

              // Champ identifiant amélioré
              _buildEnhancedTextField(
                controller: _loginController,
                label: 'Identifiant',
                hint: 'Email, username ou téléphone',
                prefixIcon: Icons.person_outline_rounded,
                keyboardType: TextInputType.emailAddress,
                validator: (value) {
                  if (value?.isEmpty ?? true) {
                    return 'Veuillez entrer votre identifiant';
                  }
                  return null;
                },
              ),

              const SizedBox(height: 24),

              // Champ mot de passe amélioré
              _buildEnhancedTextField(
                controller: _passwordController,
                label: 'Mot de passe',
                hint: 'Entrez votre mot de passe',
                prefixIcon: Icons.lock_outline_rounded,
                obscureText: !_isPasswordVisible,
                suffixIcon: IconButton(
                  icon: Icon(
                    _isPasswordVisible
                        ? Icons.visibility_rounded
                        : Icons.visibility_off_rounded,
                    color: AppConstants.textHint,
                  ),
                  onPressed: () {
                    HapticFeedback.lightImpact();
                    setState(() => _isPasswordVisible = !_isPasswordVisible);
                  },
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

              const SizedBox(height: 20),

              // Options avancées
              Row(
                children: [
                  Material(
                    color: Colors.transparent,
                    child: InkWell(
                      borderRadius: BorderRadius.circular(4),
                      onTap: () {
                        HapticFeedback.selectionClick();
                        setState(() => _rememberMe = !_rememberMe);
                      },
                      child: Padding(
                        padding: const EdgeInsets.all(4),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            AnimatedContainer(
                              duration: const Duration(milliseconds: 200),
                              width: 20,
                              height: 20,
                              decoration: BoxDecoration(
                                color: _rememberMe
                                    ? AppConstants.primaryColor
                                    : Colors.transparent,
                                border: Border.all(
                                  color: _rememberMe
                                      ? AppConstants.primaryColor
                                      : Colors.grey.shade400,
                                  width: 2,
                                ),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: _rememberMe
                                  ? const Icon(
                                      Icons.check,
                                      size: 14,
                                      color: Colors.white,
                                    )
                                  : null,
                            ),
                            const SizedBox(width: 8),
                            Text(
                              'Se souvenir de moi',
                              style: GoogleFonts.inter(
                                fontSize: 14,
                                color: AppConstants.textSecondary,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                  const Spacer(),
                  TextButton(
                    onPressed: () {
                      HapticFeedback.lightImpact();
                      _showForgotPasswordDialog();
                    },
                    child: Text(
                      'Mot de passe oublié ?',
                      style: GoogleFonts.inter(
                        fontSize: 14,
                        color: AppConstants.primaryColor,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 32),

              // Bouton de connexion amélioré
              Consumer<AuthService>(
                builder: (context, authService, child) {
                  return AnimatedContainer(
                    duration: const Duration(milliseconds: 300),
                    child: ElevatedButton(
                      onPressed: authService.isLoading ? null : _submitForm,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppConstants.primaryColor,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 16),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                        elevation: authService.isLoading ? 2 : 8,
                        shadowColor: AppConstants.primaryColor.withOpacity(0.3),
                      ),
                      child: AnimatedSwitcher(
                        duration: const Duration(milliseconds: 200),
                        child: authService.isLoading
                            ? SizedBox(
                                key: const ValueKey('loading'),
                                height: 20,
                                width: 20,
                                child: CircularProgressIndicator(
                                  color: Colors.white,
                                  strokeWidth: 2,
                                ),
                              )
                            : Text(
                                key: const ValueKey('text'),
                                'SE CONNECTER',
                                style: GoogleFonts.poppins(
                                  fontSize: 16,
                                  fontWeight: FontWeight.w600,
                                  letterSpacing: 0.5,
                                ),
                              ),
                      ),
                    ),
                  );
                },
              ),

              const SizedBox(height: 20),

              // Message d'erreur amélioré
              Consumer<AuthService>(
                builder: (context, authService, child) {
                  if (authService.errorMessage != null) {
                    return AnimatedContainer(
                      duration: const Duration(milliseconds: 300),
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: AppConstants.errorColor.withOpacity(0.08),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: AppConstants.errorColor.withOpacity(0.2),
                        ),
                      ),
                      child: Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(6),
                            decoration: BoxDecoration(
                              color: AppConstants.errorColor.withOpacity(0.1),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Icon(
                              Icons.warning_rounded,
                              color: AppConstants.errorColor,
                              size: 16,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              authService.errorMessage!,
                              style: GoogleFonts.inter(
                                color: AppConstants.errorColor,
                                fontSize: 14,
                                fontWeight: FontWeight.w500,
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
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildEnhancedTextField({
    required TextEditingController controller,
    required String label,
    required String hint,
    required IconData prefixIcon,
    Widget? suffixIcon,
    bool obscureText = false,
    TextInputType keyboardType = TextInputType.text,
    String? Function(String?)? validator,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: GoogleFonts.inter(
            fontSize: 14,
            fontWeight: FontWeight.w600,
            color: AppConstants.textPrimary,
          ),
        ),
        const SizedBox(height: 8),
        TextFormField(
          controller: controller,
          obscureText: obscureText,
          keyboardType: keyboardType,
          style: GoogleFonts.inter(
            fontSize: 16,
            fontWeight: FontWeight.w500,
          ),
          decoration: InputDecoration(
            hintText: hint,
            hintStyle: GoogleFonts.inter(
              color: AppConstants.textHint,
              fontWeight: FontWeight.w400,
            ),
            prefixIcon: Container(
              margin: const EdgeInsets.all(12),
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppConstants.primaryColor.withOpacity(0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(
                prefixIcon,
                color: AppConstants.primaryColor,
                size: 20,
              ),
            ),
            suffixIcon: suffixIcon,
            filled: true,
            fillColor: Colors.grey.shade50,
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(16),
              borderSide: BorderSide.none,
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(16),
              borderSide: BorderSide(
                color: Colors.grey.shade200,
                width: 1,
              ),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(16),
              borderSide: BorderSide(
                color: AppConstants.primaryColor,
                width: 2,
              ),
            ),
            errorBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(16),
              borderSide: const BorderSide(
                color: AppConstants.errorColor,
                width: 1,
              ),
            ),
            focusedErrorBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(16),
              borderSide: const BorderSide(
                color: AppConstants.errorColor,
                width: 2,
              ),
            ),
            contentPadding: const EdgeInsets.symmetric(
              horizontal: 20,
              vertical: 16,
            ),
          ),
          validator: validator,
        ),
      ],
    );
  }

  Future<void> _submitForm() async {
    HapticFeedback.mediumImpact();
    
    if (!_formKey.currentState!.validate()) return;

    final authService = Provider.of<AuthService>(context, listen: false);

    try {
      final success = await authService.login(
        _loginController.text.trim(),
        _passwordController.text.trim(),
      );

      if (success && mounted) {
        HapticFeedback.lightImpact();
        
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(
                    Icons.check_circle_rounded,
                    color: Colors.white,
                    size: 20,
                  ),
                ),
                const SizedBox(width: 12),
                const Text('Connexion réussie !'),
              ],
            ),
            backgroundColor: AppConstants.successColor,
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
            duration: const Duration(seconds: 2),
          ),
        );
        
        await Future.delayed(const Duration(milliseconds: 300));
        
        Navigator.of(context).pushReplacement(
          PageRouteBuilder(
            pageBuilder: (context, animation, secondaryAnimation) =>
                const ChatScreen(),
            transitionsBuilder: (context, animation, secondaryAnimation, child) {
              return FadeTransition(opacity: animation, child: child);
            },
            transitionDuration: const Duration(milliseconds: 500),
          ),
        );
      } else {
        HapticFeedback.heavyImpact();
      }
    } catch (e) {
      HapticFeedback.heavyImpact();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Row(
              children: [
                const Icon(Icons.error_outline, color: Colors.white),
                const SizedBox(width: 12),
                Expanded(child: Text('Erreur: $e')),
              ],
            ),
            backgroundColor: AppConstants.errorColor,
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
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
          backgroundColor: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
          ),
          title: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppConstants.primaryColor.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(
                  Icons.help_outline_rounded,
                  color: AppConstants.primaryColor,
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),
              Text(
                'Mot de passe oublié',
                style: GoogleFonts.poppins(
                  fontWeight: FontWeight.bold,
                  fontSize: 20,
                ),
              ),
            ],
          ),
          content: Text(
            'Veuillez contacter l\'administrateur pour réinitialiser votre mot de passe.',
            style: GoogleFonts.inter(
              fontSize: 16,
              height: 1.5,
            ),
          ),
          actions: [
            TextButton(
              onPressed: () {
                HapticFeedback.lightImpact();
                Navigator.of(context).pop();
              },
              style: TextButton.styleFrom(
                padding: const EdgeInsets.symmetric(
                  horizontal: 24,
                  vertical: 12,
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              child: Text(
                'Compris',
                style: GoogleFonts.poppins(
                  color: AppConstants.primaryColor,
                  fontWeight: FontWeight.w600,
                  fontSize: 16,
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}