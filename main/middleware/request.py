from django.utils import timezone

class RequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Example: read from user profile or session
        # read the timezone from header 'X-Timezone'
        user_tz = request.headers.get('X-Timezone', 'UTC')
        
        timezone.activate(user_tz)
        response = self.get_response(request)
        timezone.deactivate()
        return response