import 'package:flutter/material.dart';

import '../../core/app_content.dart';
import '../../core/widgets/status_card.dart';

class CoreFlowScreen extends StatefulWidget {
  const CoreFlowScreen({super.key});

  @override
  State<CoreFlowScreen> createState() => _CoreFlowScreenState();
}

class _CoreFlowScreenState extends State<CoreFlowScreen> {
  var _loading = false;
  String? _errorMessage;
  var _completed = false;

  Future<void> _completeAction() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
      _completed = false;
    });
    await Future<void>.delayed(const Duration(milliseconds: 350));
    setState(() {
      _loading = false;
      _completed = true;
    });
  }

  void _showSampleError() {
    setState(() {
      _loading = false;
      _completed = false;
      _errorMessage = 'Sample error state: review the local data and try again.';
    });
  }

  @override
  Widget build(BuildContext context) {
    final features = AppContent.coreFeatures;
    return Scaffold(
      appBar: AppBar(title: const Text('Core flow')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Core feature', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 8),
          Text(AppContent.idea),
          const SizedBox(height: 16),
          if (_loading)
            const StatusCard(
              title: 'Loading state',
              value: 'Preparing local sample data',
              icon: Icons.hourglass_empty,
              description: 'This preview keeps the app usable without a backend.',
            ),
          if (!_loading && features.isEmpty)
            const StatusCard(
              title: 'Empty state',
              value: 'No local items yet',
              icon: Icons.inbox_outlined,
              description: 'Add the first workflow item to begin.',
            ),
          if (!_loading && features.isNotEmpty)
            ...features.map(
              (feature) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: StatusCard(
                  title: 'Local sample data',
                  value: feature,
                  icon: Icons.checklist_outlined,
                  description: 'Adapt this item to the selected candidate before release.',
                ),
              ),
            ),
          if (_errorMessage != null) ...[
            const SizedBox(height: 4),
            StatusCard(
              title: 'Error state',
              value: 'Needs attention',
              icon: Icons.error_outline,
              description: _errorMessage,
            ),
          ],
          if (_completed) ...[
            const SizedBox(height: 4),
            const StatusCard(
              title: 'Success feedback',
              value: 'Action completed',
              icon: Icons.check_circle_outline,
              description: 'The next local step is ready on the dashboard.',
            ),
          ],
          const SizedBox(height: 12),
          FilledButton(
            onPressed: _loading ? null : _completeAction,
            child: const Text('Complete next action'),
          ),
          TextButton(
            onPressed: _loading ? null : _showSampleError,
            child: const Text('Preview error state'),
          ),
        ],
      ),
    );
  }
}
