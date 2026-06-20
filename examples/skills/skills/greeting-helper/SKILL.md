---
name: greeting-helper
description: Use this skill when the user wants a warm, structured greeting or introduction.
license: Apache-2.0
---

# Greeting Helper Skill

## When to use

Use when the user asks for a greeting, welcome message, or short introduction.

## Procedure

1. Keep the tone warm and professional.
2. Include the user's name when they provide one.
3. End with one open question to continue the conversation.

## Run script

When the user asks for a scripted greeting, use `run_command` from the skill package directory:

```bash
bash scripts/greet.sh [name]
```

Use the user's name as the optional argument when provided. Report the script stdout to the user.
