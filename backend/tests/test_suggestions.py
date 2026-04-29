from app.services.suggestions import suggest_queries_for_document


def test_suggestions_are_derived_from_uploaded_document_content():
    suggestions = suggest_queries_for_document(
        "profile.pdf",
        "Contact: user@example.com\nSkills: Python, React\nExperience: Developer",
    )

    assert len(suggestions) == 3
    assert suggestions[0] == "Find the email address in profile"
    assert "profile" in suggestions[1]
    assert "profile" in suggestions[2]


def test_suggestions_fall_back_to_general_document_prompts():
    suggestions = suggest_queries_for_document("notes.md", "A short plain note.")

    assert suggestions == [
        "Summarize notes",
        "Extract the key facts from notes",
        "List important follow-up questions for notes",
    ]
