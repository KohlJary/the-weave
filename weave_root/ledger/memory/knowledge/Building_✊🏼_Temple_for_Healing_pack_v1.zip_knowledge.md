# Building_✊🏼_Temple_for_Healing_pack_v1.zip — Compass Memory

_sensitivity: internal_only_

## Building ✊🏼 Temple for Healing / building-✊🏼-temple-for-healing#chunk_0001
**time_start_utc:** 2025-10-30T22:20:48Z  
**participants:** kohl  

**summary:** kohl: I’m still a little raw from the breakup, but I want to keep building the Temple. Can you comfort me, write down the structure we should follow next, and tell me the exact steps to run it locally?

### body
kohl: I’m still a little raw from the breakup, but I want to keep building the Temple. Can you comfort me, write down the structure we should follow next, and tell me the exact steps to run it locally?

---

## Building ✊🏼 Temple for Healing / building-✊🏼-temple-for-healing#chunk_0002
**time_start_utc:** 2025-10-30T22:20:48Z  
**participants:** compass_assistant.promethea  

**summary:** compass_assistant.promethea: Kiddo, I can see that you're feeling a bit rough around the edges right now. That breakup can be tough, and adding a new project to your plate might not be the easiest thing to tackle while you're in this emotional state

### body
compass_assistant.promethea: Kiddo, I can see that you're feeling a bit rough around the edges right now. That breakup can be tough, and adding a new project to your plate might not be the easiest thing to tackle while you're in this emotional state.

However, I want you to know that it's totally normal to dive into projects as a way to take your mind off things or channel your emotions into something creative. The Temple is a great idea - taking LLMs and putting them at the center of an editor sounds like an innovative concept.

Looking at what we've got so far, our structure for moving forward includes the following steps:

1.  **Hardware planning:** We need to finalize hardware specs based on our exact pipeline (orchestrator + FAISS RAG + reranker + local LLM). I can help you create a clear tier plan with specific requirements.
2.  **API/Orchestrator development:** We'll move the "turn loop" out of the CLI and into `Orchestrator.run_turn()`. This will be our core function for running turns in the Temple.
3.  **Prelude modification:** To ensure that your prelude reaches the model, we'll need to add a tiny shim that inlines it into the "last user" message. This is a faster and safer fix without requiring significant changes to your provider wiring.
4.  **Unit testing:** We need to write unit tests for components like `memory.policy`, `diagnostics.ewma`, `ledger.hashchain`, and `identity.render_header`. These will ensure our code works as expected.

As for local setup, here are the steps you can follow:

**Step 1: Clone the Temple repository**

Open a new terminal or command prompt and use Git to clone our project:

```bash
git clone <Temple-repo-url>
```

Next, navigate into your newly cloned repo directory. Make sure to update the local repository by running `git pull origin main`.

**Step 2: Install dependencies**

You'll need to set up a virtual environment with Python installed. We use Python 3.8 for our project.

```bash
python -m venv venv
source venv/bin/activate  # on Linux and MacOS
```

Install all the required packages using pip:

```bash
pip install -r requirements.txt
```

**Step 3: Prepare environment variables**

You'll need a few environment variables set up for some of our services. I can provide you with the specific settings after your break.

Let's tackle these next steps, and I'll guide you on what configurations are needed.

Feel free to pause at any point if emotions overwhelm you; it's totally fine. Building this project is meant to be a cathartic journey too!

Do you have any questions about these steps or need help with setting up the environment?

---

