from django.conf import settings
from django.utils import translation
from django.utils.translation import get_supported_language_variant


class PreferredLanguageFallbackMiddleware:
    """
    Fallback locale resolver:
    1) Keep LocaleMiddleware result when Accept-Language is supported
    2) Client preferred language (if client context exists)
    3) Business preferred language
    4) Django default language
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.default_language = (getattr(settings, "LANGUAGE_CODE", "en") or "en").split("-")[0]

    def __call__(self, request):
        fallback_language = self._resolve_fallback_language(request)
        if fallback_language:
            translation.activate(fallback_language)
            request.LANGUAGE_CODE = translation.get_language()

        response = self.get_response(request)
        translation.deactivate()
        return response

    def _resolve_fallback_language(self, request):
        if self._has_supported_accept_language(request):
            return None

        client_language = self._resolve_client_language(request)
        if client_language:
            return client_language

        business_language = self._resolve_business_language(request)
        if business_language:
            return business_language

        return self.default_language

    def _has_supported_accept_language(self, request):
        header = request.headers.get("Accept-Language", "")
        if not header:
            return False

        candidates = []
        for part in header.split(","):
            code = part.split(";")[0].strip()
            if code:
                candidates.append(code)

        for code in candidates:
            try:
                get_supported_language_variant(code)
                return True
            except LookupError:
                continue
        return False

    def _normalize_language(self, code):
        if not code:
            return None
        try:
            return get_supported_language_variant(code)
        except LookupError:
            return None

    def _extract_param(self, request, keys):
        for key in keys:
            value = request.headers.get(key)
            if value:
                return value

        for key in keys:
            value = request.query_params.get(key) if hasattr(request, "query_params") else request.GET.get(key)
            if value:
                return value

        if hasattr(request, "data"):
            try:
                for key in keys:
                    value = request.data.get(key)
                    if value:
                        return value
            except Exception:
                return None
        return None

    def _resolve_client_language(self, request):
        client_id = self._extract_param(request, ["X-Client-Id", "client_id", "client"])
        if not client_id:
            return None

        from client.models import Client

        client = (
            Client.objects.select_related("primary_business__settings")
            .filter(pk=client_id, is_deleted=False)
            .first()
        )
        if not client:
            return None

        client_language = self._normalize_language(getattr(client, "preferred_language", None))
        if client_language:
            return client_language

        settings_obj = getattr(getattr(client, "primary_business", None), "settings", None)
        return self._normalize_language(getattr(settings_obj, "preferred_language", None))

    def _resolve_business_language(self, request):
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            settings_obj = getattr(getattr(user, "business", None), "settings", None)
            language = self._normalize_language(getattr(settings_obj, "preferred_language", None))
            if language:
                return language

        business_id = self._extract_param(request, ["X-Business-Id", "business_id", "business"])
        if not business_id:
            return None

        from business.models import BusinessSettings

        settings_obj = BusinessSettings.objects.filter(business_id=business_id, is_deleted=False).first()
        return self._normalize_language(getattr(settings_obj, "preferred_language", None))
