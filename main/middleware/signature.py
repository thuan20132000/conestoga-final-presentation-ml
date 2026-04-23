# main/middleware/signature.py
from django.http import JsonResponse
from rest_framework.exceptions import AuthenticationFailed
from django.utils.translation import gettext as _

# Import your existing verifier (adjust path if needed)

import hmac
import hashlib
import time
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed

SIGNATURE_EXPIRY_TIME = 60 * 5

def verify_signature(request):
    public_key = request.headers.get('X-API-KEY')
    signature = request.headers.get('X-SIGNATURE')
    timestamp = request.headers.get('X-TIMESTAMP')
    if not (public_key and signature and timestamp):
        raise AuthenticationFailed({
            'status': False,
            'message': _('Missing required headers'),
            'code': 401
        })
    
   
    # expiry time
    if int(timestamp) > int(time.time() + SIGNATURE_EXPIRY_TIME):
        raise AuthenticationFailed({
            'status': False,
            'message': _('Signature expired'),
            'code': 401
        })
    
    secret_key = settings.SIGNATURE_SECRET_KEY.encode()
    message = f"{request.method.upper()}|{timestamp}"
    expected_signature = hmac.new(
        key=secret_key,
        msg=message.encode(),
        digestmod=hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected_signature): 
        raise AuthenticationFailed({
            'status': False,
            'message': _('Invalid signature'),
            'code': 401
        })

    return None


def signature_required_api(view_func):
    def _wrapped_view(request, *args, **kwargs):
        auth_error = verify_signature(request)
        if auth_error:
            return auth_error
        return view_func(request, *args, **kwargs)
    return _wrapped_view



class SignatureVerificationMiddleware:
    """
    Verify request signature before the request reaches the view.
    If verification fails, return 401 and do not call the view.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only check paths that should be protected by signature (e.g. API)
        if not self._path_requires_signature(request.path):
            return self.get_response(request)

        try:
            verify_signature(request)
        except AuthenticationFailed as e:
            detail = e.detail
            if isinstance(detail, dict):
                return JsonResponse(detail, status=401)
            return JsonResponse({"detail": str(detail)}, status=401)

        return self.get_response(request)

    def _path_requires_signature(self, path):
        # Require signature for all /api/... except a few paths (e.g. login, webhooks)
        if not path.startswith("/api/"):
            return False
        excluded = (
          "/webhooks/",
          "/admin/",
        )  # adjust as needed
        if any(path.startswith(prefix) for prefix in excluded):
            return False
        return True