# OpenSCAD BOSL2 Workflow

Professional workflow for creating high-quality 3D printable models with OpenSCAD, BOSL2, and AI assistance.

## Features

✨ **Hybrid Visual Workflow** - Edit with AI assistance, see changes instantly in OpenSCAD GUI
🤖 **AI-Powered Learning** - Learn BOSL2 through examples and explanations
✅ **Quality Validation** - Automated checks for manifold geometry and printability
🎯 **Ready-to-Use Templates** - Quick start for common design types
🔧 **Bambu Studio Integration** - Streamlined slicing pipeline
📚 **Comprehensive Docs** - How-to guide and BOSL2 quick reference

## Quick Start

### 1. Start a New Design

```bash
# Copy a template
cp templates/basic.scad designs/mechanical/my-part.scad

# Open in OpenSCAD GUI
open -a OpenSCAD designs/mechanical/my-part.scad

# Enable "Design → Automatic Reload and Preview"
```

### 2. Edit with AI Assistance

Describe what you want to Claude Code:
- "Create a bracket with 4 mounting holes"
- "Add a cylindrical standoff on top"
- "Make the edges more rounded"

AI generates BOSL2 code → Save → OpenSCAD updates instantly!

### 3. Validate and Print

```bash
# Check design quality
./scripts/validate.sh designs/mechanical/my-part.scad

# Create print-ready STL
./scripts/render.sh designs/mechanical/my-part.scad

# Slice for printing
./scripts/slice.sh output/stl/my-part.stl
```

## Project Structure

```
OpenScad_AI/
├── designs/          # Your .scad designs (version controlled)
│   ├── mechanical/  # Functional parts
│   ├── artistic/    # Decorative objects
│   └── prototypes/  # Experimental designs
│
├── output/          # Generated files (gitignored)
│   ├── stl/        # Print-ready STL files
│   ├── png/        # Preview images
│   └── gcode/      # Sliced files
│
├── templates/       # Starting points
│   ├── basic.scad
│   ├── mechanical-part.scad
│   └── parametric.scad
│
├── scripts/         # Automation tools
│   ├── validate.sh # Design quality checks
│   ├── render.sh   # STL generation
│   └── slice.sh    # Slicing preparation
│
└── docs/           # Documentation
    ├── HOW-TO-USE.md
    └── bosl2-quickref.md
```

## Documentation

- **[How-To Guide](docs/HOW-TO-USE.md)** - Complete workflow guide
- **[BOSL2 Quick Reference](docs/bosl2-quickref.md)** - Common patterns and examples
- **[Sample Bracket](designs/examples/sample-bracket.scad)** - Example design

## Scripts

### validate.sh - Design Quality Checks

```bash
./scripts/validate.sh designs/mechanical/my-part.scad
```

Validates:
- ✓ Syntax - Will OpenSCAD compile it?
- ✓ STL Export - Can it generate a valid STL?
- ✓ Manifold Geometry - Are all edges connected?

### render.sh - High-Quality STL Generation

```bash
./scripts/render.sh designs/mechanical/my-part.scad
```

Creates:
- `output/stl/my-part.stl` - Print-ready STL
- `output/png/my-part.png` - Preview image

### slice.sh - Slicing Preparation

```bash
./scripts/slice.sh output/stl/my-part.stl
```

Prepares file for Bambu Studio slicing.

## Templates

**basic.scad** - Simple designs, quick prototypes
**mechanical-part.scad** - Functional parts with mounting holes
**parametric.scad** - Configurable designs with Customizer support

## Requirements

- **OpenSCAD** 2024.10.18+ with CLI access
- **BOSL2** v2.0.716+ installed in OpenSCAD libraries
- **Bambu Studio** (for slicing)
- **macOS** (scripts use macOS paths)

## System Setup

OpenSCAD CLI: `/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD`
BOSL2 Location: `~/Documents/OpenSCAD/libraries/BOSL2`
Bambu Studio CLI: `/Applications/BambuStudio.app/Contents/MacOS/BambuStudio`

## Workflow

1. **Design** - Edit .scad files with AI assistance
2. **Preview** - OpenSCAD GUI shows changes instantly (auto-reload)
3. **Iterate** - Make changes, save, see results in 1-2 seconds
4. **Validate** - Run quality checks before printing
5. **Render** - Generate high-quality STL
6. **Slice** - Prepare for your printer
7. **Print** - High-quality 3D prints!

## Tips

- Keep OpenSCAD GUI open with auto-reload enabled
- Use F5 for quick preview, F6 for full render
- Always validate before printing
- Start from templates for faster development
- Ask Claude Code for help with BOSL2 syntax
- Add 0.2mm clearance for parts that fit together

## Resources

- [BOSL2 Documentation](https://github.com/BelfrySCAD/BOSL2/wiki)
- [OpenSCAD Manual](https://openscad.org/documentation.html)
- [BOSL2 Tutorial](https://github.com/BelfrySCAD/BOSL2/wiki/Tutorial-Getting-Started)

## License

This workflow setup is provided as-is for personal and commercial use.

BOSL2 is licensed under BSD 2-Clause License.

---

**Ready to create amazing 3D prints! 🚀**

See [docs/HOW-TO-USE.md](docs/HOW-TO-USE.md) for the complete guide.
