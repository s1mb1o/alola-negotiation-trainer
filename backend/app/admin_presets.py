"""Approved context labels. Objectives and economics remain in immutable scenarios."""

CONTEXTS = {
    "supplier_001": "equipment",
    "supplier_integration_ru": "equipment",
    "supplier_integration_en": "equipment",
    "saas_subscription_ru": "software",
    "saas_subscription_en": "software",
    "freight_contract_ru": "logistics",
    "freight_contract_en": "logistics",
    "office_lease_ru": "property",
    "office_lease_en": "property",
}

LABELS = {
    "ru": {
        "equipment": ("Промышленность", "Поставка промышленных компьютеров"),
        "software": ("IT", "Годовая подписка на сервис"),
        "logistics": ("Логистика", "Срочная грузовая перевозка"),
        "property": ("Недвижимость", "Годовая аренда офиса"),
    },
    "en": {
        "equipment": ("Industry", "Industrial computer supply"),
        "software": ("IT", "Annual service subscription"),
        "logistics": ("Logistics", "Urgent freight transport"),
        "property": ("Real estate", "Annual office lease"),
    },
}
