from unittest.mock import patch

from django.conf import settings
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from business.models import BusinessType, Business, BusinessRoles
from staff.models import Staff, StaffSocialAccount
from subscription.models import SubscriptionPlan


_MIDDLEWARE_WITHOUT_SIGNATURE = [
    m for m in settings.MIDDLEWARE
    if m != "main.middleware.signature.SignatureVerificationMiddleware"
]


class BusinessRegisterAPITests(APITestCase):
    def setUp(self):
        self.business_type = BusinessType.objects.create(name="Nail Salon")
        self.url = "/api/business/auth/register/"

    def test_register_business_success(self):
        payload = {
            "business": {
                "name": "Test Salon",
                "business_type": str(self.business_type.id),
                "phone": "15550001",
                "email": "info1@luxenails.com",
                "city": "Toronto",
                "country": "Canada",
            },
            "owner": {
                "first_name": "John",
                "last_name": "Doe",
                "email": "info1@luxenails.com",
                "phone": "15550001",
            },
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data.get("success"))
        results = response.data.get("results") or {}


        self.assertIsNotNone(results)

        user_data = results.get("user")
        self.assertIsNotNone(user_data)
        self.assertEqual(user_data["first_name"], "John")
        self.assertEqual(user_data["last_name"], "Doe")
        self.assertEqual(user_data["email"], "info1@luxenails.com")
        self.assertEqual(user_data["phone"], "15550001")

        tokens = results.get("tokens")
        self.assertIsNotNone(tokens)
        self.assertIsNotNone(tokens.get("refresh"))
        self.assertIsNotNone(tokens.get("access"))


