import "package:dio/dio.dart";

import "../config/app_config.dart";

class ApiClient {
  ApiClient({Dio? dio}) : _dio = dio ?? Dio(BaseOptions(baseUrl: AppConfig.baseUrl));

  final Dio _dio;

  Future<String> authAnonymous({required String role}) async {
    final response = await _dio.post("/v1/auth/anonymous", data: {"role": role});
    return response.data["token"] as String;
  }

  Future<Map<String, dynamic>> requestSession({required String token}) async {
    final response = await _dio.post(
      "/v1/session/request",
      data: {"client_capabilities": {"platform": "android"}},
      options: Options(headers: {"Authorization": "Bearer $token"}),
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<void> cancelSession({required String token, required String sessionId}) async {
    await _dio.post(
      "/v1/session/cancel",
      data: {"session_id": sessionId},
      options: Options(headers: {"Authorization": "Bearer $token"}),
    );
  }

  Future<void> leaveSession({required String token, required String sessionId}) async {
    await _dio.post(
      "/v1/session/leave",
      data: {"session_id": sessionId},
      options: Options(headers: {"Authorization": "Bearer $token"}),
    );
  }

  Future<void> volunteerStatus({required String token, required bool available}) async {
    await _dio.post(
      "/v1/volunteer/status",
      data: {"available": available},
      options: Options(headers: {"Authorization": "Bearer $token"}),
    );
  }

  Future<List<Map<String, dynamic>>> volunteerPending({required String token}) async {
    final response = await _dio.get(
      "/v1/volunteer/pending",
      options: Options(headers: {"Authorization": "Bearer $token"}),
    );
    return (response.data as List)
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();
  }

  Future<void> volunteerAccept({required String token, required String sessionId}) async {
    await _dio.post(
      "/v1/volunteer/accept",
      data: {"session_id": sessionId},
      options: Options(headers: {"Authorization": "Bearer $token"}),
    );
  }

  Future<void> volunteerDecline({required String token, required String sessionId}) async {
    await _dio.post(
      "/v1/volunteer/decline",
      data: {"session_id": sessionId},
      options: Options(headers: {"Authorization": "Bearer $token"}),
    );
  }

  Future<Map<String, dynamic>> fetchPublicConfig() async {
    final response = await _dio.get("/v1/config/public");
    return Map<String, dynamic>.from(response.data as Map);
  }
}
