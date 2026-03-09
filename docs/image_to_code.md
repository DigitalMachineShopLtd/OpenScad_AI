# IMAGE → OPENSCAD: The Art of the Possible
## A Deep-Dive Research Report — State of the Art, Early 2026

> **Core Question:** Can you take a photo of a physical object — or a sketch on a napkin — and get parametric OpenSCAD code out the other side?
>
> **Short Answer:** Sometimes yes, often almost, and always with significant caveats. The pathway you choose determines everything.

---

## Why This Matters

OpenSCAD's code-based CSG (Constructive Solid Geometry) architecture makes it uniquely well-suited to AI generation. Unlike GUI-driven CAD tools, you can describe an object entirely in text that a language model can produce. This is both its superpower and its constraint: it excels at geometric primitives and parametric logic, but it cannot natively express the free-form organic shapes that photogrammetry typically recovers from the real world.

**The fundamental tension:** OpenSCAD's CSG model is a perfect target for LLM code generation, but a terrible fit for photogrammetric mesh output. These two facts define almost every trade-off in this space.

---

## The Five Pathways at a Glance

| Pathway | Input Type | Output Quality | Complexity | Maker Ready? |
|---------|-----------|---------------|------------|-------------|
| 1. Direct VLM Prompting | Single image or sketch | Medium — simple shapes | ★☆☆ Very Low | ✅ YES |
| 2. Multi-View + MVS Pipeline | 5–30 photos | Low — mesh→CSG gap | ★★★ High | ⚠️ Partial |
| 3. Photogrammetry → Point Cloud → CAD-Recode | 20+ calibrated photos | High — for prismatic parts | ★★★★ Expert | 🔬 Lab Only |
| 4. Sketch / Drawing → CAD Commands | Engineering drawing/sketch | High — for 2D→3D | ★★☆ Medium | ⚠️ Emerging |
| 5. Agentic Visual Feedback Loop | Reference image + LLM render loop | Medium-High — iterative | ★★☆ Medium | ✅ YES (Claude Code) |

---

## Pathway 1: Direct VLM Multimodal Prompting

*Hand a photo or sketch to Claude / GPT-4o / Gemini and ask for OpenSCAD code.*

This is the most accessible pathway and the one most relevant for makers today. Modern vision-language models (VLMs) have demonstrated genuine ability to translate images of objects into workable OpenSCAD code — with important caveats about what "workable" means.

### How It Works

You provide a single image (photograph, sketch, screenshot, engineering drawing) alongside a prompt asking the VLM to generate OpenSCAD code. No specialized tooling is required beyond API access or a chat interface.

### Benchmark Performance (CADPrompt Dataset, 2024–2025)

| Model | Compile Rate | Notes |
|-------|-------------|-------|
| GPT-4o | 96.5% | Best baseline; strong topology metrics |
| Claude Sonnet (+ feedback loop) | ~85% | With iterative correction |
| Gemini 2.0 Flash | ~85% | Fastest; most cost-effective |
| CodeLlama (open source) | 73.5% | Struggles with 3D spatial logic |
| Fine-tuned CAD-Coder VLM | 100% | Trained on 163k image-code pairs; beats GPT-4.5 |

> **Counter-intuitive finding:** GPT-4V research showed that **text-only input frequently outperformed multimodal (image + text) input for simple objects**. Images helped most for complex geometries like springs and gears — where verbal description alone is insufficient. Adding an image doesn't always help and can sometimes hurt.

### What Works Well

- Simple prismatic objects: boxes, cylinders, brackets, enclosures
- Objects with clear silhouettes and minimal occlusion
- Electronic enclosures, simple mechanical brackets, connector housings
- Iterative refinement: providing a rendered preview and asking for corrections
- Sketch-to-code where you drew the sketch yourself (no ambiguity about dimensions)

### Where It Breaks Down

- Complex mechanical parts with internal features (hidden holes, threads, pockets)
- Organic or free-form geometry — curves, ergonomic shapes, artistic forms
- Precise dimensional accuracy (LLMs estimate, not measure)
- Mechanical springs: IoU drops to near zero even with GPT-4o + debugger
- Assemblies with multiple interacting parts
- Any shape where the CSG construction sequence isn't visually obvious

### Practical Maker Workflow

