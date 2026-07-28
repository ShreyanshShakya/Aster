"""Deterministic, evidence-labeled Milestone 2 research planning pipeline."""
import math
import re
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.literature import RetrievedPaper, retrieve_literature
from app.models import Artifact, ExperimentPlan, Hypothesis, JobStatus, Knowledge, Paper, Report, ResearchEvent, ResearchPaper, ResearchRun
from app.storage import put_text


def event(db: Session, run: ResearchRun, stage: str, message: str, data: dict | None = None) -> None:
    db.add(ResearchEvent(research_run_id=run.id, stage=stage, message=message, data=data or {}))
    db.commit()


def intent(question: str) -> dict:
    text = question.lower()
    segmentation = "segment" in text
    classification = any(term in text for term in ("classif", "diagnos", "detect"))
    medical = any(term in text for term in ("tumor", "mri", "brain", "medical", "brats"))
    return {"domain": "Medical Imaging" if medical else "Machine Learning", "task": "Segmentation" if segmentation else "Classification" if classification else "Research investigation", "modality": "MRI" if any(term in text for term in ("mri", "brain", "brats")) else "Unspecified", "possible_models": ["SwinUNETR", "nnU-Net"] if segmentation and medical else ["U-Net", "Vision Transformer"] if segmentation else ["ResNet", "Vision Transformer"]}


def rank(question: str, papers: list[RetrievedPaper]) -> list[tuple[RetrievedPaper, float]]:
    terms = {term for term in re.findall(r"[a-z0-9]+", question.lower()) if len(term) > 2}
    current_year = datetime.now(timezone.utc).year
    scored = []
    for paper in papers:
        corpus = f"{paper.title} {paper.abstract or ''}".lower()
        overlap = sum(term in corpus for term in terms) / max(len(terms), 1)
        citations = min(math.log1p(paper.cited_by_count) / 10, 1)
        recency = max(0, 1 - ((current_year - (paper.publication_year or current_year)) / 15))
        scored.append((paper, round(0.65 * overlap + 0.25 * citations + 0.10 * recency, 4)))
    return sorted(scored, key=lambda item: item[1], reverse=True)[:10]


def persist_paper(db: Session, paper: RetrievedPaper) -> Paper:
    stored = db.scalar(select(Paper).where(Paper.source == paper.source, Paper.external_id == paper.external_id))
    if stored is None:
        stored = Paper(source=paper.source, external_id=paper.external_id, doi=paper.doi, title=paper.title, authors=paper.authors, publication_year=paper.publication_year, abstract=paper.abstract, url=paper.url, cited_by_count=paper.cited_by_count, raw_metadata=paper.raw_metadata)
        db.add(stored); db.flush()
    return stored


def recommendations(info: dict) -> tuple[list[dict], list[str], dict]:
    if info["task"] == "Segmentation" and info["domain"] == "Medical Imaging":
        return ([{"name": "BraTS", "reason": "Public multi-modal brain-tumor MRI benchmark.", "preprocessing": "Resample, normalize per modality, use foreground-aware patches."}], ["Dice", "Hausdorff distance (95th percentile)", "sensitivity"], {"model": "SwinUNETR", "optimizer": "AdamW", "loss": "DiceFocalLoss", "epochs": 200, "learning_rate": 0.0001, "patch_size": [128, 128, 128], "batch_size": 2, "hardware": "Single GPU with at least 24 GB VRAM recommended", "bottleneck": "3D patch memory and I/O"})
    return ([{"name": "Dataset selection required", "reason": "Question does not identify a benchmark.", "preprocessing": "Define task-specific splits and preprocessing before execution."}], ["accuracy", "precision", "recall", "F1"], {"model": info["possible_models"][0], "optimizer": "AdamW", "epochs": 50, "learning_rate": 0.0003, "hardware": "Single CPU/GPU baseline", "bottleneck": "Dataset definition is unresolved"})


def experiment_design(info: dict, metrics: list[str], configuration: dict) -> dict:
    """A machine-readable hand-off contract for a future execution adapter."""
    primary_metric = metrics[0]
    baseline = "nnU-Net or a documented U-Net baseline" if info["task"] == "Segmentation" and info["domain"] == "Medical Imaging" else "a documented baseline using the same data split"
    return {
        "primary_metric": primary_metric,
        "baseline": {"name": baseline, "purpose": "Establish the fixed-compute reference result."},
        "intervention": {"name": configuration["model"], "purpose": f"Evaluate the proposed {configuration['model']} configuration against the baseline."},
        "controls": [
            "Use identical train/validation/test splits for every arm.",
            "Fix preprocessing, augmentation policy, epoch budget, and seed policy before running.",
            "Run each arm with at least three seeds before interpreting a difference.",
        ],
        "acceptance_criterion": f"Report mean and variance of {primary_metric}; treat an improvement as preliminary until repeated runs and expert review are complete.",
        "execution_status": "planned — not yet submitted to a training worker",
    }


def literature_synthesis(question: str, ranked: list[tuple[RetrievedPaper, float]]) -> dict:
    """Create an inspectable, conservative synthesis from available abstracts only."""
    abstract_papers = [(paper, score) for paper, score in ranked if paper.abstract]
    snippets: list[dict] = []
    for paper, score in abstract_papers[:3]:
        # First complete-looking sentence is displayed as an evidence excerpt, not a claim by Aster.
        first_sentence = re.split(r"(?<=[.!?])\s+", paper.abstract.strip())[0].strip()
        snippets.append({"title": paper.title, "source": paper.source, "score": score, "excerpt": first_sentence[:500]})
    return {
        "question": question,
        "papers_ranked": len(ranked),
        "abstracts_available": len(abstract_papers),
        "summary": (
            f"Aster ranked {len(ranked)} papers for this question; {len(abstract_papers)} included an abstract that can be inspected locally. "
            "The proposal uses task intent and these metadata/abstract records for planning only. "
            "It does not infer experimental results, methods, or causal conclusions from papers without reviewing their full text."
        ),
        "evidence_excerpts": snippets,
        "limitations": "Abstract excerpts are source text supplied by the metadata provider. Validate every scientific claim against the linked primary paper before execution or publication.",
    }


