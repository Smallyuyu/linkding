import pytest
from django.test import TestCase

from bookmarks import queries
from bookmarks.models import BookmarkSearch
from bookmarks.services.search_query_parser import (
    TermExpression,
    expression_to_string,
    parse_search_query,
)
from bookmarks.tests.helpers import BookmarkFactoryMixin

ESCAPED_TERMS = [
    (r'"folder\\name guide"', r"folder\name guide"),
    (r'"line\nbreak guide"', "line\nbreak guide"),
    (r'"tab\tstop guide"', "tab\tstop guide"),
    (r'"say \"hello\" today"', 'say "hello" today'),
]


@pytest.mark.parametrize(("query", "term"), ESCAPED_TERMS)
def test_escaped_term_round_trips(query, term):
    expected = TermExpression(term)
    assert parse_search_query(query) == expected
    assert parse_search_query(expression_to_string(expected)) == expected


class SearchQueryRoundTripTestCase(TestCase, BookmarkFactoryMixin):
    def test_serialized_composite_query_selects_same_bookmarks(self):
        user = self.get_or_create_test_user()
        kept = self.setup_tag(user=user, name="kept")
        path_match = self.setup_bookmark(title=r"folder\name guide", tags=[kept])
        alternative = self.setup_bookmark(title="and guide", tags=[kept])
        self.setup_bookmark(title="folder name guide", tags=[kept])
        self.setup_bookmark(title="and guide")
        original = r'("folder\\name guide" or "and guide") #kept'
        expression = parse_search_query(original)
        serialized = expression_to_string(expression)
        self.assertEqual(parse_search_query(serialized), expression)
        for query in (original, serialized):
            with self.subTest(query=query):
                results = queries.query_bookmarks(user, user.profile, BookmarkSearch(q=query))
                self.assertCountEqual(results.values_list("pk", flat=True), [path_match.pk, alternative.pk])
