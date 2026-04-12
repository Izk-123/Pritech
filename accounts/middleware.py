class LastLoginIPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
            if ip and request.user.last_login_ip != ip:
                request.user.last_login_ip = ip.split(',')[0].strip()
                request.user.save(update_fields=['last_login_ip'])
        return response
