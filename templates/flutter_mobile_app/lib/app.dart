import 'package:flutter/material.dart';

import 'core/app_content.dart';
import 'core/theme/app_theme.dart';
import 'features/home/home_screen.dart';

class ForgeTrendApp extends StatelessWidget {
  const ForgeTrendApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: AppContent.appName,
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      home: const HomeScreen(),
    );
  }
}
