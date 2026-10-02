from datetime import date, datetime, timezone

from app.rag.note_index import SearchFilters, point_id, search_filter


def test_the_same_note_always_gets_the_same_point_id():
    assert point_id("note_job_1_1", "Replaced two breakers.") == point_id("note_job_1_1", "Replaced two breakers.")


def test_editing_a_note_gives_it_a_new_point_id():
    assert point_id("note_job_1_1", "Replaced two breakers.") != point_id("note_job_1_1", "Replaced three breakers.")


def test_no_filters_means_search_everything():
    assert search_filter(SearchFilters()) is None


def test_each_given_filter_becomes_a_condition():
    query_filter = search_filter(SearchFilters(city="Bellevue", service="Panel Upgrade"))

    assert {condition.key: condition.match.value for condition in query_filter.must} == {
        "city": "Bellevue",
        "service": "Panel Upgrade",
    }


def test_a_date_range_filters_on_when_the_note_was_written():
    query_filter = search_filter(SearchFilters(written_from=date(2026, 1, 1)))
    [condition] = query_filter.must

    assert condition.key == "written_on"
    assert condition.range.gte == datetime(2026, 1, 1, tzinfo=timezone.utc)  # Qdrant parses the text
    assert condition.range.lte is None
