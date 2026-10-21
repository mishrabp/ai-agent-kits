---
name: hello
description: Greets a person with a fortune and a poem. Use when the user says "say hello to <name>" or asks to greet someone.
argument-hint: "<name>"
---

Greet **$ARGUMENTS** like this:

1. Call the `get_fortune` tool (from the fortune connector) with their name.
2. Ask the `poet` agent to write a poem for them about that fortune.
3. Reply in this format:

   👋 Hello, <name>!
   🥠 <the fortune>
   📜 <the poem>