1. Provide a clear, well-lit photo OR your own sketch of the target object
2. Include explicit dimensional information in your prompt (or measure and specify)
3. Ask the LLM to generate OpenSCAD code and immediately render it
4. Pass the rendered preview back to the LLM for self-critique and correction
5. Repeat 2–4 times; manually edit remaining discrepancies

**DesignBench Case Study (Build Great AI):** Dan Becker's prototype ran LLaMA 3.1, GPT-4, and Claude 3.5 in parallel to generate OpenSCAD code. Users selected the most promising result and refined iteratively. Design time dropped from hours to minutes for simple objects. The system included an image upload feature for napkin-sketch-to-model workflows.

---

## Pathway 2: Multi-View Reconstruction Pipeline (jhacksman MCP Server)

*Generate or photograph multiple views, run CUDA Multi-View Stereo, then convert mesh to OpenSCAD.*

Released March 2025 (102+ GitHub stars), the jhacksman OpenSCAD MCP Server represents the most complete attempt at a fully automated image-to-OpenSCAD pipeline.

### The Full Pipeline

1. **Image Generation:** Text prompt → Google Gemini or Venice.ai API → photorealistic images from multiple angles
2. **Multi-View Generation:** AI generates 6–12 views of the same object for 3D reconstruction
3. **Human Approval Gate:** Generated views shown for approval/rejection before processing
4. **CUDA Multi-View Stereo:** Approved images → 3D point cloud via CUDA-accelerated MVS
5. **OpenSCAD Code Generation:** Point cloud / mesh → parametric OpenSCAD code
6. **Remote Processing:** Optionally offloads CUDA work to a more powerful LAN machine

### The Fundamental Problem: The Mesh-to-CSG Gap

Converting a triangle mesh into CSG operations is a fundamentally hard inverse problem. It is like looking at a photograph of a Lego model and trying to deduce the exact bricks used to build it.

Multi-View Stereo produces a dense triangle mesh — a cloud of polygons that approximates surfaces. OpenSCAD's CSG model describes objects as combinations of geometric primitives (spheres, cylinders, cubes) subjected to boolean operations. For simple prismatic shapes, bridging this works with moderate success. For organic or complex forms, the resulting code is either a rough approximation or falls back to importing the mesh directly (losing all parametric properties).

### Hardware Requirements

- CUDA-capable NVIDIA GPU for MVS processing (RTX 3060 minimum recommended)
- CUDA toolkit installation and CUDA MVS library compilation from source
- Python virtual environment with multiple specialized dependencies
- Google Gemini or Venice.ai API keys for image generation
- Optional: dedicated LAN server for remote CUDA processing

### Output Formats

`OBJ` | `CSG` | `AMF` | `3MF` | `SCAD`

> **Maker Reality Check:** This pipeline is technically impressive but requires significant infrastructure investment. Best suited to makers who already have a dedicated GPU workstation and are comfortable with CUDA development environments. For most hobbyists, Pathway 1 or 5 will deliver better results with a fraction of the setup effort.

---

## Pathway 3: Photogrammetry → Point Cloud → Parametric CAD Reverse Engineering

*State-of-the-art academic research; not yet accessible for everyday maker use.*

This is where the most exciting academic research is happening. Two landmark papers define the state of the art:

### Point2CAD (CVPR 2024)

Point2CAD proposes a hybrid analytic-neural approach that bridges segmented point clouds to structured CAD models. Key innovation: a novel implicit neural representation of free-form surfaces that powers the surface-fitting stage, allowing reconstruction of smooth curved surfaces (not just planes and cylinders) while maintaining CAD-compatible topology.

### CAD-Recode (ICCV 2025) — Current State of the Art

CAD-Recode is state-of-the-art across three major CAD reconstruction benchmarks (DeepCAD, Fusion360, CC3D). Its approach: instead of recovering a mesh or B-rep model, it translates a point cloud **directly into Python code** using the CadQuery library — code that, when executed, reconstructs the CAD model.

This is directly analogous to the OpenSCAD code generation goal. CAD-Recode uses a small fine-tuned LLM (Qwen2-1.5B) as a decoder, combined with a lightweight point cloud projector. The LLM's pre-training on Python code gives it a strong foundation for generating structured geometric operations.

