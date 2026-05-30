"""Unit tests for table-view column parsing and the issue-cell formatter."""

from decimal import Decimal

from django.test import TestCase

from codex.serializers.browser.page import _format_issue
from codex.serializers.browser.settings import BrowserPageInputSerializer


class FormatIssueTestCase(TestCase):
    """Pin the compound issue-cell formatter."""

    def test_number_only(self):
        assert _format_issue(1, "") == {"number": "1", "suffix": ""}

    def test_number_and_suffix(self):
        assert _format_issue(1, "a") == {"number": "1", "suffix": "a"}

    def test_decimal_strips_trailing_zeros(self):
        # "1.50" → "1.5"; "1.00" → "1".
        assert _format_issue(Decimal("1.50"), "") == {"number": "1.5", "suffix": ""}
        assert _format_issue(Decimal("1.00"), "b") == {"number": "1", "suffix": "b"}

    def test_missing_number(self):
        assert _format_issue(None, "a") == {"number": "", "suffix": "a"}

    def test_missing_both(self):
        assert _format_issue(None, "") == {"number": "", "suffix": ""}

    def test_none_suffix_coerced_to_empty(self):
        assert _format_issue(1, None) == {"number": "1", "suffix": ""}


class BrowserPageInputColumnsTestCase(TestCase):
    """Validate the ``columns=`` query-param parser."""

    def test_empty_returns_empty_tuple(self):
        s = BrowserPageInputSerializer(data={"columns": ""})
        assert s.is_valid(), s.errors
        assert s.validated_data["columns"] == ()

    def test_csv_parsed_to_tuple(self):
        s = BrowserPageInputSerializer(data={"columns": "cover,name,issue"})
        assert s.is_valid(), s.errors
        assert s.validated_data["columns"] == ("cover", "name", "issue")

    def test_whitespace_trimmed(self):
        s = BrowserPageInputSerializer(data={"columns": " cover , name "})
        assert s.is_valid(), s.errors
        assert s.validated_data["columns"] == ("cover", "name")

    def test_unknown_key_rejected(self):
        s = BrowserPageInputSerializer(data={"columns": "cover,phantom_column"})
        assert not s.is_valid()
        assert "columns" in s.errors
