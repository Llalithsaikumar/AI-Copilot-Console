from app.services.memory import SQLiteMemoryStore


def test_memory_store_round_trips_session_turns(tmp_path):
    store = SQLiteMemoryStore(tmp_path / "memory.sqlite3")
    store.add_turn(
        account_id="acc",
        session_id="session-1",
        user_input="hello",
        system_response="hi",
        mode_used="llm",
        request_id="request-1",
        metadata={"tokens": 3},
    )

    turns = store.list_turns("acc", "session-1")

    assert len(turns) == 1
    assert turns[0].user_input == "hello"
    assert turns[0].metadata == {"tokens": 3}