> **Why this matters for OpenSCAD:** CAD-Recode proves that point cloud → parametric code generation is solvable with small fine-tuned LLMs. The output is CadQuery Python, not OpenSCAD, but the approach is directly applicable. A fine-tuned model targeting OpenSCAD's CSG syntax could achieve similar results.

### The Full Reverse Engineering Pipeline

1. Capture 40–80 calibrated photos with even lighting, no reflections, 60–80% overlap
2. Process with Agisoft Metashape or COLMAP → dense point cloud
3. Cleanup and decimate mesh in Meshmixer or Blender (target: 500k–1M faces)
4. Apply Point2CAD or CAD-Recode to generate parametric code
5. Translate CadQuery output to OpenSCAD equivalent (LLM-assisted translation)

### Photogrammetry Photo Capture Tips

- Use diffuse, even illumination — eliminate shadows and specular highlights
- Capture 60–80% overlap between adjacent frames
- DSLR or mirrorless preferred; smartphone usable for low-accuracy work
- Typical accuracy: a few tenths of a millimeter for small objects
- Matte surfaces work far better than shiny or transparent objects

### Honest Assessment

- CAD-Recode and Point2CAD are research code — no polished installer, no GUI
- Requires CUDA GPU, Python environment management, Docker
- Best results on prismatic mechanical parts; curved organic shapes still struggle
- CadQuery output requires translation to OpenSCAD (an LLM can assist this step)
- Packaged accessible tools are approximately 12–24 months away

---

## Pathway 4: Sketch & Engineering Drawing → Parametric CAD

*The most promising pathway for structured inputs — engineering drawings, technical sketches, isometric views.*

If your input is a structured image — a hand-drawn sketch, an isometric view, a technical drawing with dimensions — a different family of specialized fine-tuned models applies.

### CadVLM (Autodesk Research, ECCV 2024)

The first multimodal LLM successfully applied to parametric CAD generation. Adapts pre-trained foundation models to manipulate engineering sketches. Supports three critical tasks:

- **CAD autocompletion:** given a partial sketch, complete it
- **CAD autoconstraint:** predict missing geometric constraints
- **Image-conditional generation:** given an image, generate the CAD sketch

Output feeds directly to existing CAD tools' APIs to generate project files.

### OpenECAD (Fine-Tuned VLMs, 0.55B–3.1B Parameters)

Fine-tunes small VLMs on images of 3D designs and outputs highly structured 2D sketches and 3D construction commands. Key differentiator: uses **dependency-based constraint definitions** — a sketch's reference plane is defined relative to existing faces, not just absolute coordinates. This mirrors how human modelers think and makes output far more robust and editable.

### CAD-Assistant (GPT-4o + FreeCAD, Dec 2024)

First general-purpose AI framework for CAD design. Runs as an agent inside FreeCAD, processing multimodal inputs including text, hand-drawn sketches, precise engineering drawings, and 3D scans. FreeCAD objects can be exported as STEP and re-ingested — no direct FreeCAD → OpenSCAD conversion with full parametric preservation.

### Free2CAD: Hand-Drawn Isometric → CAD Sequences

Specifically designed to convert hand-drawn isometric sketches into CAD command sequences. If you sketch objects in isometric perspective on paper and photograph them, Free2CAD can parse the geometry and produce construction sequences.

### CAD2Program: Technical Drawings as Raster Images

Research shows that treating a 2D CAD drawing as a raster image and encoding it with a standard ViT model achieves competitive performance against methods requiring vector-graphics input. **A photograph of a technical drawing can work nearly as well as the original CAD file.**

> **Practical Implication:** If you produce structured engineering sketches (isometric or orthographic), you are in the sweet spot of this pathway. Models perform significantly better on sketches with clear geometric intent than on photographs of finished real objects.

---

## Pathway 5: Agentic Visual Feedback Loop (Claude Code + OpenSCAD Render)

*The most practical and powerful workflow available to makers today.*

This pathway flips the question: rather than extracting an OpenSCAD model from an image, it uses images to iteratively improve an AI-generated OpenSCAD model. Documented in a September 2025 Medium article (Gian Luca Bailo) and directly executable using Claude Code with an OpenSCAD MCP server.

### The Five-Step Cycle

