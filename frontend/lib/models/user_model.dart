import 'dart:convert';

class UserModel {
  final String idpersonne;
  final String? email;
  final List<String> roles;
  final bool changepassword;
  final String? token;

  UserModel({
    required this.idpersonne,
    this.email,
    required this.roles,
    required this.changepassword,
    this.token,
  });

  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      idpersonne: json['idpersonne']?.toString() ?? '',
      email: json['email'],
      roles: _parseRoles(json['roles']),
      changepassword: _parseBool(json['changepassword']),
      token: json['token'],
    );
  }

  /// Parse les rôles depuis différents formats possibles
  static List<String> _parseRoles(dynamic roles) {
    if (roles == null) return [];
    
    print('🔍 Parsing roles: $roles (type: ${roles.runtimeType})');
    
    if (roles is List) {
      // Déjà une liste
      List<String> result = roles.map((e) => e.toString()).toList();
      print('✅ Roles parsed as list: $result');
      return result;
    }
    
    if (roles is String) {
      try {
        // Tenter de parser comme JSON
        var decoded = jsonDecode(roles);
        if (decoded is List) {
          List<String> result = decoded.map((e) => e.toString()).toList();
          print('✅ Roles parsed from JSON: $result');
          return result;
        }
        // Si c'est une chaîne simple après décodage
        List<String> result = [decoded.toString()];
        print('✅ Roles parsed as single item: $result');
        return result;
      } catch (e) {
        // Si le parsing JSON échoue, traiter comme une chaîne simple
        print('⚠️ JSON parsing failed, treating as string: $roles');
        return [roles];
      }
    }
    
    // Fallback pour tout autre type
    List<String> result = [roles.toString()];
    print('⚠️ Roles fallback: $result');
    return result;
  }

  /// Parse un boolean depuis différents formats
  static bool _parseBool(dynamic value) {
    if (value == null) return false;
    if (value is bool) return value;
    if (value is int) return value != 0;
    if (value is String) {
      return value.toLowerCase() == 'true' || value == '1';
    }
    return false;
  }

  Map<String, dynamic> toJson() {
    return {
      'idpersonne': idpersonne,
      'email': email,
      'roles': roles,
      'changepassword': changepassword,
      'token': token,
    };
  }

  UserModel copyWith({
    String? idpersonne,
    String? email,
    List<String>? roles,
    bool? changepassword,
    String? token,
  }) {
    return UserModel(
      idpersonne: idpersonne ?? this.idpersonne,
      email: email ?? this.email,
      roles: roles ?? this.roles,
      changepassword: changepassword ?? this.changepassword,
      token: token ?? this.token,
    );
  }

  /// Vérifie si l'utilisateur a un rôle spécifique
  bool hasRole(String role) {
    return roles.contains(role);
  }

  /// Vérifie si l'utilisateur a un des rôles spécifiés
  bool hasAnyRole(List<String> rolesToCheck) {
    return roles.any((role) => rolesToCheck.contains(role));
  }

  // /// Vérifie si l'utilisateur est admin
  // bool get isAdmin {
  //   return hasAnyRole(['ROLE_ADMIN', 'ROLE_SUPER_ADMIN']);
  // }

  // /// Vérifie si l'utilisateur est professeur
  // bool get isTeacher {
  //   return hasAnyRole(['ROLE_TEACHER', 'ROLE_ADMIN', 'ROLE_SUPER_ADMIN']);
  // }

  // /// Vérifie si l'utilisateur est étudiant
  // bool get isStudent {
  //   return hasRole('ROLE_STUDENT');
  // }

  // /// Obtient le rôle principal (le plus élevé dans la hiérarchie)
  // String get primaryRole {
  //   if (hasRole('ROLE_SUPER_ADMIN')) return 'Super Admin';
  //   if (hasRole('ROLE_ADMIN')) return 'Administrateur';
  //   if (hasRole('ROLE_TEACHER')) return 'Professeur';
  //   if (hasRole('ROLE_STUDENT')) return 'Étudiant';
  //   return 'Utilisateur';
  // }

  /// Obtient une version lisible des rôles
  // List<String> get displayRoles {
  //   return roles.map((role) {
  //     switch (role) {
  //       case 'ROLE_SUPER_ADMIN':
  //         return 'Super Admin';
  //       case 'ROLE_ADMIN':
  //         return 'Administrateur';
  //       case 'ROLE_TEACHER':
  //         return 'Professeur';
  //       case 'ROLE_STUDENT':
  //         return 'Étudiant';
  //       default:
  //         return role.replaceFirst('ROLE_', '').toLowerCase().capitalize();
  //     }
  //   }).toList();
  // }

  @override
  String toString() {
    return 'UserModel{idpersonne: $idpersonne, email: $email, roles: $roles, changepassword: $changepassword}';
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is UserModel &&
        other.idpersonne == idpersonne &&
        other.email == email;
  }

  @override
  int get hashCode {
    return idpersonne.hashCode ^ (email?.hashCode ?? 0);
  }
}

// Extension pour capitaliser les chaînes
extension StringCapitalizeExtension on String {
  String capitalize() {
    if (isEmpty) return this;
    return '${this[0].toUpperCase()}${substring(1).toLowerCase()}';
  }
}