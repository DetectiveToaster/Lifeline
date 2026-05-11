import "package:flutter/material.dart";
import "package:provider/provider.dart";

import "../models/chat_message.dart";
import "../state/session_controller.dart";

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final TextEditingController _messageController = TextEditingController();

  @override
  void dispose() {
    _messageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final controller = context.watch<SessionController>();
    return Scaffold(
      backgroundColor: const Color(0xFF05070A),
      body: SafeArea(
        child: Column(
          children: [
            _Header(controller: controller),
            Expanded(child: _Body(controller: controller)),
            if (controller.phase == SessionPhase.active) _Composer(controller: controller, input: _messageController),
          ],
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.controller});

  final SessionController controller;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
      child: Row(
        children: [
          const Expanded(
            child: Text(
              "Lifeline",
              style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: Color(0xFFF5F7FA)),
            ),
          ),
          _RoleChip(
            label: "Seeker",
            selected: controller.role == DemoRole.seeker,
            onTap: () => controller.switchRole(DemoRole.seeker),
          ),
          const SizedBox(width: 8),
          _RoleChip(
            label: "Volunteer",
            selected: controller.role == DemoRole.volunteer,
            onTap: () => controller.switchRole(DemoRole.volunteer),
          ),
        ],
      ),
    );
  }
}

class _RoleChip extends StatelessWidget {
  const _RoleChip({required this.label, required this.selected, required this.onTap});

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(20),
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: selected ? const Color(0xFF4BA3C7) : const Color(0xFF12151C),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: const Color(0xFF2B3140)),
        ),
        child: Text(label, style: const TextStyle(color: Color(0xFFF5F7FA), fontSize: 13)),
      ),
    );
  }
}

class _Body extends StatelessWidget {
  const _Body({required this.controller});

  final SessionController controller;

  @override
  Widget build(BuildContext context) {
    if (controller.phase == SessionPhase.active) {
      return _ChatView(controller: controller);
    }
    if (controller.phase == SessionPhase.matching || controller.phase == SessionPhase.pendingAccept) {
      return _WaitingView(controller: controller);
    }
    if (controller.phase == SessionPhase.ended || controller.phase == SessionPhase.error) {
      return _EndedView(controller: controller);
    }
    return controller.role == DemoRole.seeker ? _SeekerLanding(controller: controller) : _VolunteerLanding(controller: controller);
  }
}

class _SeekerLanding extends StatelessWidget {
  const _SeekerLanding({required this.controller});

  final SessionController controller;

  @override
  Widget build(BuildContext context) {
    return _CenteredPanel(
      title: "You are not alone.",
      body: "Start a private five minute conversation with a volunteer. No names, no profiles, no saved chat.",
      action: FilledButton(
        onPressed: controller.startSeekerSession,
        child: const Text("I need someone"),
      ),
    );
  }
}

class _VolunteerLanding extends StatelessWidget {
  const _VolunteerLanding({required this.controller});

  final SessionController controller;

  @override
  Widget build(BuildContext context) {
    return _CenteredPanel(
      title: "Offer five minutes.",
      body: "Listening matters more than fixing. Stay anonymous, avoid advice, and keep the conversation grounded.",
      action: SwitchListTile(
        value: controller.volunteerAvailable,
        onChanged: controller.setVolunteerAvailable,
        title: const Text("Available for requests", style: TextStyle(color: Color(0xFFF5F7FA))),
        activeThumbColor: const Color(0xFF4BA3C7),
      ),
    );
  }
}

class _WaitingView extends StatelessWidget {
  const _WaitingView({required this.controller});

  final SessionController controller;

  @override
  Widget build(BuildContext context) {
    if (controller.phase == SessionPhase.pendingAccept && controller.role == DemoRole.volunteer) {
      return _CenteredPanel(
        title: "Someone needs to talk.",
        body: "Accept if you can be present for five minutes.",
        action: Row(
          children: [
            Expanded(
              child: OutlinedButton(onPressed: controller.declineVolunteerSession, child: const Text("Decline")),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: FilledButton(onPressed: controller.acceptVolunteerSession, child: const Text("Accept")),
            ),
          ],
        ),
      );
    }
    return _CenteredPanel(
      title: controller.role == DemoRole.seeker ? "Finding someone..." : "Waiting for a request...",
      body: controller.role == DemoRole.seeker
          ? "If no volunteer is available, you will see a fallback message shortly."
          : "Keep this screen open in demo mode to receive assigned sessions.",
      action: OutlinedButton(onPressed: controller.leaveSession, child: const Text("Cancel")),
    );
  }
}