1. The AI writes OpenSCAD code describing the object (optionally informed by a reference image)
2. OpenSCAD CLI renders orthographic views (front, top, side) automatically
3. The AI examines the rendered images using its vision capabilities
4. The AI critiques its own work: *"legs too thin"*, *"spout misaligned"*, *"hole missing"*
5. The AI edits the OpenSCAD code to fix identified issues; loop repeats 3–6 times

### Documented Results

- Starting from crude blocky geometry, the loop produced objects "closer to a manufactured item" after several cycles on a table and a teapot test
- AI successfully caught proportional issues (thin legs, awkward spout curvature) and corrected them through code edits
- When provided a reference image, the model iterates toward visual matching as a constraint

### Documented Limitations

- Works only for parametric, CSG-constructable objects — organic shapes out of reach
- No engineering depth: no stress analysis, tolerances, or material considerations
- Complex designs with many interacting parts do not scale well
- Occasional non-manifold geometry or overlapping errors requiring manual correction
- AI's visual self-critique is faster but not necessarily more accurate than human inspection

### Why This Is the Sweet Spot for Your Stack

This pathway maps **directly** onto Claude Code + OpenSCAD MCP:

- Claude Code writes and edits `.scad` files via the OpenSCAD MCP
- The MCP server triggers OpenSCAD CLI renders and returns PNG images
- Claude's vision capabilities allow it to inspect those renders in the same context
- MQTT can broadcast render events and trigger downstream workflows
- The loop is fully automatable within a Claude Code agentic session
- **No additional tooling required beyond what is already being built**

---

## What the Research Actually Shows

### The CadQuery vs. OpenSCAD Debate

Most academic work and newer tooling has moved toward CadQuery (Python) rather than OpenSCAD as the target CAD language. Reasons given consistently across papers:

- CadQuery is pure Python — LLMs have vastly more Python training data than OpenSCAD-specific syntax
- CadQuery's "design intent" approach produces more concise code for complex objects
- CadQuery can be executed without external software dependencies
- OpenSCAD requires full software installation to execute and render

GPT-4 achieved 96.5% compile rate on CadQuery vs. noticeably lower rates with OpenSCAD on comparable tasks.

**The OpenSCAD counter-argument for makers:** simpler to install, no Python dependency management, natively parametric by design, large community of 3D-printable models (Thingiverse, Printables), and is the lingua franca of the hobbyist CAD world. The LLM performance gap is real but narrowing.

### EvoCAD: Evolutionary Generation (2025)

EvoCAD introduces an evolutionary approach: generates a **population** of designs, evaluates them using a two-step VLM + reasoning LLM fitness function (GPT-4V/4o describes each candidate visually, o3-mini ranks them), applies crossover and mutation to evolve better designs. EvoCAD with GPT-4o significantly outperforms single-generation baselines on topology metrics. Multi-generation evolutionary approaches are the next frontier for AI-assisted CAD quality.

### "Don't Mesh With Me": CSG via Fine-Tuned LLM (2024)

TU Berlin paper targeting CSG — the same representation underlying OpenSCAD. Pipeline: convert BREP geometry to CSG-based Python scripts → generate natural language descriptions with GPT-4o → fine-tune DeepSeek-Coder-1B on 37,000 geometry-description pairs.

Result: the first LLM specifically trained to generate CSG geometry. While output is Python CSG scripts (not OpenSCAD), this demonstrates that **fine-tuning a small model specifically on CSG data dramatically improves parametric geometry generation quality** over general-purpose LLMs.

> **Implication for OpenSCAD:** A model fine-tuned on OpenSCAD code paired with images of corresponding rendered objects would likely achieve similar results. ~37,000 sample dataset size is achievable by scraping Thingiverse/Printables `.scad` files and rendering them programmatically.

### The LLM Spatial Reasoning Problem

A consistent finding across all research: LLMs fundamentally struggle with 3D spatial reasoning. They may generate syntactically valid OpenSCAD code that renders an object with incorrect topology — the right general shape but with holes in the wrong place, dimensions off by a factor, or boolean operations applied in the wrong order.

The DesignBench approach: run multiple LLMs simultaneously, let users select the best result. "Multi-generation with human selection in the loop" acknowledges that LLMs produce a distribution of outputs — the task is to navigate that distribution effectively.

---

