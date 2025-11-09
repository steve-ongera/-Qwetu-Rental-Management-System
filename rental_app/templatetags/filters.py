from django import template
from datetime import datetime

register = template.Library()

@register.filter
def sum_amount(payments):
    """Sums the 'amount' attribute of a queryset or list of payments."""
    if not payments:
        return 0
    return sum(getattr(p, 'amount', 0) for p in payments)

@register.filter
def filter_by_date(payments, date_str):
    """
    Filters payments by a date string (YYYY-MM-DD).
    Usage in template: {{ payments|filter_by_date:"2025-11-01" }}
    """
    if not payments or not date_str:
        return payments
    try:
        filter_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        return [p for p in payments if getattr(p, 'payment_date', None) == filter_date]
    except ValueError:
        return payments
