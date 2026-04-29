from app.services.agent import AgentPlanner, SafeCalculator


def test_safe_calculator_allows_arithmetic():
    calculator = SafeCalculator()

    assert calculator.evaluate("2 + 3 * 4") == 14


def test_planner_adds_risk_extraction_step():
    planner = AgentPlanner()

    plan = planner.plan("Analyze the report and extract risks", has_context=True)

    assert [step["tool"] for step in plan] == ["summarize_context", "extract_risks"]

