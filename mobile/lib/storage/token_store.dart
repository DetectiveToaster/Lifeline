import "package:flutter_secure_storage/flutter_secure_storage.dart";

import "../services/api_client.dart";

class TokenStore {
  TokenStore({FlutterSecureStorage? storage}) : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  Future<String> getOrCreateToken({required ApiClient api, required String role}) async {
    final key = "token_$role";
    final existing = await _storage.read(key: key);
    if (existing != null && existing.isNotEmpty) {
      return existing;
    }
    final token = await api.authAnonymous(role: role);
    await _storage.write(key: key, value: token);
    return token;
  }
}
