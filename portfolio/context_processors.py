from .models import PortfolioSettings

def portfolio_settings(request):
    return {'portfolio_settings': PortfolioSettings.get()}