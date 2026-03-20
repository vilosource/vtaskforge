"""Generate C4-style diagrams for vtaskforge using Python diagrams library."""

from diagrams import Diagram, Cluster, Edge
from diagrams.c4 import Person, Container, Database, System, SystemBoundary, Relationship

output_dir = "/home/jasonvi/GitHub/vtaskforge/docs/diagrams"

# Common graph attributes for all diagrams
graph_attr = {
    "splines": "spline",
    "pad": "2.0",
    "nodesep": "0.60",
    "ranksep": "0.75",
    "fontname": "Sans-Serif",
    "fontsize": "15",
    "fontcolor": "#2D3436",
}

# ============================================================
# Diagram 1: C1 — System Context
# ============================================================
with Diagram(
    "vtaskforge — C1 System Context",
    filename=f"{output_dir}/c1-system-context",
    direction="TB",
    graph_attr=graph_attr,
    show=False,
):
    human = Person(
        name="Product Owner",
        description="Defines workplans, reviews tasks, triages issues, final authority",
    )

    vtf = System(
        name="vtaskforge",
        description="Distributed task execution system. Manages workplans, phases, tasks, reviews, links, and events.",
        external=False,
    )

    vfagents = System(
        name="vf-agents",
        description="Agent pool manager. Claims tasks, manages executor containers, captures sessions.",
        external=True,
    )

    mykb = System(
        name="mykb",
        description="Knowledge base. Stores facts, decisions, gotchas, patterns by area.",
        external=True,
    )

    scrum = System(
        name="Scrum Master Agent",
        description="Autonomous process agent. Monitors flow, triages blockers, generates reports.",
        external=True,
    )

    webui = System(
        name="Web UI",
        description="Browser SPA. Kanban board, task editing, agent-assisted chat.",
        external=True,
    )

    tui = System(
        name="Terminal UI",
        description="Ink-based TUI. Kanban view, CLI task management.",
        external=True,
    )

    intake = System(
        name="Intake Tooling",
        description="Converts markdown plans into structured workplans, phases, and tasks.",
        external=True,
    )

    human >> Edge(label="defines workplans\nreviews tasks") >> vtf
    human >> Edge(label="uses browser") >> webui
    human >> Edge(label="monitors via CLI") >> tui

    vfagents >> Edge(label="claims tasks\nreports results") >> vtf
    vfagents >> Edge(label="loads context") >> mykb

    vtf >> Edge(label="event stream") >> scrum
    vtf >> Edge(label="real-time updates") >> webui
    vtf >> Edge(label="task data") >> tui

    intake >> Edge(label="creates tasks") >> vtf
    scrum >> Edge(label="nudges\ninsights", style="dashed") >> human


# ============================================================
# Diagram 2: C2 — Container (vtaskforge internals)
# ============================================================
with Diagram(
    "vtaskforge — C2 Container",
    filename=f"{output_dir}/c2-container",
    direction="TB",
    graph_attr=graph_attr,
    show=False,
):
    human = Person(
        name="Product Owner",
        description="Human user",
    )

    with SystemBoundary("vtaskforge System"):
        api = Container(
            name="API Server",
            technology="Node/TS, Port 3000",
            description="RPC API + business logic",
        )
        db = Database(
            name="Postgres",
            technology="PostgreSQL, Port 5432",
            description="Workplans, phases, tasks, links, reviews, events",
        )
        events = Container(
            name="Event Bus",
            technology="SSE / WebSocket",
            description="Real-time event broadcasting",
        )
        webspa = Container(
            name="Web UI SPA",
            technology="Browser App",
            description="Kanban board, task editing, agent chat",
        )

    vfagents = System(name="vf-agents", description="Agent pool manager", external=True)
    scrum = System(name="Scrum Master Agent", description="Process automation", external=True)
    tui = System(name="Terminal UI", description="CLI interface", external=True)
    intake = System(name="Intake Tooling", description="Plan converter", external=True)

    human >> Edge(label="HTTPS") >> webspa
    vfagents >> Edge(label="RPC API") >> api
    scrum >> Edge(label="event stream") >> events
    tui >> Edge(label="API calls") >> api
    intake >> Edge(label="task creation") >> api

    api >> Edge(label="SQL") >> db
    api >> Edge(label="publishes") >> events
    events >> Edge(label="live updates") >> webspa