class _ChatView extends StatelessWidget {
  const _ChatView({required this.controller});

  final SessionController controller;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
          child: _TimerPill(seconds: controller.remainingSeconds),
        ),
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
            itemCount: controller.messages.length,
            itemBuilder: (context, index) => _MessageBubble(message: controller.messages[index]),
          ),
        ),
        if (controller.role == DemoRole.volunteer)
          const Padding(
            padding: EdgeInsets.fromLTRB(20, 0, 20, 12),
            child: Text(
              "Try: I hear you.  You are safe to talk here.  Thank you for trusting me.",
              style: TextStyle(color: Color(0xFFA0A7B3), fontSize: 12),
            ),
          ),
      ],
    );
  }
}

class _EndedView extends StatelessWidget {
  const _EndedView({required this.controller});

  final SessionController controller;

  @override
  Widget build(BuildContext context) {
    return _CenteredPanel(
      title: controller.phase == SessionPhase.error ? "Connection issue" : "Session ended",
      body: controller.lastSystemMessage ?? controller.lastWarningMessage ?? "Thank you for being here. The chat is gone.",
      action: FilledButton(
        onPressed: controller.role == DemoRole.seeker ? controller.startSeekerSession : () => controller.setVolunteerAvailable(false),
        child: Text(controller.role == DemoRole.seeker ? "Start another session" : "Return to volunteer mode"),
      ),
    );
  }
}

class _CenteredPanel extends StatelessWidget {
  const _CenteredPanel({required this.title, required this.body, required this.action});

  final String title;
  final String body;
  final Widget action;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 480),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(title, style: const TextStyle(color: Color(0xFFF5F7FA), fontSize: 28, fontWeight: FontWeight.w700)),
              const SizedBox(height: 12),
              Text(body, style: const TextStyle(color: Color(0xFFA0A7B3), fontSize: 16, height: 1.4)),
              const SizedBox(height: 24),
              action,
            ],
          ),
        ),
      ),
    );
  }
}

class _TimerPill extends StatelessWidget {
  const _TimerPill({required this.seconds});

  final int? seconds;

  @override
  Widget build(BuildContext context) {
    final value = seconds ?? 300;
    final minutes = (value ~/ 60).toString().padLeft(2, "0");
    final remaining = (value % 60).toString().padLeft(2, "0");
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(color: const Color(0xFF12151C), borderRadius: BorderRadius.circular(24)),
      child: Text("$minutes:$remaining", textAlign: TextAlign.center, style: const TextStyle(color: Color(0xFFF5F7FA), fontSize: 20)),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({required this.message});

  final ChatMessage message;

  @override
  Widget build(BuildContext context) {
    final isLocal = message.kind == ChatMessageKind.local;
    final isNotice = message.kind == ChatMessageKind.system || message.kind == ChatMessageKind.warning;
    return Align(
      alignment: isNotice ? Alignment.center : (isLocal ? Alignment.centerRight : Alignment.centerLeft),
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        constraints: const BoxConstraints(maxWidth: 320),
        decoration: BoxDecoration(
          color: isNotice
              ? const Color(0xFF1A1F29)
              : (isLocal ? const Color(0xFF4BA3C7) : const Color(0xFF12151C)),
          borderRadius: BorderRadius.circular(16),
        ),
        child: Text(
          message.text,
          style: TextStyle(color: isNotice ? const Color(0xFFA0A7B3) : const Color(0xFFF5F7FA), height: 1.35),
        ),
      ),
    );
  }
}

class _Composer extends StatelessWidget {
  const _Composer({required this.controller, required this.input});

  final SessionController controller;
  final TextEditingController input;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: input,
              minLines: 1,
              maxLines: 4,
              style: const TextStyle(color: Color(0xFFF5F7FA)),
              decoration: InputDecoration(
                hintText: "Type a message",
                hintStyle: const TextStyle(color: Color(0xFFA0A7B3)),
                filled: true,
                fillColor: const Color(0xFF12151C),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(24), borderSide: BorderSide.none),
              ),
              onSubmitted: (_) => _send(),
            ),
          ),
          const SizedBox(width: 10),
          IconButton.filled(
            onPressed: _send,
            icon: const Icon(Icons.arrow_upward),
          ),
          const SizedBox(width: 6),
          IconButton(
            onPressed: controller.leaveSession,
            icon: const Icon(Icons.close),
            color: const Color(0xFFA0A7B3),
          ),
        ],
      ),
    );
  }

  void _send() {
    final text = input.text;
    input.clear();
    controller.sendMessage(text);
  }
}
