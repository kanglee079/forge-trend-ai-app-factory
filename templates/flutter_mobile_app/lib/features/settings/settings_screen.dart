import 'package:flutter/material.dart';

import '../privacy/privacy_screen.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('Settings', style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 12),
        Card(
          child: SwitchListTile(
            value: true,
            onChanged: null,
            title: const Text('Privacy-first defaults'),
            subtitle: const Text('Production telemetry must be reviewed before release.'),
          ),
        ),
        const SizedBox(height: 12),
        const Card(
          child: ListTile(
            leading: Icon(Icons.policy_outlined),
            title: Text('Privacy policy'),
            subtitle: Text('Placeholder included in project workspace.'),
          ),
        ),
        const SizedBox(height: 12),
        FilledButton(
          onPressed: () => Navigator.of(context).push(
            MaterialPageRoute<void>(builder: (_) => const PrivacyScreen()),
          ),
          child: const Text('Privacy and about'),
        ),
      ],
    );
  }
}
