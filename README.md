# OpenSCAD AI Workflow

**AI-assisted 3D printable model design with OpenSCAD, BOSL2, and MCP**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![OpenSCAD](https://img.shields.io/badge/OpenSCAD-2025.05.02-green.svg)](https://openscad.org/)
[![BOSL2](https://img.shields.io/badge/BOSL2-v2.0.716+-orange.svg)](https://github.com/BelfrySCAD/BOSL2)
[![MCP](https://img.shields.io/badge/MCP-FastMCP%203.1-purple.svg)](https://github.com/jlowin/fastmcp)

Create high-quality 3D printable models through natural conversation with AI. Design complex mechanical parts, parametric objects, and functional prints without memorizing syntax or fighting with traditional CAD tools.

## Why This Exists

**The Problem:** Traditional CAD tools have steep learning curves. OpenSCAD is powerful but requires programming knowledge. Designing 3D printable parts involves trial-and-error, manual calculations, and constant reference to documentation.

**The Solution:** This project provides an MCP (Model Context Protocol) server that gives Claude direct access to OpenSCAD tools and BOSL2 documentation. Claude can validate designs, render multi-view previews, track design iterations, and self-critique its own output — all without manual intervention.

**How It's Different:**
- **vs. Traditional CAD (Fusion 360, SolidWorks)** — No GUI learning curve, version-controlled designs, parametric by default
- **vs. Vanilla OpenSCAD** — AI assistance eliminates syntax lookup, BOSL2 reduces code complexity 10x
- **vs. Tinkercad/Easy CAD** — Professional-grade results, unlimited complexity, reusable parametric designs
- **vs. Other OpenSCAD MCP servers** — BOSL2 documentation as native resources, multi-view visual feedback loop, design iteration tracking, MQTT event integration

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                     Claude Code / LLM                      │
│                                                            │
│  "Create a bracket with 4 M3 holes, render it,            │
│   critique the views, iterate until proportions match"     │
└────────────────────┬───────────────────────────────────────┘
                     │ MCP Protocol (JSON-RPC over stdio)
                     ▼
┌────────────────────────────────────────────────────────────┐
│              MCP Server (mcp_server/)                       │
│                                                            │
│  17 Tools                    7 Resources                   │
│  ├── validate_design         ├── bosl2://quickref          │
│  ├── render_stl_file         ├── bosl2://attachments       │
│  ├── render_png_preview      ├── bosl2://threading         │
│  ├── render_design_views     ├── bosl2://rounding          │
│  ├── list_designs            ├── bosl2://patterns          │
│  ├── create_from_template    ├── bosl2://examples/...      │
│  ├── get_design_status       └── bosl2://prompts/...       │
│  ├── check_environment                                     │
│  ├── save_design_iteration                                 │
│  ├── list_design_iterations                                │
│  ├── get_latest_design_iteration                           │
│  ├── search_knowledge_base                                 │
│  ├── ingest_document                                       │
│  ├── ingest_directory                                      │
│  ├── analyze_stl                                           │
│  ├── convert_stl_to_scad                                   │
│  └── reverse_engineer_stl                                  │
└────────────────────┬───────────────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
┌──────────────────┐  ┌──────────────────┐
│    OpenSCAD      │  │      MQTT        │
│  (AppImage CLI)  │  │    Broker        │
│                  │  │                  │
│  xvfb-run for    │  │  openscad/...    │
│  headless render │  │  event topics    │
└──────────────────┘  └──────────────────┘
```

### Key Design Decisions

- **MCP over shell scripts** — Claude invokes tools directly via structured protocol instead of parsing shell output
- **BOSL2 docs as MCP Resources** — Claude loads attachment, threading, pattern, and rounding references into its context on demand, producing higher-quality code
- **Multi-view rendering** — Four camera angles (front, top, right, isometric) let Claude self-critique proportions and feature placement
- **MQTT event bus** — Every tool invocation publishes structured events for Node-RED integration and observability
- **Design versioning** — Auto-numbered `design_v001.scad`, `design_v002.scad` copies preserve iteration history

## Quick Start

### Prerequisites

- **Linux** (headless supported) or **macOS**
- **Python 3.10+**
- **OpenSCAD 2025.05+** (AppImage recommended for Linux)
- **BOSL2** library installed
- **xvfb** (for headless Linux rendering)

### Installation

```bash
# Clone the repo
git clone https://github.com/DigitalMachineShopLtd/OpenScad_AI.git
cd OpenScad_AI

# Run environment check (tells you what's missing)
./scripts/setup.sh

# Create Python venv and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Install OpenSCAD AppImage (Linux)
mkdir -p bin
wget -O bin/OpenSCAD-latest.AppImage \
  "https://files.openscad.org/snapshots/OpenSCAD-2025.05.02-x86_64.AppImage"
chmod +x bin/OpenSCAD-latest.AppImage

# Install BOSL2
git clone https://github.com/BelfrySCAD/BOSL2.git \
  ~/.local/share/OpenSCAD/libraries/BOSL2

# Install xvfb for headless rendering (Linux)
sudo apt-get install xvfb
```

### Register the MCP Server with Claude Code

```bash
claude mcp add openscad -- /path/to/OpenScad_AI/.venv/bin/python -m mcp_server
```

### Verify Everything Works

```bash
# Activate venv
source .venv/bin/activate

# Run tests
python -m pytest tests/ -v

# Run environment check
./scripts/setup.sh

# Validate a sample design
./scripts/validate.sh designs/examples/sample-bracket.scad
```

## Usage

### With Claude Code (MCP)

Once the MCP server is registered, Claude can use all tools directly:

```
You: "Create a bracket with 4 M3 holes and render it"

Claude: [uses create_from_template to scaffold the design]
        [writes BOSL2 code using bosl2://attachments reference]
        [uses validate_design to check geometry]
        [uses render_design_views for 4-angle preview]
        [self-critiques proportions and iterates]
        [uses save_design_iteration to preserve the version]
```

### With Shell Scripts (standalone)

```bash
# Validate a design
./scripts/validate.sh designs/mechanical/my-part.scad

# Render STL + PNG
./scripts/render.sh designs/mechanical/my-part.scad

# Check STL readiness for slicing
./scripts/slice.sh output/stl/my-part.stl
```

### The Visual Feedback Loop

The core workflow for AI-assisted design:

```
1. Claude generates BOSL2 code
         │
         ▼
2. render_design_views → 4 PNG previews (front/top/right/isometric)
         │
         ▼
3. Claude examines views, identifies issues:
   - "Front view shows holes are too close to edge"
   - "Top view reveals missing symmetry"
   - "Isometric shows thickness is wrong"
         │
         ▼
4. save_design_iteration → preserves current version
         │
         ▼
5. Claude edits code to fix issues → back to step 2
         │
         ▼
6. After 2-4 iterations → validate_design → render_stl_file
```

## MCP Server Reference

Full API documentation: **[docs/mcp-api-reference.md](docs/mcp-api-reference.md)**

### Tools (17)

| Tool | Purpose |
|------|---------|
| `validate_design` | Three-stage validation: syntax, STL export, manifold check |
| `render_stl_file` | High-quality STL rendering to `output/stl/` |
| `render_png_preview` | Single PNG preview with configurable camera |
| `render_design_views` | Multi-view render: front, top, right, isometric PNGs |
| `list_designs` | List all `.scad` files in the project |
| `create_from_template` | Create new design from basic/mechanical/parametric template |
| `get_design_status` | File info, last render outputs, staleness check |
| `check_environment` | Verify OpenSCAD, BOSL2, xvfb, MQTT availability |
| `save_design_iteration` | Save numbered snapshot (`design_v001.scad`) |
| `list_design_iterations` | List all saved iteration versions |
| `get_latest_design_iteration` | Get the highest version of a design |
| `search_knowledge_base` | Semantic search across RAG collections (code, docs, schemas, history) |
| `ingest_document` | Ingest a single file into the RAG knowledge base |
| `ingest_directory` | Bulk ingest a directory with glob pattern filtering |
| `analyze_stl` | Extract STL metadata, render views, generate import wrapper, store in RAG |
| `convert_stl_to_scad` | Primitive fitting (cuboid/cylinder/sphere) for simple convex STL shapes |
| `reverse_engineer_stl` | Prepare STL for AI-driven visual reverse engineering into BOSL2 code |

### Resources (7)

| URI | Content |
|-----|---------|
| `bosl2://quickref` | BOSL2 function quick reference (from `docs/bosl2-quickref.md`) |
| `bosl2://attachments` | Attachment system: anchors, `attach()`, `position()`, `diff()+tag()` |
| `bosl2://threading` | Threading, screws, heat-set inserts, standoffs |
| `bosl2://rounding` | Rounding and chamfering with print-friendly rules |
| `bosl2://patterns` | `grid_copies()`, `linear_copies()`, `rot_copies()`, `path_copies()` |
| `bosl2://examples/mounting-plate` | Complete parametric mounting plate example |
| `bosl2://prompts/image-to-code` | Structured prompt template for image/sketch to OpenSCAD |

## Project Structure

```
OpenScad_AI/
├── mcp_server/              # MCP server (Python/FastMCP)
│   ├── __init__.py
│   ├── __main__.py          # Entry point: python -m mcp_server
│   ├── server.py            # 17 tools + 7 resources
│   ├── openscad.py          # OpenSCAD CLI wrapper, multi-view rendering
│   ├── mqtt_client.py       # Persistent MQTT with QoS 1
│   ├── versioning.py        # Iteration tracking (design_v001.scad)
│   ├── rag_client.py        # ChromaDB reads + MQTT writes for RAG
│   ├── chunking.py          # Document chunking for RAG ingestion
│   └── stl_converter.py     # STL analysis, primitive fitting, conversion
│
├── tests/                   # Test suite
│   ├── test_openscad.py     # Multi-view rendering tests
│   ├── test_versioning.py   # Versioning module tests (5 tests)
│   ├── test_chunking.py     # Document chunking tests (11 tests)
│   ├── test_rag_client.py   # RAG client tests (11 tests)
│   └── test_stl_converter.py # STL converter tests (15 tests)
│
├── designs/                 # .scad source files (version controlled)
│   ├── mechanical/          # Functional parts
│   ├── artistic/            # Decorative objects
│   ├── prototypes/          # Experimental designs
│   └── examples/            # Sample designs (sample-bracket.scad)
│
├── output/                  # Generated files (gitignored)
│   ├── stl/                 # Print-ready STL files
│   ├── png/                 # Preview images
│   ├── gcode/               # Sliced files
│   └── iterations/          # Design version history
│
├── templates/               # Starting points
│   ├── basic.scad           # Simple objects, quick prototypes
│   ├── mechanical-part.scad # Functional parts with mounting holes
│   └── parametric.scad      # Customizer-compatible designs
│
├── scripts/                 # Shell automation
│   ├── setup.sh             # Environment check and dependency verification
│   ├── validate.sh          # Three-stage design validation
│   ├── render.sh            # STL + PNG rendering
│   └── slice.sh             # STL readiness check (placeholder)
│
├── docs/                    # Documentation
│   ├── HOW-TO-USE.md        # Complete workflow guide
│   ├── bosl2-quickref.md    # BOSL2 function reference
│   ├── mcp-api-reference.md # Full MCP server API documentation
│   ├── image_to_code.md     # Research: 5 pathways for image-to-OpenSCAD
│   └── plans/               # Architecture and implementation plans
│
├── bin/                     # Local binaries (gitignored)
│   └── OpenSCAD-latest.AppImage
│
├── .venv/                   # Python virtual environment (gitignored)
├── requirements.txt         # Pinned Python dependencies
└── CLAUDE.md                # Project rules and conventions
```

## MQTT Integration

Every MCP tool publishes events to MQTT for observability and Node-RED integration.

**Topics:**

| Topic | Trigger |
|-------|---------|
| `openscad/validate/result` | After validation completes |
| `openscad/render/started` | When STL render begins |
| `openscad/render/stl` | After STL render completes |
| `openscad/render/png` | After PNG render completes |
| `openscad/render/multi_view` | After multi-view render completes |
| `openscad/design/created` | After template-based design creation |
| `openscad/design/iteration_saved` | After design iteration is saved |
| `openscad/rag/search` | After RAG knowledge base search |
| `openscad/rag/ingested` | After single document ingestion |
| `openscad/rag/bulk_ingested` | After directory bulk ingestion |
| `openscad/stl/analyzed` | After STL analysis completes |
| `openscad/stl/converted` | After STL primitive fitting completes |
| `openscad/stl/reverse_engineer_started` | After STL reverse engineering is prepared |

**Payload format:** JSON with auto-appended `timestamp` field (ISO 8601 UTC).

**Configuration:**

| Environment Variable | Default | Purpose |
|---------------------|---------|---------|
| `MQTT_BROKER` | `localhost` | MQTT broker hostname |
| `MQTT_PORT` | `1883` | MQTT broker port |

MQTT is optional — if the broker is unavailable, the server logs a warning and continues without publishing.

## RAG Knowledge Base

The server includes a RAG (Retrieval-Augmented Generation) subsystem backed by ChromaDB for semantic search across project knowledge.

**Collections:** `openscad_code`, `project_docs`, `schemas_config`, `design_history`

**Tools:** `search_knowledge_base`, `ingest_document`, `ingest_directory` — search existing knowledge or add new files to the vector store.

**Auto-injection:** When `RAG_AUTO_INJECT=true`, relevant context is silently injected during `create_from_template` (code patterns), `render_design_views` (design history), and `validate_design` (schemas). No manual search needed.

**Configuration:**

| Environment Variable | Default | Purpose |
|---------------------|---------|---------|
| `CHROMADB_HOST` | `10.0.1.81` | ChromaDB server hostname |
| `CHROMADB_PORT` | `8000` | ChromaDB server port |
| `RAG_ENABLED` | `true` | Enable/disable RAG features |
| `RAG_AUTO_INJECT` | `true` | Auto-inject context on tool calls |
| `RAG_N_RESULTS` | `5` | Default semantic search result count |

## Why BOSL2?

BOSL2 is the critical enabler for AI-assisted OpenSCAD. It transforms low-level geometry operations into high-level, declarative design intent that maps naturally to human language:

| What You Say | BOSL2 Code | Vanilla OpenSCAD |
|---|---|---|
| "Put this on top" | `attach(TOP)` | `translate([0,0,h/2])` |
| "4 holes in a grid" | `grid_copies(spacing=20, n=[2,2])` | 4x `translate()` calls |
| "Round the edges" | `cuboid([...], rounding=2)` | `minkowski()` + math |
| "Subtract these" | `diff() + tag("remove")` | Nested `difference()` |

**Result:** 60-73% less code, easier to modify, fewer bugs, and the AI generates it in seconds.

## Documentation

- **[How-To Guide](docs/HOW-TO-USE.md)** — Complete workflow guide (shell scripts + MCP)
- **[MCP API Reference](docs/mcp-api-reference.md)** — All 17 tools and 7 resources with parameters and examples
- **[BOSL2 Quick Reference](docs/bosl2-quickref.md)** — Common functions, shapes, patterns
- **[Image to Code Research](docs/image_to_code.md)** — 5 pathways for converting images to OpenSCAD (Pathway 5 implemented)
- **[Sample Bracket](designs/examples/sample-bracket.scad)** — Example design

## Scripts

### setup.sh — Environment Check

```bash
./scripts/setup.sh
```

Checks: OpenSCAD (AppImage priority), BOSL2, xvfb, MQTT, output directories, script permissions, BOSL2 compile test. Cross-platform (Linux/macOS).

### validate.sh — Design Validation

```bash
./scripts/validate.sh designs/mechanical/my-part.scad
```

Three-stage pipeline:
1. **Syntax check** — catches typos, missing brackets, undefined variables
2. **STL export test** — confirms OpenSCAD can generate geometry
3. **Manifold check** — verifies watertight mesh for slicing

Publishes results to MQTT topics `openscad/validate/*`.

### render.sh — STL + PNG Rendering

```bash
./scripts/render.sh designs/mechanical/my-part.scad
```

Creates `output/stl/my-part.stl` and `output/png/my-part.png`. Uses `xvfb-run` automatically on headless systems. Publishes to `openscad/render/*`.

### slice.sh — Slicing Readiness

```bash
./scripts/slice.sh output/stl/my-part.stl
```

Validates the STL exists and is non-empty, publishes readiness to MQTT. Slicing is manual — transfer the STL to a machine with Bambu Studio, OrcaSlicer, or PrusaSlicer.

## Requirements

| Component | Version | Notes |
|-----------|---------|-------|
| Python | 3.10+ | For MCP server |
| OpenSCAD | 2025.05+ | AppImage recommended for Linux |
| BOSL2 | v2.0.716+ | Installed in OpenSCAD libraries path |
| xvfb | any | Required for headless Linux rendering |
| MQTT broker | any | Optional — for event publishing |
| FastMCP | 3.1.0 | Python MCP framework |
| paho-mqtt | 2.1.0 | MQTT client library |
| trimesh | 4.11.3 | STL mesh analysis and primitive fitting |

## Contributing

### Areas for Contribution

- **New BOSL2 resource templates** — threading patterns, enclosure designs, snap-fit joints
- **Additional MCP tools** — STL analysis, BOM generation, assembly management
- **Test coverage** — integration tests, edge cases, error handling
- **Cross-platform** — Windows support, alternative OpenSCAD sources
- **Node-RED flows** — MQTT-driven automation examples

### Guidelines

1. Fork and branch from `master`
2. Run `python -m pytest tests/ -v` before submitting
3. Follow existing code style (type hints, docstrings, MQTT events)
4. Update relevant docs if adding features

## Resources

- [BOSL2 Documentation](https://github.com/BelfrySCAD/BOSL2/wiki)
- [OpenSCAD Manual](https://openscad.org/documentation.html)
- [MCP Specification](https://modelcontextprotocol.io)
- [FastMCP Framework](https://github.com/jlowin/fastmcp)

## License

This workflow setup is provided as-is for personal and commercial use.
BOSL2 is licensed under BSD 2-Clause License.
