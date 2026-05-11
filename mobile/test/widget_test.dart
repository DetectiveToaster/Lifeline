import "package:flutter_test/flutter_test.dart";
import "package:lifeline_mobile/main.dart";

void main() {
  testWidgets("renders Lifeline demo shell", (tester) async {
    await tester.pumpWidget(const LifelineApp());

    expect(find.text("Lifeline"), findsOneWidget);
    expect(find.text("Seeker"), findsOneWidget);
    expect(find.text("Volunteer"), findsOneWidget);
    expect(find.text("I need someone"), findsOneWidget);
  });
}
