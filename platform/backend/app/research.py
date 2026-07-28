from app.models import ResearchRun


def build_mock_plan(run: ResearchRun) -> dict:
    """Deterministic placeholder with the same shape the real agent will return."""
    return {
        "question": run.question,
        "papers": [
            {"title": "Mock evidence record", "source": "milestone-1", "approved": False},
        ],
        "hypothesis": f"A controlled intervention can improve the target metric for: {run.question}",
        "experiments": [
            {"id": "baseline", "name": "Baseline", "budget": {"epochs": 1}},
            {"id": "candidate", "name": "Candidate intervention", "budget": {"epochs": 1}},
        ],
        "provenance": {"mode": "mock", "requires_human_paper_approval": True},
    }


def render_mock_report(run: ResearchRun, plan: dict) -> str:
    experiments = "\n".join(f"- {item['name']} ({item['id']})" for item in plan["experiments"])
    return f"""# Research run: {run.id}

## Question
{run.question}

## Hypothesis
{plan['hypothesis']}

## Proposed experiments
{experiments}

## Evidence limitation
This is a deterministic Milestone 1 report. Paper retrieval and experiment metrics are mocked.
"""
