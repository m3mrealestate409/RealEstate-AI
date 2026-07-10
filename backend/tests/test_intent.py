"""
Regression tests for project entity linking (the "gic" and "Green Valley" bugs).
These cover the pure helpers so they run without a database.
"""
from app.services.intent import FUZZY_THRESHOLD, _candidate_phrase, _fuzzy_score


def test_candidate_phrase_strips_intent_words():
    # "price" is an intent keyword → removed, leaving the project-like word.
    assert _candidate_phrase("gic price") == "gic"


def test_candidate_phrase_bare_followup_is_empty():
    # A bare follow-up has no project-like word → empty → caller uses memory.
    assert _candidate_phrase("possession?") == ""
    assert _candidate_phrase("payment plan") == ""


def test_candidate_phrase_keeps_project_name():
    assert _candidate_phrase("palm greens possession") == "palm greens"


def test_typo_matches_correct_project():
    # Misspellings should score above the fuzzy threshold for the right project.
    assert _fuzzy_score("gold hils", "golf hills") >= FUZZY_THRESHOLD
    assert _fuzzy_score("palm grean", "palm greens") >= FUZZY_THRESHOLD


def test_unknown_word_matches_nothing():
    # "gic" is not a typo of any project → below threshold for all → unknown.
    for name in ("golf hills", "green valley", "palm greens"):
        assert _fuzzy_score("gic", name) < FUZZY_THRESHOLD


def test_correct_project_scores_higher_than_confusable():
    # The Green Valley bug is prevented at the exact-match layer (whole-word).
    # For fuzzy, the invariant that matters: the RIGHT project scores strictly
    # higher than a confusable one, so link_projects picks the correct best.
    assert _fuzzy_score("palm greens", "palm greens") > _fuzzy_score("palm greens", "green valley")
    assert _fuzzy_score("greens", "palm greens") > _fuzzy_score("greens", "green valley")
