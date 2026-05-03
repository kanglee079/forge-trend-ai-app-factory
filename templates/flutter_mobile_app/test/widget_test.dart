import 'package:flutter_test/flutter_test.dart';
import 'package:forge_trend_app_template/app.dart';
import 'package:forge_trend_app_template/core/app_content.dart';

void main() {
  testWidgets('onboarding leads to home dashboard', (tester) async {
    await tester.pumpWidget(const ForgeTrendApp());

    expect(find.text(AppContent.appName), findsOneWidget);
    expect(find.text('Start'), findsOneWidget);

    await tester.tap(find.text('Start'));
    await tester.pumpAndSettle();

    expect(find.text('Today'), findsOneWidget);
    expect(find.text('Next action'), findsOneWidget);
    expect(find.text('Core flow'), findsOneWidget);
  });

  testWidgets('paywall visible when subscription enabled', (tester) async {
    await tester.pumpWidget(const ForgeTrendApp());

    await tester.tap(find.text('Start'));
    await tester.pumpAndSettle();

    if (AppContent.subscriptionEnabled) {
      await tester.scrollUntilVisible(find.text('Premium'), 120);
      expect(find.text('Premium'), findsOneWidget);
    }
  });

  testWidgets('settings and privacy screen exists', (tester) async {
    await tester.pumpWidget(const ForgeTrendApp());

    await tester.tap(find.text('Start'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Settings'));
    await tester.pumpAndSettle();

    expect(find.text('Settings'), findsWidgets);
    expect(find.text('Privacy policy'), findsOneWidget);
  });
}
