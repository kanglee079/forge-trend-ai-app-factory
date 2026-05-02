import 'package:flutter/material.dart';

import '../../core/app_content.dart';

class OnboardingScreen extends StatelessWidget {
  const OnboardingScreen({required this.onFinish, super.key});

  final VoidCallback onFinish;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Spacer(),
              Icon(
                Icons.auto_awesome,
                size: 56,
                color: Theme.of(context).colorScheme.primary,
              ),
              const SizedBox(height: 24),
              Text(
                AppContent.appName,
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              const SizedBox(height: 12),
              Text(
                AppContent.tagline,
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 16),
              Text(AppContent.idea),
              const Spacer(),
              FilledButton(
                onPressed: onFinish,
                child: const Text('Start'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
