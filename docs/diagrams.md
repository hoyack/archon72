# Diagrams (Mermaid.js)

This file collects Mermaid diagrams documenting key flows.

## ignition.sh (Conclave runner)

```mermaid
flowchart LR
    A([ignition.sh]) --> B["python scripts/run_conclave.py\n--voting-concurrency 3\n--no-queue --no-blockers\n--motion + --motion-file\n--motion-type policy"]
    B --> C["_bmad-output/conclave/ (conclave outputs)"]
    B --> D["tee log\n_bmad-output/conclave/conclave-attribution-verifiability-<timestamp>.log"]
```

## Discovery Loop: Secretary → Consolidator → Review

```mermaid
flowchart TD
    T["Conclave transcript (.md)"] --> S["run_secretary.py\n--enhanced optional"]
    S --> SOut["_bmad-output/secretary/<session>/\nsecretary-report.json\nmotion-queue.json"]
    SOut --> C["run_consolidator.py\nauto-detects secretary output"]
    C --> COut["_bmad-output/consolidator/<session>/\nmega-motions + analyses"]
    COut --> R["run_review_pipeline.py\nsimulate | --triage-only | --real-agent"]
    R --> ROut["_bmad-output/review-pipeline/<session>/\nratification_results.json\npipeline_result.json"]
```

## Executive Pipeline (v2)

```mermaid
flowchart TD
    subgraph Inputs
        C1["--from-conclave\n_bmad-output/conclave"] --> Reg["run_registrar\n(register mandates)"]
        Reg --> Mand["ratified_mandates.json"]
        L1["--from-ledger\nratified_mandates.json or dir"] --> Mand
        R1["review-pipeline output\nratification_results.json"] --> Packets
        Mand --> Packets["build ratified intent packets"]
    end

    Packets --> Loop{"for each motion"}
    Loop --> Assign["infer assignment\nor --affected/--owner overrides"]
    Assign --> Mode{"deliberation mode\nmanual | llm | auto"}
    Mode -->|manual| Manual["load inbox contributions\n+ attestations"]
    Mode -->|llm| LLM["LLM deliberation\nwrites inbox artifacts"]
    Mode -->|auto none| Skip["skip deliberation"]
    Manual --> Blocker
    LLM --> Blocker
    Skip --> Blocker

    Blocker -.->|--llm-blocker-workup\nand v2 blockers| Workup["E2.5 blocker workup\npeer_review_summary\nconclave_queue_items\ndiscovery_task_stubs"]
    Workup --> Integrate
    Blocker --> Integrate["integrate execution plan\n+ gates + handoff"]
    Integrate --> Out["_bmad-output/executive/<session>/motions/<motion_id>/\nexecution_plan.json\nexecutive_gates.json\nexecution_plan_handoff.json\nexecutive_events.jsonl"]

    Out --> Summary["executive_cycle_summaries.json\n+ gate failure counts"]
    Summary --> Gate{"--require-gates?"}
    Gate -->|failures or fallback attestations| Exit["exit 1 (handoff blocked)"]
    Gate -->|ok| Done["pipeline complete"]
```

## Two Wheels Architecture (from docs/stages/run-pipeline.md)

```mermaid
flowchart LR
    subgraph Wheel2["Wheel 2: Execution Loop (Mandates)"]
        C[Conclave Passed Motion] --> Reg[Registrar] --> Exec[Executive] --> Admin[Administrative] --> Earl[Earl Tasking]
    end

    subgraph Wheel1["Wheel 1: Discovery Loop (Recommendations)"]
        Debate[Debate Transcript] --> Sec[Secretary] --> Con[Consolidator] --> Rev[Review Pipeline] --> Vote[Conclave Vote]
    end

    Vote -->|passed| C
    Vote -->|rejected/deferred| End[End]
```

## Aegis Bridge (Supabase → Archon72)

```mermaid
flowchart TD
    SB[(Supabase petitions table\nstatus = 'pending')] --> Bridge

    subgraph Bridge["Aegis Bridge"]
        Fetch["1) Fetch pending"] --> Mark["2) Mark processing"]
        Mark --> Transform["3) Transform to Archon72 format"]
        Transform --> Submit["4) Submit to Archon72 API"]
        Submit --> Update["5) Update status\nsubmitted | failed | dead_letter"]
    end

    Bridge --> API["Archon72 API\n/v1/petition-submissions"]
```
