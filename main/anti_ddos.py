from django.http import HttpResponseForbidden
import time

class AntiDDoSMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.request_count = {}

    def __call__(self, request):
        ip = request.META.get('REMOTE_ADDR')
        current_time = int(time.time())

        # Track requests per IP
        if ip not in self.request_count:
            self.request_count[ip] = []

        # Remove old timestamps
        self.request_count[ip] = [
            t for t in self.request_count[ip] 
            if t > current_time - 60  # 60-second window
        ]

        # Allow max 100 requests per minute per IP
        if len(self.request_count[ip]) >= 100:
            return HttpResponseForbidden("Too many requests")

        self.request_count[ip].append(current_time)
        return self.get_response(request)