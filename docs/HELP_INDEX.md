# SCADA Scout - Help & Documentation Index

Welcome to SCADA Scout's comprehensive documentation system. This index provides quick access to all guides, tutorials, and reference materials.

## 📚 Quick Access

| Shortcut | Document | Description |
|----------|----------|-------------|
| **F1** | README | Main project documentation |
| **Shift+F1** | Scripting Guide | Python automation guide |
| **Ctrl+F1** | PLC IDE Quick Start | Get started with IEC 61131-3 |
| **Ctrl+Shift+A** | AI Assistant | Interactive help system |
| **Ctrl+Shift+P** | PLC IDE | Open PLC development environment |
| **Ctrl+Shift+D** | Script IDE | Open advanced script editor |

---

## 🎯 Getting Started

### New Users
1. **[README.md](../README.md)** - Project overview, installation, first steps
2. **[Install Guides](install_guides.md)** - Platform-specific installation instructions
3. **[Complete Project Structure](complete_project_structure.md)** - Understanding the codebase

### Quick Start Guides
- **[PLC IDE Quick Start](PLC_IDE_QUICKSTART.md)** ⭐ - Learn IEC 61131-3 programming in 5 minutes
- **[Scripting Guide](script_user_guide.md)** - Automate with Python scripts
- **[Modbus Usage Guide](modbus_usage_guide.md)** - Connect to Modbus devices

---

## 🏭 Protocol Guides

### Modbus
- **[Modbus Usage Guide](modbus_usage_guide.md)** - Client/master operations
- **[Modbus Slave Guide](modbus_slave_guide.md)** - Server/slave simulator

### IEC 61850
- See PLC IDE documentation for IEC 61850 integration
- Architecture documentation includes protocol gateway examples

---

## 💻 Development Guides

### PLC Programming (IEC 61131-3)

#### Phase 1: Foundations
- **[PLC IDE Quick Start](PLC_IDE_QUICKSTART.md)** ⭐ - Your first program
  - Basic syntax and variables
  - Compilation and execution
  - Variable monitoring
  - Sample programs

- **[PLC IDE Architecture](PLC_IDE_ARCHITECTURE.md)** 📐 - System design
  - Component architecture
  - Data models and types
  - Execution model
  - Scan cycle details

- **[PLC IDE Implementation Summary](PLC_IDE_IMPLEMENTATION_SUMMARY.md)** - Phase 1 details
  - Features delivered
  - File structure
  - Integration points
  - Testing results

#### Phase 2: Advanced Features ⭐ NEW!
- **[PLC IDE Phase 2 Summary](PLC_IDE_PHASE2_SUMMARY.md)** 🎉 - Latest features
  - **Control Flow**: IF/FOR/WHILE/CASE/REPEAT
  - **Debugging**: Breakpoints, stepping, watch expressions
  - **Online Change**: Hot-reload running programs
  - **Function Blocks**: Reusable code components
  - **Professional UI**: Breakpoint gutter, call stack, debug toolbar

**Key Phase 2 Features:**
```st
(* Control Flow Example *)
IF temperature < 20.0 THEN
    mode := HEATING;
ELSIF temperature > 30.0 THEN
    mode := COOLING;
ELSE
    mode := NORMAL;
END_IF;

(* FOR Loop *)
FOR i := 1 TO 10 BY 1 DO
    sum := sum + i;
END_FOR;
```

### Python Scripting

- **[Scripting Guide](script_user_guide.md)** - Python automation basics
  - Writing device scripts
  - Event handling
  - Signal reading/writing
  - Best practices

- **[Script IDE Guide](SCRIPT_IDE_GUIDE.md)** - Advanced script development
  - Full-featured IDE
  - Debugging capabilities
  - Template library
  - Integration with devices

---

## 🔧 Advanced Topics

### System Architecture
- **[PLC IDE Architecture](PLC_IDE_ARCHITECTURE.md)** - Deep technical dive
- **[Complete Project Structure](complete_project_structure.md)** - Codebase organization

### Integration
- **[OPC Integration](opc_integration.md)** - OPC UA/DA connectivity
- **Protocol Gateway** - See PLC IDE Architecture, Chapter 7

### Deployment
- **[GitHub Deploy](github_deploy.md)** - Version control and deployment
- **[GitHub Structure](github_structure.md)** - Repository organization

---

## 📖 Reference Documentation

### By Feature

#### Device Management
- Adding devices
- Connection management
- Protocol selection
- Signal discovery

#### Signal Monitoring
- Real-time updates
- Data logging
- Quality indicators
- Timestamp tracking

#### Automation
- Python scripts (per-device)
- IEC 61131-3 programs (PLC IDE)
- Script IDE (advanced)
- Scheduling and triggers

#### Debugging Tools
- **PLC Debugging**:
  - Breakpoints (F9)
  - Step Into (F11)
  - Step Over (F10)
  - Continue (F8)
  - Watch expressions
  - Call stack
  - Variable inspector

- **Script Debugging**:
  - Console output
  - Error logging
  - Event tracking

#### Data Export
- CSV export
- JSON configuration
- Session logging

---

## 🆘 Help & Support

### Interactive Help
- **AI Assistant** (Ctrl+Shift+A) - Ask questions about:
  - Protocol analysis
  - Device troubleshooting
  - Configuration help
  - Best practices
  - Code examples

### Documentation Search
1. Use your markdown viewer's search (Ctrl+F)
2. Check the relevant guide from the menu
3. Refer to code examples in Quick Start guides

