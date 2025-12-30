class AppConfig {
  static const String baseUrl = String.fromEnvironment(
    "LIFELINE_API_BASE",
    defaultValue: "http://10.0.2.2:8000",
  );

  static String get baseWsUrl {
    if (baseUrl.startsWith("https://")) {
      return baseUrl.replaceFirst("https://", "wss://");
    }
    if (baseUrl.startsWith("http://")) {
      return baseUrl.replaceFirst("http://", "ws://");
    }
    return baseUrl;
  }
}
