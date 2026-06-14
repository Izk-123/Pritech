from .models import PortfolioSettings

def portfolio_settings(request):
    """Make portfolio settings available globally to all templates."""
    return {'portfolio_settings': PortfolioSettings.get()}