# ============================================================
# Diagram 3: System Landscape
# ============================================================
with Diagram(
    "vtaskforge — System Landscape",
    filename=f"{output_dir}/system-landscape",
    direction="TB",
    graph_attr=graph_attr,
    show=False,
):
    human = Person(name="Product Owner", description="Defines work, reviews, triages")

    with SystemBoundary("vtaskforge Core"):
        vtf_api = Container(name="vtaskforge API", technology="Node/TS", description="Task coordination")
        vtf_db = Database(name="Postgres", technology="PostgreSQL", description="Task storage")
        vtf_events = Container(name="Event Stream", technology="SSE/WebSocket", description="Real-time updates")

    with SystemBoundary("Agent Ecosystem"):
        pool = System(name="vf-agents\nPool Manager", description="Go CLI", external=True)
        executor = System(name="Executor Agents", description="Write code, run tests", external=True)
        reviewer = System(name="Reviewer Agents", description="Review at gates", external=True)
        architect = System(name="Architect Agents", description="Refine tasks", external=True)
        scrum = System(name="Scrum Master", description="Process facilitation", external=True)

    with SystemBoundary("Knowledge System"):
        kb = System(name="mykb CLI", description="Node.js", external=True)
        kbdata = Database(name="~/.mykb/", technology="SQLite + JSONL", description="Knowledge storage")

    webui = System(name="Web UI SPA", description="Browser interface", external=True)
    tui = System(name="Terminal UI", description="CLI interface", external=True)
    intake = System(name="Intake Tooling", description="Plan converter", external=True)
    registry = System(name="ghcr.io", description="Container registry", external=True)

    human >> webui
    human >> tui

    vtf_api >> vtf_db
    vtf_api >> vtf_events
    vtf_api >> pool
    intake >> vtf_api

    pool >> registry
    pool >> executor
    pool >> reviewer
    pool >> architect

    executor >> kb
    reviewer >> kb
    architect >> kb
    kb >> kbdata

    vtf_events >> scrum
    vtf_events >> webui
    vtf_events >> tui

    scrum >> Edge(style="dashed") >> human


# ============================================================
# Diagram 4: Deployment
# ============================================================
with Diagram(
    "vtaskforge — Deployment",
    filename=f"{output_dir}/deployment",
    direction="TB",
    graph_attr=graph_attr,
    show=False,
):
    with Cluster("Cloud Infrastructure"):
        with Cluster("Server Host"):
            api = Container(name="vtaskforge API", technology="Node/TS :3000", description="RPC + Events")
            db = Database(name="Postgres", technology=":5432", description="Task storage")

        registry = Container(name="ghcr.io", technology="HTTPS :443", description="Agent container images")

    with Cluster("Agent Host Machine"):
        vfa = Container(name="vf-agents", technology="Go CLI", description="Pool manager")
        with Cluster("Docker Runtime"):
            exec_c = Container(name="Executor", technology="Container", description="Code execution")
            rev_c = Container(name="Reviewer", technology="Container", description="Quality review")
            arch_c = Container(name="Architect", technology="Container", description="Task refinement")
        scrum_d = Container(name="Scrum Master", technology="Daemon", description="Process monitor")

    with Cluster("Developer Machine"):
        tui_app = Container(name="Terminal UI", technology="Ink/Node", description="CLI monitoring")
        kb_cli = Container(name="mykb CLI", technology="Node.js", description="Knowledge access")
        kb_store = Database(name="~/.mykb/", technology="SQLite + JSONL", description="Local knowledge")

    with Cluster("Browser"):
        web_app = Container(name="Web UI SPA", technology="React/TS", description="Kanban board")

    api >> Edge(label="TCP:5432") >> db
    web_app >> Edge(label="HTTPS/WSS") >> api
    tui_app >> Edge(label="TCP:3000") >> api
    vfa >> Edge(label="TCP:3000") >> api
    scrum_d >> Edge(label="SSE:3000") >> api

    vfa >> Edge(label="Docker API") >> exec_c
    vfa >> Edge(label="Docker API") >> rev_c
    vfa >> Edge(label="Docker API") >> arch_c
    vfa >> Edge(label="HTTPS:443") >> registry

    kb_cli >> kb_store
    exec_c >> Edge(label="File I/O", style="dashed") >> kb_cli


print("All diagrams generated successfully!")