def run_research_plan(db: Session, run: ResearchRun) -> dict:
    event(db, run, "intent", "Analyzing research intent")
    info = intent(run.question)
    event(db, run, "literature", "Retrieving real scholarly metadata from configured providers")
    ranked = rank(run.question, retrieve_literature(run.question))
    if not ranked:
        raise RuntimeError("No literature metadata was returned. Check network access or configure OPENALEX_API_KEY.")
    event(db, run, "ranking", f"Ranked {len(ranked)} deduplicated papers", {"count": len(ranked)})
    evidence = []
    for position, (paper, score) in enumerate(ranked, start=1):
        stored = persist_paper(db, paper)
        db.add(ResearchPaper(research_run_id=run.id, paper_id=stored.id, rank=position, score=score, relevance={"source": paper.source, "abstract_available": bool(paper.abstract)}))
        extraction = {"problem": run.question, "method": "Not inferred without full text", "dataset": "Not inferred without full text", "metrics": "Not inferred without full text", "results": "Not inferred without full text", "limitations": "Metadata/abstract evidence only; validate against the primary paper."}
        db.add(Knowledge(research_run_id=run.id, paper_id=stored.id, extracted=extraction))
        evidence.append({"title": paper.title, "year": paper.publication_year, "url": paper.url, "source": paper.source, "score": score, "abstract_available": bool(paper.abstract)})
    db.commit()
    event(db, run, "knowledge", "Stored ranked literature and metadata-limited knowledge extraction")
    synthesis = literature_synthesis(run.question, ranked)
    db.add(Knowledge(research_run_id=run.id, paper_id=None, extracted={"kind": "literature_synthesis", **synthesis}))
    db.commit()
    event(db, run, "synthesis", f"Synthesized {synthesis['abstracts_available']} available abstracts conservatively")
    datasets, metrics, configuration = recommendations(info)
    design = experiment_design(info, metrics, configuration)
    configuration = {**configuration, "experiment_design": design}
    statement = f"For {run.question}, a controlled comparison of {info['possible_models'][0]} against a baseline will improve the primary metric under a fixed compute budget."
    hypothesis = Hypothesis(research_run_id=run.id, statement=statement, rationale="Derived from task intent and ranked metadata; this is a planning hypothesis, not a literature-backed causal claim.", expected_improvement="To be estimated after a baseline is defined.", risk="Retrieved metadata may not contain methods, data, or results.", novelty="Requires expert review against full text.", evidence={"paper_count": len(evidence), "sources": sorted({item['source'] for item in evidence})})
    db.add(hypothesis); db.flush()
    plan = ExperimentPlan(research_run_id=run.id, configuration=configuration, datasets=datasets, metrics=metrics, resource_estimate={"evidence_limit": "planning estimate only", "retrieved_papers": len(evidence)})
    db.add(plan); db.flush()
    summary = {"intent": info, "hypothesis": {"id": str(hypothesis.id), "statement": statement, "rationale": hypothesis.rationale, "risk": hypothesis.risk}, "datasets": datasets, "metrics": metrics, "configuration": configuration, "experiment_design": design, "papers": evidence, "literature_synthesis": synthesis, "evidence_limit": "Paper metadata and available abstracts only; no full-text claims were inferred."}
    run.plan = summary
    prefix = f"runs/{run.id}/research-engine"
    markdown = f"# Research proposal\n\n## Question\n{run.question}\n\n## Literature synthesis\n{synthesis['summary']}\n\n### Inspectable abstract excerpts\n" + "\n".join(f"- **{item['title']}** ({item['source']}): {item['excerpt']}" for item in synthesis["evidence_excerpts"]) + f"\n\n### Limitation\n{synthesis['limitations']}\n\n## Hypothesis\n{statement}\n\n## Experiment design\n- Baseline: {design['baseline']['name']}\n- Intervention: {design['intervention']['name']}\n- Primary metric: {design['primary_metric']}\n- Acceptance: {design['acceptance_criterion']}\n\n## Controls\n" + "\n".join(f"- {control}" for control in design["controls"]) + "\n\n## Datasets\n" + "\n".join(f"- {item['name']}: {item['reason']}" for item in datasets) + "\n\n## Metrics\n" + "\n".join(f"- {metric}" for metric in metrics) + "\n\n## Evidence limit\n" + summary["evidence_limit"]
    markdown_artifact = Artifact(storage_key=put_text(f"{prefix}/proposal.md", markdown, "text/markdown"), media_type="text/markdown")
    json_artifact = Artifact(storage_key=put_text(f"{prefix}/proposal.json", json.dumps(summary, indent=2), "application/json"), media_type="application/json")
    db.add_all([markdown_artifact, json_artifact]); db.flush()
    db.add(Report(research_run_id=run.id, markdown_artifact_id=markdown_artifact.id, json_artifact_id=json_artifact.id))
    run.status = JobStatus.SUCCEEDED
    db.commit()
    event(db, run, "planning", "Generated reproducible research proposal", {"hypothesis_id": str(hypothesis.id), "experiment_plan_id": str(plan.id)})
    return summary