@override_settings(MIDDLEWARE=_MIDDLEWARE_WITHOUT_SIGNATURE)
class BusinessFacebookAuthAPITests(APITestCase):
    register_url = "/api/business/auth/facebook/register/"
    login_url = "/api/business/auth/facebook/login/"

    def setUp(self):
        self._email_patcher = patch("business.services.EmailService.send_async")
        self._email_patcher.start()
        self.addCleanup(self._email_patcher.stop)

        self.business_type = BusinessType.objects.create(name="Nail Salon")
        SubscriptionPlan.objects.get_or_create(
            name="Free Trial",
            defaults={"is_active": True, "trial_days": 14},
        )
        self.fb_profile = {
            "id": "fb_123456",
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane.doe@example.com",
        }
        self.register_payload = {
            "facebook_access_token": "fake-fb-token",
            "business": {
                "name": "Jane's Salon",
                "business_type": str(self.business_type.id),
                "phone_number": "15550002",
                "email": "salon@example.com",
                "city": "Toronto",
                "country": "Canada",
            },
            "settings": {},
        }

    @patch("business.services.BusinessFacebookAuthService._verify_facebook_token")
    def test_register_success(self, mock_verify):
        mock_verify.return_value = self.fb_profile

        response = self.client.post(self.register_url, self.register_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertTrue(response.data.get("success"))
        results = response.data["results"]
        self.assertEqual(results["user"]["email"], self.fb_profile["email"])
        self.assertIsNotNone(results["tokens"].get("access"))
        self.assertIsNotNone(results["tokens"].get("refresh"))

        staff = Staff.objects.get(email__iexact=self.fb_profile["email"])
        self.assertTrue(Business.objects.filter(staff=staff).exists())
        self.assertTrue(
            StaffSocialAccount.objects.filter(
                staff=staff, provider="facebook", provider_user_id=self.fb_profile["id"]
            ).exists()
        )

    @patch("business.services.BusinessFacebookAuthService._verify_facebook_token")
    def test_register_duplicate_email(self, mock_verify):
        mock_verify.return_value = self.fb_profile
        existing_business = Business.objects.create(
            name="Existing Salon",
            business_type=self.business_type,
            phone_number="15550099",
            email="existing@example.com",
        )
        Staff.objects.create(
            username="existing-user",
            email=self.fb_profile["email"],
            first_name="Existing",
            business=existing_business,
        )

        response = self.client.post(self.register_url, self.register_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data.get("success"))
        self.assertIn("email", response.data.get("message", "").lower())

    @patch("business.services.BusinessFacebookAuthService._verify_facebook_token")
    def test_login_success(self, mock_verify):
        mock_verify.return_value = self.fb_profile
        self.client.post(self.register_url, self.register_payload, format="json")

        response = self.client.post(
            self.login_url,
            {"facebook_access_token": "fake-fb-token"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data.get("success"))
        results = response.data["results"]
        self.assertEqual(results["user"]["email"], self.fb_profile["email"])
        self.assertIsNotNone(results["tokens"].get("access"))

    @patch("business.services.BusinessFacebookAuthService._verify_facebook_token")
    def test_register_without_email_scope(self, mock_verify):
        """User denied the Facebook email permission — should still register."""
        mock_verify.return_value = {**self.fb_profile, "email": None}

        response = self.client.post(self.register_url, self.register_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        staff = Staff.objects.get(social_accounts__provider_user_id=self.fb_profile["id"])
        self.assertEqual(staff.email, "")
        self.assertTrue(
            StaffSocialAccount.objects.filter(
                staff=staff, provider="facebook", email__isnull=True
            ).exists()
        )

    @patch("business.services.BusinessFacebookAuthService._verify_facebook_token")
    def test_login_unknown_identity(self, mock_verify):
        mock_verify.return_value = self.fb_profile

        response = self.client.post(
            self.login_url,
            {"facebook_access_token": "fake-fb-token"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data.get("success"))
        self.assertIn("no account", response.data.get("message", "").lower())


@override_settings(MIDDLEWARE=_MIDDLEWARE_WITHOUT_SIGNATURE)
class BusinessGoogleAuthAPITests(APITestCase):
    register_url = "/api/business/auth/google/register/"
    login_url = "/api/business/auth/google/login/"

    def setUp(self):
        self._email_patcher = patch("business.services.EmailService.send_async")
        self._email_patcher.start()
        self.addCleanup(self._email_patcher.stop)

        self.business_type = BusinessType.objects.create(name="Nail Salon")
        SubscriptionPlan.objects.get_or_create(
            name="Free Trial",
            defaults={"is_active": True, "trial_days": 14},
        )
        self.google_idinfo = {
            "sub": "google_sub_123",
            "email": "google.user@example.com",
            "email_verified": True,
            "given_name": "Google",
            "family_name": "User",
        }
        self.register_payload = {
            "google_id_token": "fake-google-token",
            "business": {
                "name": "Google Salon",
                "business_type": str(self.business_type.id),
                "phone_number": "15550003",
                "email": "gsalon@example.com",
                "city": "Toronto",
                "country": "Canada",
            },
            "settings": {},
        }

    @patch("business.services.BusinessGoogleAuthService._verify_google_token")
    def test_register_success(self, mock_verify):
        mock_verify.return_value = self.google_idinfo

        response = self.client.post(self.register_url, self.register_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        staff = Staff.objects.get(email__iexact=self.google_idinfo["email"])
        self.assertTrue(Business.objects.filter(staff=staff).exists())
        self.assertTrue(
            StaffSocialAccount.objects.filter(
                staff=staff, provider="google", provider_user_id=self.google_idinfo["sub"]
            ).exists()
        )

    @patch("business.services.BusinessGoogleAuthService._verify_google_token")
    def test_register_rejects_duplicate_social_account(self, mock_verify):
        mock_verify.return_value = self.google_idinfo
        self.client.post(self.register_url, self.register_payload, format="json")

        response = self.client.post(self.register_url, self.register_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already registered", response.data.get("message", "").lower())

    @patch("business.services.BusinessGoogleAuthService._verify_google_token")
    def test_login_success(self, mock_verify):
        mock_verify.return_value = self.google_idinfo
        self.client.post(self.register_url, self.register_payload, format="json")

        response = self.client.post(
            self.login_url,
            {"google_id_token": "fake-google-token"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["results"]["user"]["email"], self.google_idinfo["email"])

    @patch("business.services.BusinessGoogleAuthService._verify_google_token")
    def test_login_lazy_backfill_for_legacy_owner(self, mock_verify):
        """Owner who registered before StaffSocialAccount existed can still log in."""
        mock_verify.return_value = self.google_idinfo
        legacy_business = Business.objects.create(
            name="Legacy Salon",
            business_type=self.business_type,
            phone_number="15550098",
            email="legacy@example.com",
        )
        legacy_staff = Staff.objects.create(
            username="legacy-owner",
            email=self.google_idinfo["email"],
            first_name="Legacy",
            business=legacy_business,
        )

        response = self.client.post(
            self.login_url,
            {"google_id_token": "fake-google-token"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(
            StaffSocialAccount.objects.filter(
                staff=legacy_staff,
                provider="google",
                provider_user_id=self.google_idinfo["sub"],
            ).exists()
        )

    @patch("business.services.BusinessGoogleAuthService._verify_google_token")
    def test_login_unknown(self, mock_verify):
        mock_verify.return_value = self.google_idinfo

        response = self.client.post(
            self.login_url,
            {"google_id_token": "fake-google-token"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("no account", response.data.get("message", "").lower())


@override_settings(MIDDLEWARE=_MIDDLEWARE_WITHOUT_SIGNATURE)
class BusinessKnowledgeAPITests(APITestCase):
    def setUp(self):
        self.business_type = BusinessType.objects.create(name="Salon")
        self.business = Business.objects.create(
            name="Knowledge Salon",
            business_type=self.business_type,
            phone_number="15552222",
        )
        manager_role = BusinessRoles.objects.create(
            business=self.business,
            name="Manager",
        )
        self.user = Staff.objects.create_user(
            username="knowledge-manager",
            password="test-pass-123",
            business=self.business,
            role=manager_role,
        )
        self.client.force_authenticate(self.user)
        self.base_url = f"/api/business/{self.business.id}"
        self.query_params = f"?business_id={self.business.id}"

    @patch("business.views.BusinessKnowledgeService.reindex")
    def test_reindex_knowledge_success(self, mock_reindex):
        mock_reindex.return_value = {
            "created": 2,
            "updated": 1,
            "skipped": 0,
            "deleted": 0,
            "total_candidates": 3,
        }
        response = self.client.post(
            f"{self.base_url}/reindex-knowledge/{self.query_params}",
            {"reason": "manual"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["results"]["created"], 2)
        mock_reindex.assert_called_once()

    def test_reindex_knowledge_rejects_invalid_source_types(self):
        response = self.client.post(
            f"{self.base_url}/reindex-knowledge/{self.query_params}",
            {"source_types": "service"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertFalse(response.data["success"])

    @patch("business.views.BusinessKnowledgeService.search")
    def test_search_knowledge_success(self, mock_search):
        mock_search.return_value = [
            {"title": "Policy", "source_type": "policy", "score": 0.98, "content": "Policy"}
        ]
        response = self.client.post(
            f"{self.base_url}/search-knowledge/{self.query_params}",
            {"query": "what is your policy?", "top_k": 3},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(len(response.data["results"]), 1)
        mock_search.assert_called_once()

    def test_search_knowledge_requires_query(self):
        response = self.client.post(
            f"{self.base_url}/search-knowledge/{self.query_params}",
            {"top_k": 3},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertFalse(response.data["success"])