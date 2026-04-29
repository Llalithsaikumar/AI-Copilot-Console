from app.services.memory import InMemoryMemoryStore


def test_memory_store_round_trips_session_turns():
    store = InMemoryMemoryStore()
    user_id = "user-1"
    session_id = store.create_session(user_id)
    store.add_turn(
        user_id=user_id,
        session_id=session_id,
        user_input="hello",
        system_response="hi",
        mode_used="llm",
        request_id="request-1",
        metadata={"tokens": 3},
    )

    turns = store.list_turns(user_id, session_id)

    assert len(turns) == 1
    assert turns[0].user_input == "hello"
    assert turns[0].metadata == {"tokens": 3}
