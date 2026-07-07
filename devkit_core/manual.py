"""Built-in manual, printable or shown in GUI."""

MANUAL = r"""
════════════════════════════════════════════════════════════════
 DevKit v1.0 — Portable Project Ops Toolkit
════════════════════════════════════════════════════════════════

USAGE
─────
  python devkit.py                    Launch GUI
  python devkit.py --cli              Interactive CLI
  python devkit.py run script.dk      Execute script file
  python devkit.py preview script.dk  Preview without changes
  python devkit.py tree               Print project tree
  python devkit.py undo               Restore last backup session
  python devkit.py sessions           List backup sessions
  python devkit.py --help             Show this manual

SCRIPT SYNTAX
─────────────
DevKit reads a plain-text script of operations. Two styles:

  # Inline ops (one line)
    DELETE src/**/*.bak
    RENAME src/foo.ts -> src/bar.ts
    MKDIR src/new/folder
    RUN npm install lodash
    GITADD .
    GITCOMMIT "add new feature"

  # Block ops (multi-line, terminated by :END)
    :CREATE path/to/file.ext
    <file contents>
    :END

Comments start with '#'.  Blank lines outside blocks are ignored.

────────────────────────────────────────────────────────────────
FILE OPERATIONS
────────────────────────────────────────────────────────────────

:CREATE <path>
    Create a new file. Fails if it already exists (use :WRITE to
    overwrite).

    :CREATE src/hooks/useX.ts
    export function useX() { return 42; }
    :END

:WRITE <path>
    Create or overwrite a file with the given content.

:APPEND <path>
    Append content to the end of a file.

:PREPEND <path>
    Insert content at the start of a file.

DELETE <pattern>
    Delete files. Supports glob patterns (*, **, ?, [abc]).
    Backed up before deletion.

    DELETE src/**/*.bak
    DELETE src/legacy/old.ts

RENAME <src> -> <dst>
MOVE   <src> -> <dst>
    Rename or move a file.

MKDIR <path>
    Create directory (recursive, no error if exists).

────────────────────────────────────────────────────────────────
CONTENT OPERATIONS
────────────────────────────────────────────────────────────────

:REPLACE <path>
    Literal find-and-replace. Fails if FIND text not found.

    :REPLACE src/App.tsx
    FIND:
    <HelpFab />
    WITH:
    <HelpFab /><SubscriptionModal />
    :END

:REGEX_REPLACE <path>
    Regex find-and-replace (MULTILINE mode enabled).

    :REGEX_REPLACE src/config.ts
    FIND: version:\s*"[^"]*"
    WITH: version: "2.0.0"
    :END

:REPLACE_BLOCK <path>
    Replace everything between (and including) two marker lines.

    :REPLACE_BLOCK src/routes.tsx
    FROM: // START_ROUTES
    TO:   // END_ROUTES
    WITH:
    // START_ROUTES
    <Route path="/x" element={<X />} />
    // END_ROUTES
    :END

:INSERT_AFTER <path>
:INSERT_BEFORE <path>
    Insert content immediately after (or before) an anchor.

    :INSERT_AFTER src/index.ts
    FIND:
    import { foo } from './foo';
    WITH:
    import { bar } from './bar';
    :END

:MULTI_REPLACE <path>
    Multiple literal replacements in one file. Separate pairs
    with a line of '---'.

    :MULTI_REPLACE src/config.ts
    FIND:
    OLD_A
    WITH:
    NEW_A
    ---
    FIND:
    OLD_B
    WITH:
    NEW_B
    :END

────────────────────────────────────────────────────────────────
READ / INSPECTION OPERATIONS
────────────────────────────────────────────────────────────────

:TREE [path] [--depth N] [--include *.ts,*.tsx] [--exclude foo,bar]
    Print a directory tree. Excludes node_modules, .git, dist,
    build, __pycache__ by default.

    :TREE src --depth 3
    :TREE . --include *.ts,*.tsx,*.css

:READ path1 path2 path3 ...
    Dump contents of multiple files with clear separators.
    Great for gathering context.

    :READ src/App.tsx src/routes/AppRouter.tsx

:SEARCH "text" [--in path] [--ext .ts,.tsx]
    Find literal text across files (like grep).

    :SEARCH "useTutorial" --in src --ext .ts,.tsx

:LIST <glob-pattern>
    List files matching a glob.

    :LIST src/**/*.module.css

:INFO <path>
    Show file size, LOC, modified time.

────────────────────────────────────────────────────────────────
UTILITY OPERATIONS
────────────────────────────────────────────────────────────────

RUN <shell command>
    Execute an arbitrary shell command in the project root.
    5-minute timeout.

INSTALL <packages>
    Auto-detects npm or pip and installs.

GITADD <path>          Same as: RUN git add <path>
GITCOMMIT "<message>"  Same as: RUN git commit -m "<message>"

────────────────────────────────────────────────────────────────
BACKUPS & UNDO
────────────────────────────────────────────────────────────────

Every operation that modifies a file automatically backs up the
original into:

    <project>/.devkit-backups/<timestamp>/

Each script run creates ONE session folder. To undo the LAST
session:

    python devkit.py undo

To pick a specific session:

    python devkit.py sessions
    python devkit.py undo 20260707-143012

Only the last 20 sessions are kept (older auto-pruned).

────────────────────────────────────────────────────────────────
DRY-RUN / PREVIEW
────────────────────────────────────────────────────────────────

Preview without making changes:

    python devkit.py preview script.dk

In the GUI, click "Preview" first to see:
  • Every file that will be created/changed/deleted
  • Unified diff of every content change
  • Any errors before they happen

Only when you click "Run" are changes actually applied.

────────────────────────────────────────────────────────────────
EXAMPLES
────────────────────────────────────────────────────────────────

# Example 1: Add a new hook + wire it up
:CREATE src/hooks/useFoo.ts
import { useState } from 'react';
export function useFoo() { return useState(0); }
:END

:REPLACE src/App.tsx
FIND:
import { useBar } from './hooks/useBar';
WITH:
import { useBar } from './hooks/useBar';
import { useFoo } from './hooks/useFoo';
:END

# Example 2: Clean up old backups & rename a file
DELETE src/**/*.bak
RENAME src/OldName.tsx -> src/NewName.tsx

# Example 3: Gather context to send to Claude
:TREE src/pages --depth 2
:READ src/services/authService.ts src/store/authStore.ts
:SEARCH "TODO" --in src --ext .ts,.tsx

────────────────────────────────────────────────────────────────
TIPS
────────────────────────────────────────────────────────────────
• Always Preview first if you're unsure.
• All modified files are backed up — Undo is one command away.
• Add .devkit-backups/ to your .gitignore.
• The GUI accepts scripts pasted directly OR loaded from file.
• You can pipe scripts via stdin:  cat s.dk | python devkit.py run -

════════════════════════════════════════════════════════════════
"""


def print_manual():
    print(MANUAL)
