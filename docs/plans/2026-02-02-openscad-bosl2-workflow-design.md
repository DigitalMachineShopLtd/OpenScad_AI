# OpenSCAD + BOSL2 Workflow Design

**Date:** 2026-02-02
**Status:** Approved
**Approach:** Hybrid Visual Workflow

## Overview

This design establishes a workflow for creating high-quality 3D printable models using OpenSCAD with the BOSL2 library, combining visual feedback from OpenSCAD GUI with AI-assisted coding in Claude Code, and automated validation/slicing pipeline.

## System Environment

- **OpenSCAD:** 2024.10.18 (CLI available at `/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD`)
- **BOSL2:** v2.0.716 (installed at `~/Documents/OpenSCAD/libraries/BOSL2`)
- **Bambu Studio:** CLI available at `/Applications/BambuStudio.app/Contents/MacOS/BambuStudio`
- **Platform:** macOS (Darwin 25.2.0)

## User Context

- **Experience:** Knows OpenSCAD basics, new to BOSL2
- **Goals:** Create mechanical parts, artistic objects, and parametric prototypes
- **Quality Requirements:** Full validation workflow including manifold checks and slicing preview
- **Workflow Preference:** Visual feedback during development, automated validation before printing

## Design Approach: Hybrid Visual Workflow

### Core Principles

1. **Visual feedback first** - OpenSCAD GUI provides immediate visual preview
2. **AI-assisted learning** - Claude Code helps learn BOSL2 through examples
3. **Automation for quality** - Scripts catch errors before printing
4. **Organized by intent** - Clear separation of designs, outputs, and tooling

### The Development Cycle

```
Edit .scad in Claude Code
         ↓
      Save file
         ↓
OpenSCAD GUI auto-reloads (F5/F6)
         ↓
   Visual feedback
         ↓
    Iterate quickly
```

## Project Structure

```
OpenScad_AI/
├── designs/              # Source .scad files (version controlled)
│   ├── mechanical/      # Gears, brackets, enclosures, functional parts
│   ├── artistic/        # Decorative objects, sculptures, containers
│   └── prototypes/      # Experimental and parametric designs
├── output/              # Generated files (gitignored)
│   ├── stl/            # Rendered STL files for printing
│   ├── png/            # Preview images for documentation
│   └── gcode/          # Sliced files ready for printer (optional)
├── templates/           # Starting points for new designs
│   ├── basic.scad      # Minimal BOSL2 template
│   ├── mechanical-part.scad  # Functional part with mounting holes
│   └── parametric.scad # Customizer-enabled design
├── scripts/             # Automation tools
│   ├── validate.sh     # Check design quality and printability
│   ├── render.sh       # Generate high-quality STL files
│   └── slice.sh        # Prepare for printing with Bambu Studio
├── docs/                # Documentation and references
│   ├── HOW-TO-USE.md   # User guide for the workflow
│   ├── bosl2-quickref.md  # Common BOSL2 patterns and functions
│   └── plans/          # Design documents
└── .gitignore           # Exclude output/ directory
```

## Component Details

### 1. Development Workflow

**OpenSCAD GUI Setup:**
- Open .scad file in OpenSCAD GUI at session start
- Enable "Design → Automatic Reload and Preview"
- Position window for visibility while coding
- F5 for quick preview (fast, lower quality)
- F6 for full render (slower, precise)

**Claude Code Integration:**
- User describes intent in natural language
- AI generates BOSL2 code with explanations
- User saves → GUI updates → instant visual feedback
- Iterative refinement with AI assistance
- Learn BOSL2 patterns through doing

**Typical session:**
1. Open design file in both Claude Code and OpenSCAD GUI
2. Enable auto-reload in OpenSCAD
3. Describe desired changes to AI
4. Review generated code and save
5. See results in GUI within 1-2 seconds
6. Refine and iterate

### 2. AI Assistance Strategy

**Learning BOSL2:**
- AI provides code examples with explanations
- Parameters and alternatives are discussed
- Best practices embedded in generated code
- Debugging assistance when errors occur
- Incremental complexity building

**Code generation includes:**
- Proper BOSL2 function usage
- Parameter explanations
- Manifold geometry practices
- Attachment and transformation patterns
- Comments explaining non-obvious logic

### 3. Validation Pipeline

**`validate.sh` - Pre-print Quality Checks**

Validates design before committing to print:
- **Syntax check:** OpenSCAD compiles without errors
- **Manifold geometry:** All edges properly connected (required for printing)
- **Wall thickness:** Detects sections too thin to print reliably
- **Overhang analysis:** Identifies steep angles needing supports
- **Dimensions:** Verifies model fits printer build volume
- **STL export:** Confirms clean export without errors

**Usage:**
```bash
./scripts/validate.sh designs/mechanical/bracket.scad
```

**`render.sh` - High-Quality STL Generation**

Creates print-ready STL files:
- High resolution rendering (fine detail)
- Preview PNG generation for documentation
- STL mesh optimization for smaller files
- Timestamped outputs for version tracking

**Usage:**
```bash
./scripts/render.sh designs/mechanical/bracket.scad
# Output: output/stl/bracket.stl
#         output/png/bracket.png
```

