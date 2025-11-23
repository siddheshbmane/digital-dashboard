"""
Currency formatting utilities for the dashboard.
"""

def format_currency(amount, currency="INR"):
    """
    Format amount as currency with proper symbol and formatting.
    
    Args:
        amount: Numeric amount to format
        currency: Currency code (default: INR)
    
    Returns:
        Formatted currency string
    """
    if currency == "INR":
        # Indian Rupee formatting with ₹ symbol
        return f"₹{amount:,.2f}"
    elif currency == "USD":
        return f"${amount:,.2f}"
    else:
        return f"{currency} {amount:,.2f}"

def get_currency_symbol(currency="INR"):
    """
    Get currency symbol for the specified currency.
    
    Args:
        currency: Currency code (default: INR)
    
    Returns:
        Currency symbol string
    """
    symbols = {
        "INR": "₹",
        "USD": "$",
        "EUR": "€",
        "GBP": "£"
    }
    return symbols.get(currency, currency)
