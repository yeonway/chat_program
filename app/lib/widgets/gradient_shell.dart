import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

class GradientShell extends StatelessWidget {
  const GradientShell({
    super.key,
    required this.child,
    this.maxWidth = 460,
    this.padding = const EdgeInsets.all(20),
  });

  final Widget child;
  final double maxWidth;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [AppTheme.backgroundTop, AppTheme.backgroundBottom],
        ),
      ),
      child: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: padding,
            child: ConstrainedBox(
              constraints: BoxConstraints(maxWidth: maxWidth),
              child: child,
            ),
          ),
        ),
      ),
    );
  }
}
