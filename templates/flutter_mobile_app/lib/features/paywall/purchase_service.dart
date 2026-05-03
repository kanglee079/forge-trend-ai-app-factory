class PurchaseService {
  const PurchaseService();

  bool get productionBillingEnabled => false;

  Future<String> startPlaceholderPurchase(String planName) async {
    await Future<void>.delayed(const Duration(milliseconds: 300));
    return 'Purchase placeholder for $planName. Add reviewed store billing before release.';
  }
}
