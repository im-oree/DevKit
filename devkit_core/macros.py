# -*- coding: utf-8 -*-
"""
DevKit Macros — reusable text blocks copied to clipboard.
"""

AI_SYNTAX_REFERENCE = r"""
# DevKit Script Syntax (paste this into AI so it knows how to reply)

You reply with DevKit scripts. I paste them into DevKit → Preview → Run.
Every op is auto-backed-up; Undo is one click.

INLINE (one line):
  DELETE <path_or_glob>
  RENAME <src> -> <dst>
  MKDIR  <path>
  RUN    <shell command>
  INSTALL <packages>
  GITADD <path>
  GITCOMMIT "message"

BLOCK (multi-line, terminated with :END):
  :CREATE <path>            new file (fails if exists)
  <content>
  :END

  :WRITE <path>             create or overwrite
  <content>
  :END

  :APPEND <path>            add to end
  <content>
  :END

  :PREPEND <path>           add to start
  <content>
  :END

  :REPLACE <path>           literal find/replace
  FIND:
  <exact text>
  WITH:
  <replacement>
  :END

  :REGEX_REPLACE <path>
  FIND: pattern
  WITH: replacement
  :END

  :REPLACE_BLOCK <path>
  FROM: start marker line
  TO:   end marker line
  WITH:
  <new content>
  :END

  :INSERT_AFTER <path>
  FIND:
  <anchor>
  WITH:
  <content>
  :END

  :INSERT_BEFORE <path>
  FIND:
  <anchor>
  WITH:
  <content>
  :END

  :MULTI_REPLACE <path>
  FIND:
  <a>
  WITH:
  <A>
  ---
  FIND:
  <b>
  WITH:
  <B>
  :END

READ OPS:
  :TREE [path] [--depth N] [--include *.ts] [--exclude foo]
  :READ path1 path2 path3...
  :SEARCH "text" [--in path] [--ext .ts,.tsx]
  :LIST <glob>
  :INFO <path>

RULES:
- Paths relative to DevKit Project folder.
- Use :READ first when needing context.
- Prefer :REPLACE over :REGEX_REPLACE.
- Combine ops in one script.
- Comments start with #.
""".strip()


AI_COLLAB_PROMPT = r"""
I'm using a portable tool called DevKit. You send me compact scripts and
I paste them into DevKit's GUI to preview and apply changes to my project.
Every change is auto-backed up.

HOW WE WORK:
1) If you need to see files, send :READ / :TREE / :SEARCH first.
2) Send the actual edit as ONE DevKit script.
3) Break big features into multiple scripts if needed.
4) :REPLACE FIND text must match EXACTLY.
5) Prefer small focused scripts.

Project tree and syntax below. Confirm you've read them, then wait.

--- PROJECT TREE ---
{TREE}

--- DEVKIT SYNTAX ---
{SYNTAX}
""".strip()


QUICK_START = r"""
DEVKIT QUICK START
------------------

1. Set your project via "Choose folder" (top-right).
2. Get a script from AI (use Macros -> Copy AI Syntax to teach it).
3. Paste script into the Script panel.
4. Click Preview first — nothing is written yet.
5. Click Run — all edits auto-backed up. Undo is one click.

MACROS (top toolbar):
  - Copy Project Tree
  - Copy AI Prompt
  - Copy AI Syntax
  - Copy All-In-One

KEYBOARD:
  F5           = Run
  Ctrl+Enter   = Preview

TIPS:
  - Add .devkit-backups/ to .gitignore
  - Save useful scripts with "Save to file"
  - Use "Copy all" on Output to send results back to AI
""".strip()


def build_tree_text(cwd, depth=3):
    from .parser import Operation
    from .ops import op_tree, OpContext
    op = Operation(kind="TREE", target=".", args={"depth": depth})
    ctx = OpContext(cwd=cwd)
    r = op_tree(op, ctx)
    return r.output


def build_all_in_one(cwd, depth=3):
    tree = build_tree_text(cwd, depth=depth)
    return AI_COLLAB_PROMPT.replace("{TREE}", tree).replace("{SYNTAX}", AI_SYNTAX_REFERENCE)