### 4. Slicing Integration

**`slice.sh` - Bambu Studio CLI Automation**

Prepares validated models for printing:
- Uses existing Bambu Studio profiles
- Interactive profile selection or command-line specification
- Generates preview images (layers, supports)
- Estimates print time and filament usage
- Creates printer-ready files

**Usage:**
```bash
# Interactive mode
./scripts/slice.sh output/stl/bracket.stl

# With specific profile
./scripts/slice.sh output/stl/bracket.stl --profile "PLA Standard"
```

**Profile management:**
- Leverages user's saved Bambu Studio profiles
- Profiles include: material, layer height, supports, infill, speeds
- Preview option opens GUI for final review before printing

**Complete pipeline:**
```bash
./scripts/validate.sh designs/mechanical/bracket.scad
./scripts/render.sh designs/mechanical/bracket.scad
./scripts/slice.sh output/stl/bracket.stl
```

### 5. Templates System

**Purpose:** Accelerate new design creation with proven starting points

**`basic.scad`**
- Minimal BOSL2 template
- Essential includes and basic structure
- Starting point for simple objects

**`mechanical-part.scad`**
- Functional print template
- Includes: mounting holes, rounded edges, attachment points
- Clearance gaps for assembly
- Parametric dimensions

**`parametric.scad`**
- OpenSCAD Customizer support
- Adjustable parameters in GUI
- Easy variant generation
- Documentation of parameters

**Usage:**
```bash
cp templates/mechanical-part.scad designs/mechanical/my-design.scad
open -a OpenSCAD designs/mechanical/my-design.scad
# Edit with AI assistance in Claude Code
```

### 6. Documentation

**`HOW-TO-USE.md`**
- Step-by-step workflow guide
- Common tasks and examples
- Troubleshooting tips
- Quick reference for scripts

**`bosl2-quickref.md`**
- Frequently used BOSL2 functions
- Common patterns and idioms
- Parameter explanations
- Links to full documentation

## Workflow Examples

### Creating a new mechanical part

```bash
# 1. Start from template
cp templates/mechanical-part.scad designs/mechanical/motor-mount.scad

# 2. Open in OpenSCAD GUI
open -a OpenSCAD designs/mechanical/motor-mount.scad

# 3. Edit with AI in Claude Code
# "I need a motor mount for NEMA 17, with 4 mounting holes"
# AI generates BOSL2 code, you save, GUI updates

# 4. Iterate until design looks good

# 5. Validate before printing
./scripts/validate.sh designs/mechanical/motor-mount.scad

# 6. Render high-quality STL
./scripts/render.sh designs/mechanical/motor-mount.scad

# 7. Slice for printing
./scripts/slice.sh output/stl/motor-mount.stl
```

### Quick iteration on existing design

```bash
# GUI already open with your design
# In Claude Code: "make the mounting holes 0.5mm larger"
# AI updates code, you save
# GUI reloads instantly
# Visual verification in 1-2 seconds
```

## Trade-offs and Decisions

### Why Hybrid over IDE-Integrated?

**Chosen:** Hybrid Visual Workflow
**Alternative:** Pure IDE-integrated with CLI preview

**Reasoning:**
- Visual feedback accelerates learning for BOSL2 beginners
- Immediate visual verification reduces iteration cycles
- OpenSCAD GUI provides familiar reference while learning
- User specifically wanted visual approach (Approach C: both quick and detailed previews)

**Trade-offs accepted:**
- Context switching between windows (minimal with auto-reload)
- Slightly slower than pure CLI workflow
- Requires managing two applications

### Why Script-Based Automation?

**Chosen:** Shell scripts for validation/render/slice
**Alternative:** Integrated development commands or Make-based system

**Reasoning:**
- Simple, transparent, easy to understand
- Low barrier to customization
- Works with existing tools (no new dependencies)
- Clear separation of concerns
- Easy to run individually or chain together

## Success Criteria

The workflow is successful if:
1. ✅ User can start designing within 5 minutes of setup
2. ✅ Visual feedback appears within 2 seconds of saving
3. ✅ AI assistance accelerates BOSL2 learning
4. ✅ Validation catches common print issues before slicing
5. ✅ Complete design-to-print pipeline is < 5 commands
6. ✅ Templates provide good starting points for common tasks
7. ✅ Documentation enables independent problem-solving

## Implementation Priorities

1. **Core structure** - Create directories, .gitignore
2. **Scripts** - validate.sh, render.sh, slice.sh (with proper error handling)
3. **Templates** - Three starter files with documentation
4. **Documentation** - HOW-TO-USE.md with examples, bosl2-quickref.md
5. **Verification** - Test complete workflow with sample design

## Future Enhancements (Out of Scope)

- Watch mode for truly automatic preview (after initial workflow validated)
- Web-based preview interface (if GUI becomes limiting)
- Design library with reusable components
- Git hooks for automatic validation
- CI/CD for design testing
- STL comparison tools for design versioning

## References

- OpenSCAD Documentation: https://openscad.org/documentation.html
- BOSL2 Documentation: https://github.com/BelfrySCAD/BOSL2/wiki
- Bambu Studio CLI: Built-in help via `--help` flag
