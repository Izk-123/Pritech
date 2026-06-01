# accounts/middleware.py
class LastLoginIPMiddleware:
    """
    Previously updated last_login_ip on every request.
    Now only placeholder; actual IP update moved to signal.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # IP update removed – handled by signal on user_logged_in
        return response