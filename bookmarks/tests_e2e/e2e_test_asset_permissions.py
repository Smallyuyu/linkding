from django.urls import reverse
from playwright.sync_api import expect

from bookmarks.models import BookmarkAsset
from bookmarks.tests_e2e.helpers import LinkdingE2ETestCase


class AssetPermissionsE2ETestCase(LinkdingE2ETestCase):
    def test_public_asset_stops_streaming_after_sharing_is_disabled(self):
        self.setup_temp_assets_dir()
        profile = self.get_or_create_test_user().profile
        profile.enable_sharing = True
        profile.enable_public_sharing = True
        profile.save()
        bookmark = self.setup_bookmark(shared=True)
        asset = self.setup_asset(bookmark, file="shared.html.gz", gzip=True, content_type="text/html")
        content = "<p>Snapshot shared with guests</p>"
        self.setup_asset_file(asset, content)
        self.open(reverse("linkding:bookmarks.index"))
        modal = self.open_details_modal(bookmark)
        row = modal.locator(f'[data-asset-id="{asset.id}"]')
        link = row.get_by_role("link", name="View")
        path = reverse("linkding:assets.view", args=[asset.id])
        expect(link).to_have_attribute("href", path)
        url = self.live_server_url + path
        guest = self.browser.new_context()
        try:
            response = guest.request.get(url)
            try:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.body(), content.encode())
            finally:
                response.dispose()
            profile.enable_public_sharing = False
            profile.save(update_fields=["enable_public_sharing"])
            response = guest.request.get(url)
            try:
                self.assertEqual(response.status, 404)
                self.assertNotIn(content.encode(), response.body())
            finally:
                response.dispose()
        finally:
            guest.close()
        response = self.context.request.get(url)
        try:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.body(), content.encode())
        finally:
            response.dispose()
        row.get_by_role("button", name="Remove").click()
        self.locate_confirm_dialog().get_by_text("Confirm").click()
        expect(row).to_have_count(0)
        self.assertFalse(BookmarkAsset.objects.filter(pk=asset.id).exists())
        self.assertFalse(self.has_asset_file(asset))