### Common Tasks

| Task | Documentation | Shortcut |
|------|---------------|----------|
| Add a device | README → Getting Started | - |
| Write a PLC program | PLC IDE Quick Start | Ctrl+F1 |
| Debug PLC code | PLC Phase 2 Summary | F9-F11 |
| Automate tasks | Scripting Guide | Shift+F1 |
| Connect Modbus | Modbus Usage Guide | - |
| Hot-reload code | PLC Phase 2 → Online Change | - |
| Set breakpoints | PLC Phase 2 → Debugging | F9 |

---

## 📊 Feature Matrix

### PLC IDE Capabilities

| Feature | Phase 1 | Phase 2 | Documentation |
|---------|---------|---------|---------------|
| Basic ST Programming | ✅ | ✅ | Quick Start |
| Variables (I/O/Local) | ✅ | ✅ | Quick Start |
| Compilation | ✅ | ✅ | Architecture |
| Runtime Execution | ✅ | ✅ | Architecture |
| Variable Monitoring | ✅ | ✅ | Quick Start |
| **Control Flow** | ❌ | ✅ | Phase 2 Summary |
| **Debugging** | ❌ | ✅ | Phase 2 Summary |
| **Online Change** | ❌ | ✅ | Phase 2 Summary |
| **Function Blocks** | ❌ | ✅ | Phase 2 Summary |
| Ladder Diagram (LD) | ❌ | 🔜 Phase 3 | Roadmap |
| FBD Editor | ❌ | 🔜 Phase 3 | Roadmap |

### Control Flow Support

| Statement | Supported | Example |
|-----------|-----------|---------|
| IF/THEN/ELSE | ✅ | `IF x > 10 THEN y := 5; END_IF;` |
| ELSIF | ✅ | `IF...ELSIF...ELSE...END_IF` |
| FOR | ✅ | `FOR i := 1 TO 10 BY 2 DO...END_FOR` |
| WHILE | ✅ | `WHILE x < 100 DO...END_WHILE` |
| REPEAT/UNTIL | ✅ | `REPEAT...UNTIL x > 50 END_REPEAT` |
| CASE/OF | ✅ | `CASE selector OF 1: ... END_CASE` |

### Debug Features

| Feature | Shortcut | Status |
|---------|----------|--------|
| Toggle Breakpoint | F9 | ✅ |
| Step Into | F11 | ✅ |
| Step Over | F10 | ✅ |
| Continue | F8 | ✅ |
| Watch Expressions | - | ✅ |
| Call Stack | - | ✅ |
| Conditional Breakpoints | - | ✅ |
| Breakpoint Gutter | Click | ✅ |

---

## 🎓 Learning Path

### Beginner
1. Read README.md
2. Follow PLC IDE Quick Start
3. Try example programs
4. Explore Scripting Guide

### Intermediate
1. Study PLC IDE Architecture
2. Learn Phase 2 control flow
3. Practice debugging techniques
4. Explore Script IDE

### Advanced
1. Review Phase 2 Implementation
2. Create function blocks
3. Use online change feature
4. Build protocol gateways

---

## 📝 Documentation Updates

### Latest Additions (February 2, 2026)
- ✨ **PLC IDE Phase 2 Summary** - Advanced features guide
- 🐛 **Debugging Guide** - Complete debugging workflow
- 🔄 **Online Change** - Hot-reload documentation
- 🎯 **Control Flow** - IF/FOR/WHILE/CASE examples

### Recently Updated
- PLC IDE Quick Start - Enhanced with Phase 2 examples
- Scripting Guide - Updated best practices
- Modbus Guide - Extended coverage

---

## 🔍 Quick Reference

### File Locations
- Documentation: `docs/*.md`
- Examples: `examples/`
- Tests: `test_*.py`
- Source: `src/`

### Key Directories
```
scada_scout/
├── docs/              ← All documentation here
│   ├── PLC_IDE_*.md   ← PLC programming guides
│   ├── script_*.md    ← Python scripting guides
│   └── modbus_*.md    ← Protocol guides
├── examples/          ← Sample programs
└── src/               ← Source code
```

### Menu Shortcuts
- **Help → Documentation (README)** - F1
- **Help → Scripting Guide** - Shift+F1
- **Help → PLC IDE Quick Start** - Ctrl+F1
- **Help → AI Assistant** - Ctrl+Shift+A

---

## 💡 Tips & Tricks

### PLC Development
- Use F7 to compile before F5 run
- F9 on any line to toggle breakpoint
- Ctrl+S saves current program
- Variables update at 2Hz (500ms)

### Debugging
- Click line number gutter to set breakpoints
- Use watch expressions for complex calculations
- Call stack shows execution hierarchy
- Step Over (F10) for function calls

### Performance
- Minimize scan cycle time for responsiveness
- Use local variables for temporary data
- Prefer FOR loops over WHILE for bounded iteration

---

## 📧 Additional Resources

### Community
- GitHub Issues - Bug reports and feature requests
- Documentation feedback - Suggest improvements

### Contributing
- See CONTRIBUTING.md (if available)
- Submit documentation improvements
- Share example programs

---

**Need help?** Press **Ctrl+Shift+A** to launch the AI Assistant for interactive guidance!

**Getting started?** Press **Ctrl+F1** for the PLC IDE Quick Start guide!

**Exploring features?** Check the **Help** menu for all available documentation!