## Honest Accuracy Assessment

| Object Type | Code Compiles? | Shape Accuracy | Dimensional Accuracy |
|-------------|--------------|--------------|---------------------|
| Simple box / enclosure | 95–99% | Excellent | ±10–20% without explicit dims |
| Bracket / plate with holes | 90–96% | Good | ±15–25% hole placement |
| Threaded / geared components | 60–80% | Fair | Thread pitch unreliable; specify explicitly |
| Organic / curved shapes | 50–70% | Poor | CSG approximation only |
| Spring / helical geometry | 20–40% | Very Poor | Near zero IoU in all tested models |
| Assemblies (multi-part) | 40–70% | Poor | Inter-part relationships lost |

---

## The Tool Ecosystem

### Three Complementary OpenSCAD MCP Servers

| Server | Core Purpose | Input | Output |
|--------|-------------|-------|--------|
| `jhacksman` | Image/text → 3D model via MVS pipeline | Natural language, images | .scad, STL, OBJ, CSG, AMF |
| `trikos529` | Code quality validation, refactoring, analysis | OpenSCAD code or file path | JSON feedback, analysis results |
| `quellant` | Visual preview generation, renders, animations | OpenSCAD file, camera params | Base64 PNG images, animations |

**Integrated pipeline:** jhacksman generates first draft → trikos529 validates and refactors → quellant generates visual previews for human approval. Maps directly onto the agentic visual feedback loop.

### ScadLM: An Honest Failure Report

ScadLM (KrishKrosh, GitHub) attempted to use a visual transformer for real-time visual feedback during model generation. Their honest assessment: "In the end, it didn't work that well." They also attempted fine-tuning on a labeled dataset of descriptions and OpenSCAD files — the model "didn't learn anything useful," attributed to the dataset being too small and not high quality. This validates that dataset size and quality are critical gating factors for fine-tuning.

---

## Prompt Engineering for Image-to-OpenSCAD

High-performing prompt template:

```
I am showing you [front view / top view / isometric sketch / engineering drawing] of a [object type].

Key dimensions: [W x H x D mm]. Additional measurements: [list any critical dimensions].

The object consists of: [describe the construction sequence — e.g., "a rectangular base plate 
with four M3 mounting holes, a central raised boss, and a cable routing slot along one edge"].

Generate parametric OpenSCAD code with:
- Well-named variables for all key dimensions at the top
- Modules for any repeated geometry
- Comments explaining each section
- Appropriate tolerances for 3D printing (0.2mm wall minimum, 0.4mm clearance for fits)
```

**Tips that work across all pathways:**

- Specify dimensions explicitly — LLMs estimate proportions from images but cannot measure
- Run 3–5 simultaneous generations and pick the best candidate to iterate from
- Always render and critique before accepting results; first generation is rarely good enough
- Decompose complex objects — generate simpler individual components separately
- Provide multiple views — even in Pathway 1, front + side + top dramatically improves accuracy
- Annotate sketches — label key dimensions, angles, and features directly on the image
- Describe construction sequence conceptually, not just appearance

---

## Choosing the Right Pathway for Your Situation

| Your Situation | Best Pathway | Expected Outcome |
|---------------|-------------|-----------------|
| I have a rough idea; no reference object | Pathway 1 or 5 — text/sketch to VLM | Good for simple objects; 30–60 min to acceptable result |
| I have a broken part to recreate | Pathway 1 with calipers + explicit dimensions | Very good if you specify all dimensions |
| I have an engineering sketch or isometric drawing | Pathway 4 — sketch to CAD sequence | Strong results; best-supported input type |
| I have photos of a complex real object | Pathway 3 — photogrammetry chain | Excellent mesh, poor parametric fidelity; expert-level setup |
| I want to match a reference image visually | Pathway 5 — agentic visual loop | Best for iterative convergence; works today with Claude Code |
| I need production-accurate reverse engineering | Pathway 3 + professional 3D scanner | Photogrammetry alone insufficient for high precision |

---

## 18–36 Month Outlook

