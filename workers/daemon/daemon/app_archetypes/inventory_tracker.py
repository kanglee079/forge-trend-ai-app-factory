INVENTORY_TRACKER_ARCHETYPE = {
    "id": "inventory_tracker",
    "screens": ["item list", "stock adjustment", "low stock alert", "history", "settings"],
    "entities": ["InventoryItem", "StockMovement", "LowStockRule"],
    "actions": ["Add item", "Adjust stock", "Mark low stock", "Review movement history"],
    "sample_data": [{"name": "Áo thun", "stock": 12}],
    "tests": ["add item", "adjust stock", "low stock state appears"],
    "store_positioning": {"short_vi": "Theo dõi tồn kho nhỏ gọn cho người bán hàng online."},
    "quality_checks": ["has_crud_action", "has_low_stock_state", "has_history"],
}
