"""Looks up which planted city story, if any, is in effect."""

from datetime import date

from synthetic_data.calibration import CITY_STORIES, CityStory


def city_story_in_effect(city: str, day: date) -> CityStory:
    """The city's story once it has started; otherwise a story that changes nothing.

    Returning a neutral story instead of None means callers can always
    multiply by its effects without checking first.
    """
    for story in CITY_STORIES:
        if story.city == city and day >= story.starts:
            return story
    return CityStory(city, day, "nothing unusual")
