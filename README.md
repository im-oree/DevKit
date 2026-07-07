# DevKit — Portable Project Ops Toolkit

A single-folder utility for scripted, safe, auto-backed-up project edits.
Drop it into ANY project root — React, Node, Python, anything.

Built to make AI-assisted coding sessions faster and safer: your AI sends
a compact script, you paste it in, preview the diff, then apply with one
click. Undo is one click away.

## Requirements
- Python 3.8+ (stdlib only)
- Optional: pip install pyinstaller (for portable .exe)

## Setup
Place the devkit folder anywhere:
- Global: C:\Tools\devkit\  then  python C:\Tools\devkit\devkit.py
- Per-project: copy inside your project root
- Portable exe: run build_exe.bat  ->  dist\DevKit.exe

## Launching
| Method                                | Result                    |
|---------------------------------------|---------------------------|
| python devkit.py                      | GUI                       |
| devkit.bat                            | GUI (Windows)             |
| DevKit.exe                            | GUI (portable)            |
| python devkit.py run script.dk        | Run script (CLI)          |
| python devkit.py preview script.dk    | Preview only (CLI)        |
| python devkit.py tree                 | Print project tree        |
| python devkit.py undo                 | Restore last backup       |
| python devkit.py sessions             | List backup sessions      |
| python devkit.py --help               | Full reference            |

Keyboard: F5 = Run, Ctrl+Enter = Preview

## Working with an AI

1. Click Macros -> Copy ALL-IN-ONE and paste into a new AI chat.
   The AI now knows your project tree + full DevKit syntax.

2. Ask for work. The AI sends a context script first:
       :READ src/App.tsx
       :SEARCH "TODO" --in src --ext .ts,.tsx
       :TREE src/pages --depth 2

3. Preview -> Run -> Copy all output -> paste back to AI.

4. AI now sends the actual edit script. Preview, then Run.

5. Anything wrong? Click Undo last.

## Macros dropdown
| Button                       | What it copies                          |
|------------------------------|-----------------------------------------|
| Copy Project Tree (3)        | Folder tree, depth 3                    |
| Copy Project Tree (5)        | Folder tree, depth 5                    |
| Copy AI Collab Prompt        | Instructions + tree + syntax            |
| Copy AI Syntax Reference     | Syntax cheat sheet only                 |
| Copy ALL-IN-ONE              | Everything merged                       |

## Script Syntax

Inline ops:
    DELETE  src/**/*.bak
    RENAME  src/old.ts -> src/new.ts
    MKDIR   src/newfolder
    RUN     npm install lodash
    INSTALL react-query
    GITADD  .
    GITCOMMIT "feat: subscription system"

Block ops (end with :END):
    :CREATE path/to/file
    <content>
    :END

    :WRITE path/to/file
    <content>
    :END

    :APPEND path/to/file
    <content>
    :END

    :REPLACE path/to/file
    FIND:
    old exact text
    WITH:
    new text
    :END

    :REGEX_REPLACE path/to/file
    FIND: pattern\s+here
    WITH: replacement
    :END

    :REPLACE_BLOCK path/to/file
    FROM: // START
    TO:   // END
    WITH:
    replacement
    :END

    :INSERT_AFTER path/to/file
    FIND:
    anchor line
    WITH:
    inserted after
    :END

    :MULTI_REPLACE path/to/file
    FIND:
    old A
    WITH:
    new A
    ---
    FIND:
    old B
    WITH:
    new B
    :END

Read ops (output only):
    :TREE src --depth 3 --exclude node_modules
    :READ src/App.tsx src/main.tsx
    :SEARCH "TODO" --in src --ext .ts,.tsx
    :LIST src/**/*.module.css
    :INFO src/App.tsx

## Backups & Undo
Every run backs up changed files to:
    <project>/.devkit-backups/<YYYYMMDD-HHMMSS>/

Restore latest:      python devkit.py undo
List sessions:       python devkit.py sessions
Restore specific:    python devkit.py undo 20260707-143012

Auto-pruned to last 20 sessions.

Add to .gitignore:
    .devkit-backups/
    devkit/

## Always Preview First
- GUI: Ctrl+Enter or click Preview
- CLI: python devkit.py preview script.dk

Shows every file that would be created / changed / deleted, plus a diff
for each content change. Only Run (F5) actually writes.

## File Layout
    devkit/
    |-- devkit.py               entry point
    |-- devkit.bat              Windows launcher
    |-- build_exe.bat           PyInstaller build
    |-- README.md               this file
    |-- devkit_core/
    |   |-- parser.py           script -> Operation objects
    |   |-- ops.py              operation executors
    |   |-- runner.py           orchestration
    |   |-- backup.py           auto-backup + undo
    |   |-- cli.py              CLI
    |   |-- gui.py              Tkinter GUI
    |   |-- manual.py           built-in manual
    |   `-- macros.py           AI collab prompts
    `-- examples/
        |-- hello.dk
        |-- context.dk
        `-- add_feature.dk

## Troubleshooting
| Symptom                   | Fix                                        |
|---------------------------|--------------------------------------------|
| File not found            | Check Project folder — paths are relative  |
| FIND text not found       | Whitespace differs — use :READ first       |
| GUI won't open            | python devkit.py --cli                     |
| .exe shows old version    | Re-run build_exe.bat                       |
| Backups filling disk      | Auto-pruned; delete .devkit-backups/       |

## License
Do whatever you want with it.
