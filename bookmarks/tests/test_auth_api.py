from django.test import RequestFactory
from django.urls import reverse
from rest_framework import exceptions, status

from bookmarks.api.auth import LinkdingTokenAuthentication
from bookmarks.tests.helpers import BookmarkFactoryMixin, LinkdingApiTestCase


class AuthApiTestCase(LinkdingApiTestCase, BookmarkFactoryMixin):
    def authenticate(self, keyword):
        self.api_token = self.setup_api_token()
        self.client.credentials(HTTP_AUTHORIZATION=f"{keyword} {self.api_token.key}")

    def test_auth_with_token_keyword(self):
        self.authenticate("Token")

        url = reverse("linkding:user-profile")
        self.get(url, expected_status_code=status.HTTP_200_OK)

    def test_auth_with_bearer_keyword(self):
        self.authenticate("Bearer")

        url = reverse("linkding:user-profile")
        self.get(url, expected_status_code=status.HTTP_200_OK)

    def test_auth_with_unknown_keyword(self):
        self.authenticate("Key")

        url = reverse("linkding:user-profile")
        self.get(url, expected_status_code=status.HTTP_401_UNAUTHORIZED)

    def test_auth_skips_absent_and_unsupported_schemes(self):
        url = reverse("linkding:user-profile")
        user = self.get_or_create_test_user()
        self.client.force_login(user)
        authenticator = LinkdingTokenAuthentication()
        for headers in ({}, {"HTTP_AUTHORIZATION": "Key unused"}):
            with self.subTest(headers=headers):
                request = RequestFactory().get(url, **headers)
                self.assertIsNone(authenticator.authenticate(request))
                self.client.credentials(**headers)
                response = self.get(url)
                self.assertEqual(response.wsgi_request.user, user)

    def test_auth_rejects_invalid_token_headers(self):
        url = reverse("linkding:user-profile")
        token = self.setup_api_token()
        authenticator = LinkdingTokenAuthentication()
        headers = {
            "missing": ("Bearer", "No credentials provided"),
            "extra": (f"Token {token.key} extra", "should not contain spaces"),
            "encoding": (b"Token \xff", "should not contain invalid characters"),
            "unknown": (f"Token {'0' * 40}", "Invalid token"),
        }
        for name, (header, message) in headers.items():
            with self.subTest(rule=name):
                request = RequestFactory().get(url, HTTP_AUTHORIZATION=header)
                with self.assertRaisesMessage(exceptions.AuthenticationFailed, message):
                    authenticator.authenticate(request)
                self.client.credentials(HTTP_AUTHORIZATION=header)
                response = self.get(url, expected_status_code=status.HTTP_401_UNAUTHORIZED)
                self.assertContains(response, message, status_code=status.HTTP_401_UNAUTHORIZED)
                self.assertEqual(response.data["detail"].code, "authentication_failed")

    def test_auth_accepts_mixed_case_scheme_and_identifies_user(self):
        url = reverse("linkding:user-profile")
        self.authenticate("bEaReR")
        request = RequestFactory().get(url, HTTP_AUTHORIZATION=f"bEaReR {self.api_token.key}")
        self.assertEqual(LinkdingTokenAuthentication().authenticate(request), (self.api_token.user, self.api_token))
        response = self.get(url)
        self.assertEqual(response.wsgi_request.user, self.api_token.user)

    def test_malformed_token_is_rejected_with_valid_session(self):
        url = reverse("linkding:user-profile")
        user = self.get_or_create_test_user()
        self.client.force_login(user)
        self.assertEqual(self.get(url).wsgi_request.user, user)
        self.client.credentials(HTTP_AUTHORIZATION="Token")
        response = self.get(url, expected_status_code=status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["detail"].code, "authentication_failed")
