import "package:flutter/material.dart";
import "package:provider/provider.dart";

import "../state/session_controller.dart";

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final controller = context.watch<SessionController>();
    return Scaffold(
      appBar: AppBar(
        title: const Text("Lifeline"),
      ),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text("Phase: ${controller.phase.name}"),
            const SizedBox(height: 12),
            if (controller.state != null) Text("State: ${controller.state}"),
            if (controller.remainingSeconds != null)
              Text("Time left: ${controller.remainingSeconds}s"),
            if (controller.lastSystemMessage != null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(
                  controller.lastSystemMessage!,
                  style: const TextStyle(color: Colors.blueGrey),
                ),
              ),
            if (controller.lastWarningMessage != null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(
                  controller.lastWarningMessage!,
                  style: const TextStyle(color: Colors.redAccent),
                ),
              ),
            const Spacer(),
            ElevatedButton(
              onPressed: controller.phase == SessionPhase.idle ||
                      controller.phase == SessionPhase.ended
                  ? () => controller.startSeekerSession()
                  : null,
              child: const Text("I need someone"),
            ),
            const SizedBox(height: 12),
            OutlinedButton(
              onPressed: controller.phase == SessionPhase.active ||
                      controller.phase == SessionPhase.matching
                  ? () => controller.leaveSession()
                  : null,
              child: const Text("Leave session"),
            ),
          ],
        ),
      ),
    );
  }
}