### Near-Term (6–18 Months)
- Fine-tuned models specifically for OpenSCAD generation will emerge, trained on Thingiverse/Printables `.scad` datasets — expect 20–30% improvement in spatial accuracy
- Integrated maker tools combining Pathway 1 + 5 will appear as VSCode extensions or Claude Code skill packs
- Better photogrammetry preprocessing tools that output CAD-friendly meshes will lower the Pathway 3 barrier
- EvoCAD evolutionary approach will be commercialized — 10–20 design candidates evaluated simultaneously via VLM fitness ranking

### Medium-Term (18–36 Months)
- CAD-Recode and Point2CAD successors become packaged consumer tools — "scan object → get parametric model" as an accessible maker workflow
- Smartphone-quality photogrammetry makes Pathway 3 viable without dedicated DSLR setups
- Multi-modal pipelines combining text, sketch, point cloud, and reference image simultaneously become standard
- Gaussian Splatting + generative NeRF combination expected to turn every smartphone into a 3D scanner — parametric CAD output is the missing last mile

### The OpenSCAD-Specific Opportunity

OpenSCAD's code-as-model approach makes it simultaneously the best and worst target for AI generation.

**Best** because LLMs generate code fluently and the output is fully inspectable, debuggable, and parametrically modifiable.

**Worst** because CSG describes objects constructively — and real-world objects weren't built that way.

The most exciting near-term development: combining the agentic visual feedback loop with better reference-image understanding. When a model can look at a photo, generate CSG code that approximates it, render that code, compare the render to the original image, and iterate — all automatically — the gap between "photo of object" and "working OpenSCAD file" will narrow significantly.

---

## Recommendations

### Immediate Actions (Next 30 Days)

1. **Implement Pathway 5 first** — add visual render feedback to the OpenSCAD MCP server. Highest-ROI capability addable with existing tooling.
2. **Build a multi-view render tool into the MCP:** orthographic front/top/side renders as PNG, returned to Claude Code for vision-based critique.
3. **Create a reference-image-guided prompt template** for the Claude Code skill — structured input for image → OpenSCAD generation with explicit dimension injection.
4. **Test with calibrated example objects:** simple electronic enclosure → bracket with holes → connector housing (increasing complexity).

### Medium-Term (60–90 Days)

1. **Experiment with multi-generation:** run 3–5 OpenSCAD generation attempts per request; implement VLM ranking step to select best candidate before iterating.
2. **Build a photogrammetry front-end experiment:** use phone camera + Meshroom or COLMAP to capture a simple object; attempt Pathway 3 on a test case.
3. **Track CAD-Recode releases:** star `filaPro/cad-recode` on GitHub; monitor for packaged release suitable for workflow integration.

### Content Opportunities

- *"Image to 3D: What Actually Works in 2026"* — the honest comparison video the maker community needs
- *"Building an Agentic OpenSCAD Design Loop with Claude Code"* — practical step-by-step tutorial
- *"Photogrammetry + AI CAD: From Phone Camera to Printable Part"* — aspirational/experimental content
- *"Fine-Tuning a Model on My Own OpenSCAD Library"* — advanced maker content for AI Lab audience

---

## Summary

| Pathway | Works Today? | Best For | Key Limitation |
|---------|------------|---------|---------------|
| 1. Direct VLM | ✅ Yes | Simple prismatic objects | No dimensional accuracy; spatial reasoning weak |
| 2. Multi-View MVS | ⚠️ With effort | Automated pipeline exploration | Mesh-to-CSG gap; CUDA required |
| 3. Photogrammetry + Point Cloud | 🔬 Research | High-fidelity reverse engineering | Expert setup; 12–24 months to accessibility |
| 4. Sketch / Drawing | ✅ Emerging | Structured sketch inputs | Requires fine-tuned specialist models |
| 5. Agentic Loop | ✅ Best option | Iterative convergence to reference | Organic shapes out of reach |

The maker who combines all five pathways intelligently — using VLM prompting for quick starts, visual feedback loops for iteration, photogrammetry awareness for real-object work, and sketch inputs when possible — will be significantly more productive than one who relies on any single approach.

The technology is ready for makers to experiment with and iterate. It is not ready to replace human judgment, precise measurement, or the full design process. But as an accelerator for rapid prototyping and early-stage iteration, it is genuinely transformative today.

---

*Research compiled March 2026 · Sources: arXiv, GitHub, Medium, academic conference proceedings (CVPR 2024, ECCV 2024, NeurIPS 2024, ICCV 2025)*
