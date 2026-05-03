import 'package:flutter/material.dart';

import '../../core/app_content.dart';
import '../../core/widgets/status_card.dart';
import '../core_flow/core_flow_screen.dart';
import '../onboarding/onboarding_screen.dart';
import '../paywall/paywall_screen.dart';
import '../settings/settings_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  var _showOnboarding = true;
  var _selectedIndex = 0;

  @override
  Widget build(BuildContext context) {
    if (_showOnboarding) {
      return OnboardingScreen(
        onFinish: () => setState(() => _showOnboarding = false),
      );
    }

    final pages = [
      const _HomeDashboard(),
      const SettingsScreen(),
    ];

    return Scaffold(
      appBar: AppBar(title: const Text(AppContent.appName)),
      body: pages[_selectedIndex],
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: (index) {
          setState(() => _selectedIndex = index);
        },
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.dashboard_outlined),
            selectedIcon: Icon(Icons.dashboard),
            label: 'Home',
          ),
          NavigationDestination(
            icon: Icon(Icons.settings_outlined),
            selectedIcon: Icon(Icons.settings),
            label: 'Settings',
          ),
        ],
      ),
    );
  }
}

class _HomeDashboard extends StatelessWidget {
  const _HomeDashboard();

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(
          'Today',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 12),
        const StatusCard(
          title: 'Next action',
          value: 'Review the first workflow',
          icon: Icons.task_alt,
          description: 'Replace this with the app-specific core loop.',
        ),
        const SizedBox(height: 12),
        StatusCard(
          title: 'Core flow',
          value: AppContent.coreFeatures.first,
          icon: Icons.route_outlined,
          description: 'Local sample data is ready for the first feature pass.',
        ),
        const SizedBox(height: 12),
        const StatusCard(
          title: 'Privacy posture',
          value: 'Local-first MVP',
          icon: Icons.verified_user_outlined,
          description: 'No production analytics or secrets are bundled.',
        ),
        const SizedBox(height: 12),
        const StatusCard(
          title: 'Release gate',
          value: 'Human approval required',
          icon: Icons.lock_outline,
          description: 'Production publishing is intentionally blocked.',
        ),
        const SizedBox(height: 16),
        FilledButton(
          onPressed: () => Navigator.of(context).push(
            MaterialPageRoute<void>(builder: (_) => const CoreFlowScreen()),
          ),
          child: const Text('Open core flow'),
        ),
        if (AppContent.subscriptionEnabled) ...[
          const SizedBox(height: 8),
          OutlinedButton(
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const PaywallScreen()),
            ),
            child: const Text('Premium'),
          ),
        ],
      ],
    );
  }
}
