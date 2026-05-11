import "package:flutter/material.dart";
import "package:provider/provider.dart";

import "services/api_client.dart";
import "state/session_controller.dart";
import "storage/token_store.dart";
import "ui/home_screen.dart";

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const LifelineApp());
}

class LifelineApp extends StatelessWidget {
  const LifelineApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(
          create: (_) => SessionController(
            api: ApiClient(),
            tokenStore: TokenStore(),
          ),
        ),
      ],
      child: MaterialApp(
        title: "Lifeline",
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          brightness: Brightness.dark,
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFF4BA3C7),
            brightness: Brightness.dark,
            surface: const Color(0xFF12151C),
          ),
          scaffoldBackgroundColor: const Color(0xFF05070A),
          useMaterial3: true,
        ),
        home: const HomeScreen(),
      ),
    );
  }
}
