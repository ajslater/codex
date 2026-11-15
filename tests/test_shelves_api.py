"""HTTP-level tests for the shelves API."""

from django.contrib.auth.models import Group, User
from django.test import Client

from codex.models import Library, Shelf
from codex.models.auth import GroupAuth
from tests.shelf_fixtures import (
    COLLECTIONS,
    HTTP_BAD_REQUEST,
    HTTP_CREATED,
    HTTP_FORBIDDEN,
    HTTP_NO_CONTENT,
    HTTP_NOT_FOUND,
    HTTP_OK,
    LIST_URL,
    TEST_PASSWORD,
    TMP_DIR,
    ShelfTestCase,
    detail_url,
    items_url,
    make_chain,
    post_json,
    v4,
)


class ShelvesAPITestCase(ShelfTestCase):
    """Shelf CRUD and bulk membership over HTTP."""

    def test_create_list_rename_delete(self):
        """A shelf can be created, listed, renamed and deleted."""
        created = post_json(self.client, "post", LIST_URL, {"name": "  Want to Read "})
        assert created.status_code == HTTP_CREATED, created.content
        body = v4(created)
        assert body["name"] == "Want to Read"
        assert set(body["items"]) == COLLECTIONS
        shelf_pk = body["pk"]

        listed = v4(self.client.get(LIST_URL))["shelves"]
        assert [(s["pk"], s["name"]) for s in listed] == [(shelf_pk, "Want to Read")]

        renamed = post_json(
            self.client, "patch", detail_url(shelf_pk), {"name": "Later"}
        )
        assert renamed.status_code == HTTP_OK, renamed.content
        assert v4(renamed) == {"pk": shelf_pk, "name": "Later"}

        deleted = self.client.delete(detail_url(shelf_pk))
        assert deleted.status_code == HTTP_NO_CONTENT
        assert self.client.delete(detail_url(shelf_pk)).status_code == HTTP_NO_CONTENT
        assert not Shelf.objects.filter(pk=shelf_pk).exists()

    def test_names_are_unique_per_user_and_not_blank(self):
        """Duplicate and blank names are refused; another user may reuse a name."""
        self._shelf("Dupe")
        other = User.objects.create_user(username="other", password=TEST_PASSWORD)
        self._shelf("Mine", user=other)

        dupe = post_json(self.client, "post", LIST_URL, {"name": "Dupe"})
        assert dupe.status_code == HTTP_BAD_REQUEST
        blank = post_json(self.client, "post", LIST_URL, {"name": "   "})
        assert blank.status_code == HTTP_BAD_REQUEST
        reuse = post_json(self.client, "post", LIST_URL, {"name": "Mine"})
        assert reuse.status_code == HTTP_CREATED

        second = self._shelf("Second")
        clash = post_json(self.client, "patch", detail_url(second.pk), {"name": "Dupe"})
        assert clash.status_code == HTTP_BAD_REQUEST

    def test_bulk_add_and_remove_items(self):
        """One PATCH adds and removes across collections, idempotently."""
        shelf = self._shelf()
        payload = {
            "add": {
                "series": [self.s1.pk, self.s2.pk],
                "comics": [self.c1.pk],
            }
        }
        first = post_json(self.client, "patch", items_url(shelf.pk), payload)
        assert first.status_code == HTTP_OK, first.content
        assert v4(first) == {"added": 3, "removed": 0}
        again = post_json(self.client, "patch", items_url(shelf.pk), payload)
        assert v4(again) == {"added": 0, "removed": 0}

        swap = post_json(
            self.client,
            "patch",
            items_url(shelf.pk),
            {"remove": {"series": [self.s2.pk]}, "add": {"publishers": [self.p1.pk]}},
        )
        assert v4(swap) == {"added": 1, "removed": 1}

        listed = v4(self.client.get(LIST_URL))["shelves"][0]["items"]
        assert listed["series"] == [self.s1.pk]
        assert listed["comics"] == [self.c1.pk]
        assert listed["publishers"] == [self.p1.pk]
        assert listed["volumes"] == []

    def test_add_skips_missing_and_hidden_targets(self):
        """Targets that do not exist or that the ACL hides are not shelved."""
        readers = Group.objects.create(name="readers")
        GroupAuth.objects.create(group=readers)
        private_dir = TMP_DIR / "private"
        private_dir.mkdir(parents=True, exist_ok=True)
        private_library = Library.objects.create(path=str(private_dir))
        private_library.groups.add(readers)
        *_, hidden_comic = make_chain(private_library, "9")

        shelf = self._shelf()
        bogus_pk = hidden_comic.pk + 99999
        response = post_json(
            self.client,
            "patch",
            items_url(shelf.pk),
            {"add": {"comics": [self.c1.pk, hidden_comic.pk, bogus_pk]}},
        )
        assert response.status_code == HTTP_OK, response.content
        assert v4(response)["added"] == 1
        assert list(self._target_ids(shelf)) == [self.c1.pk]

    def test_unknown_collection_is_rejected(self):
        """Only the seven browse collections can be shelved."""
        shelf = self._shelf()
        response = post_json(
            self.client, "patch", items_url(shelf.pk), {"add": {"libraries": [1]}}
        )
        assert response.status_code == HTTP_BAD_REQUEST
        assert not self._target_ids(shelf)

    def test_other_users_shelves_are_invisible_and_untouchable(self):
        """Another user's shelf is not listed and reads as missing."""
        other = User.objects.create_user(username="other", password=TEST_PASSWORD)
        theirs = self._shelf("Theirs", user=other)
        self._put(theirs, "series", self.s1.pk)

        assert v4(self.client.get(LIST_URL))["shelves"] == []
        rename = post_json(self.client, "patch", detail_url(theirs.pk), {"name": "X"})
        assert rename.status_code == HTTP_NOT_FOUND
        add = post_json(
            self.client,
            "patch",
            items_url(theirs.pk),
            {"add": {"comics": [self.c1.pk]}},
        )
        assert add.status_code == HTTP_NOT_FOUND
        assert self.client.delete(detail_url(theirs.pk)).status_code == HTTP_NO_CONTENT
        theirs.refresh_from_db()
        assert theirs.name == "Theirs"
        assert len(self._target_ids(theirs)) == 1

    def test_anonymous_forbidden(self):
        """Logged-out clients must not reach the shelves surface."""
        shelf = self._shelf()
        anon = Client()
        assert anon.get(LIST_URL).status_code == HTTP_FORBIDDEN
        assert post_json(anon, "post", LIST_URL, {"name": "x"}).status_code == (
            HTTP_FORBIDDEN
        )
        assert post_json(
            anon, "patch", detail_url(shelf.pk), {"name": "x"}
        ).status_code == (HTTP_FORBIDDEN)
        assert anon.delete(detail_url(shelf.pk)).status_code == HTTP_FORBIDDEN
        add = post_json(anon, "patch", items_url(shelf.pk), {"add": {"comics": [1]}})
        assert add.status_code == HTTP_FORBIDDEN

    def test_deleting_a_target_removes_its_shelf_items(self):
        """The post-delete signal drops items that pointed at a deleted row."""
        shelf = self._shelf()
        self._put(shelf, "series", self.s2.pk)
        self._put(shelf, "series", self.s1.pk)
        self.s2.delete()
        assert list(self._target_ids(shelf)) == [self.s1.pk]
