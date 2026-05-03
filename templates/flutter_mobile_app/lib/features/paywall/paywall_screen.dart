import 'package:flutter/material.dart';

import '../../core/app_content.dart';
import 'purchase_service.dart';

class PaywallScreen extends StatefulWidget {
  const PaywallScreen({super.key});

  @override
  State<PaywallScreen> createState() => _PaywallScreenState();
}

class _PaywallScreenState extends State<PaywallScreen> {
  final _purchaseService = const PurchaseService();
  String? _message;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Premium')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Premium placeholder', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 12),
          Text('${AppContent.appName} can reserve premium flows without enabling production billing.'),
          const SizedBox(height: 12),
          Card(
            child: ListTile(
              leading: const Icon(Icons.workspace_premium_outlined),
              title: const Text('Pro plan'),
              subtitle: const Text('Human-reviewed billing is required before store release.'),
              trailing: FilledButton(
                onPressed: () async {
                  final message = await _purchaseService.startPlaceholderPurchase('Pro plan');
                  if (mounted) setState(() => _message = message);
                },
                child: const Text('Preview'),
              ),
            ),
          ),
          if (_message != null) ...[
            const SizedBox(height: 12),
            Card(
              child: ListTile(
                leading: const Icon(Icons.check_circle_outline),
                title: const Text('Success feedback'),
                subtitle: Text(_message!),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
