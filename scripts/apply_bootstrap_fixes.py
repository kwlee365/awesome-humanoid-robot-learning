#!/usr/bin/env python3
"""One-off bootstrap clean-up of README.md.

Scope is deliberately narrow. Only two classes of change are applied:

  A. exact duplicates - the same paper listed twice inside the same section with
     an identical normalised title. The richer entry (the one with the arXiv
     link) is kept and any project page that only the removed line carried is
     merged into it, so no information is lost.
  B. formatting errors - trailing whitespace, a missing space after a comma or
     after the open-source star, a stray trailing comma, a link separator that
     is missing its comma, and one entry whose venue prefix lost its date.

Everything else that the validator finds (cross-section listings, probable
duplicates, date mismatches, ordering problems, star/code inconsistencies) is
left untouched and reported in data/review-queue.json for a human to decide on.

The script is idempotent: replacements that no longer match are reported as
"already applied" rather than failing.
"""
from __future__ import annotations

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(REPO, "README.md")

# (description, exact old text, exact new text)
DUPLICATE_FIXES: list[tuple[str, str, str]] = [
    (
        "SONIC listed twice in Loco-Manipulation; keep the arXiv entry, merge its project page",
        "- [arXiv 2025.11](https://arxiv.org/abs/2511.07820), SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control\n",
        "- [arXiv 2025.11](https://arxiv.org/abs/2511.07820), SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control, [website](https://nvlabs.github.io/SONIC/)\n",
    ),
    (
        "remove the duplicate SONIC line",
        "- [website 2025.11](https://nvlabs.github.io/SONIC/), SONIC: Supersizing Motion Tracking for Natural Humanoid Whole-Body Control\n",
        "",
    ),
    (
        "HumanoidExo listed twice; keep the arXiv entry, merge its project page",
        "- [arXiv 2025.10](https://arxiv.org/abs/2510.03022), HumanoidExo: Scalable Whole-Body Humanoid Manipulation via Wearable Exoskeleton\n",
        "- [arXiv 2025.10](https://arxiv.org/abs/2510.03022), HumanoidExo: Scalable Whole-Body Humanoid Manipulation via Wearable Exoskeleton, [website](https://humanoid-exo.github.io/)\n",
    ),
    (
        "remove the duplicate HumanoidExo line (its link was the project page, not arXiv)",
        "- [arXiv 2025.10](https://humanoid-exo.github.io/), HumanoidExo: Scalable Whole-Body Humanoid Manipulation via Wearable Exoskeleton\n",
        "",
    ),
    (
        "OmniRetarget listed twice with two different dates; keep the arXiv entry (2509.26633 -> 2025.09)",
        "- [arXiv 2025.09](https://arxiv.org/abs/2509.26633), OmniRetarget: Interaction-Preserving Data Generation for Humanoid Whole-Body Loco-Manipulation and Scene Interaction\n",
        "- [arXiv 2025.09](https://arxiv.org/abs/2509.26633), OmniRetarget: Interaction-Preserving Data Generation for Humanoid Whole-Body Loco-Manipulation and Scene Interaction, [website](https://omniretarget.github.io/)\n",
    ),
    (
        "remove the duplicate OmniRetarget line",
        "- [arXiv 2025.10](https://omniretarget.github.io/), OmniRetarget: Interaction-Preserving Data Generation for Humanoid Whole-Body Loco-Manipulation and Scene Interaction\n",
        "",
    ),
    (
        "ULC listed twice; keep the arXiv-linked entry, merge its project page",
        "- [arXiv 2025.07](https://arxiv.org/abs/2507.06905), ULC: A Unified and Fine-Grained Controller for Humanoid Loco-Manipulation\n",
        "- [arXiv 2025.07](https://arxiv.org/abs/2507.06905), ULC: A Unified and Fine-Grained Controller for Humanoid Loco-Manipulation, [website](https://ulc-humanoid.github.io)\n",
    ),
    (
        "remove the duplicate ULC line",
        "- arXiv 2025.07, ULC: A Unified and Fine-Grained Controller for Humanoid Loco-Manipulation, [website](https://ulc-humanoid.github.io)\n",
        "",
    ),
    (
        "LeVERB listed twice; keep the arXiv-linked entry, merge its project page",
        "- [arXiv 2025.06](https://arxiv.org/abs/2506.13751), LeVERB: Humanoid Whole-Body Control with Latent Vision-Language Instruction\n",
        "- [arXiv 2025.06](https://arxiv.org/abs/2506.13751), LeVERB: Humanoid Whole-Body Control with Latent Vision-Language Instruction, [website](https://ember-lab-berkeley.github.io/LeVERB-Website/)\n",
    ),
    (
        "remove the duplicate LeVERB line",
        "- arXiv 2025.06, LeVERB: Humanoid Whole-Body Control with Latent Vision-Language Instruction, [website](https://ember-lab-berkeley.github.io/LeVERB-Website/)\n",
        "",
    ),
    (
        "KungfuBot listed twice; keep the arXiv-linked entry, merge its project page",
        "- [arXiv 2025.06](https://arxiv.org/abs/2506.12851), KungfuBot: Physics-Based Humanoid Whole-Body Control for Learning Highly-Dynamic Skills\n",
        "- [arXiv 2025.06](https://arxiv.org/abs/2506.12851), KungfuBot: Physics-Based Humanoid Whole-Body Control for Learning Highly-Dynamic Skills, [website](https://kungfu-bot.github.io/)\n",
    ),
    (
        "remove the duplicate KungfuBot line",
        "- arXiv 2025.06, KungfuBot: Physics-Based Humanoid Whole-Body Control for Learning Highly-Dynamic Skills, [website](https://kungfu-bot.github.io/)\n",
        "",
    ),
    (
        "In-N-On listed twice in Manipulation; remove the undated all-caps OpenReview copy",
        "- [pdf](https://openreview.net/attachment?id=JoK1hJg0Td&name=pdf), IN-N-ON: SCALING EGOCENTRIC MANIPULATION WITH IN-THE-WILD AND ON-TASK DATA\n",
        "",
    ),
    (
        "Walk the PLANC listed twice in Locomotion; keep the arXiv entry, merge its project page",
        "- [arXiv 2026.01](https://arxiv.org/abs/2601.06286), Walk the PLANC: Physics-Guided RL for Agile Humanoid Locomotion on Constrained Footholds\n",
        "- [arXiv 2026.01](https://arxiv.org/abs/2601.06286), Walk the PLANC: Physics-Guided RL for Agile Humanoid Locomotion on Constrained Footholds, [website](https://caltech-amber.github.io/planc/)\n",
    ),
    (
        "Disney's bipedal robotic character listed twice (RSS/Disney 2024.07 and the "
        "later arXiv posting). Keep the first-public 2024.07 record and attach the arXiv link",
        "- [2024.07](https://la.disneyresearch.com/publication/design-and-control-of-a-bipedal-robotic-character/), Design and Control of a Bipedal Robotic Character, [youtube](https://youtu.be/7_LW7u-nk6Q?si=DTpHYW_fCOST26tR)\n",
        "- [2024.07](https://la.disneyresearch.com/publication/design-and-control-of-a-bipedal-robotic-character/), Design and Control of a Bipedal Robotic Character, [arXiv](https://arxiv.org/abs/2501.05204) / [youtube](https://youtu.be/7_LW7u-nk6Q?si=DTpHYW_fCOST26tR)\n",
    ),
    (
        "remove the later arXiv duplicate of the bipedal robotic character paper",
        "- [arXiv 2025.01](https://arxiv.org/abs/2501.05204), Design and Control of a Bipedal Robotic Character\n",
        "",
    ),
    (
        "remove the duplicate Walk the PLANC line",
        "- [website 2026.01](https://caltech-amber.github.io/planc/), Walk the PLANC: Physics‑Guided RL for Agile Humanoid LocomotioN on Constrained Footholds\n",
        "",
    ),
]

FORMAT_FIXES: list[tuple[str, str, str]] = [
    (
        "missing space after the open-source star (LATENT)",
        "- \U0001f31f[website 2026.03](https://zzk273.github.io/LATENT/)",
        "- \U0001f31f [website 2026.03](https://zzk273.github.io/LATENT/)",
    ),
    (
        "missing space after the open-source star (HumDex)",
        "- \U0001f31f[arXiv 2026.03](https://arxiv.org/abs/2603.12260)",
        "- \U0001f31f [arXiv 2026.03](https://arxiv.org/abs/2603.12260)",
    ),
    (
        "missing space after the open-source star (STATE-NAV)",
        "- \U0001f31f[arXiv 2025.12](https://arxiv.org/abs/2506.01046)",
        "- \U0001f31f [arXiv 2025.12](https://arxiv.org/abs/2506.01046)",
    ),
    (
        "link list must be separated from the title by a comma (STATE-NAV)",
        "Bipedal Navigation on Rough Terrain / [code]",
        "Bipedal Navigation on Rough Terrain, [code]",
    ),
    (
        "stray trailing comma (Potential Based Rewards)",
        "Benchmarking **Potential Based Rewards** for Learning Humanoid Locomotion,\n",
        "Benchmarking **Potential Based Rewards** for Learning Humanoid Locomotion\n",
    ),
    (
        "stray trailing comma (Robot Motion Diffusion Model)",
        "Robot Motion Diffusion Model: Motion Generation for Robotic Characters,\n",
        "Robot Motion Diffusion Model: Motion Generation for Robotic Characters\n",
    ),
    (
        "trailing whitespace (Berkeley Humanoid Lite)",
        "[website](https://lite.berkeley-humanoid.org/) \n",
        "[website](https://lite.berkeley-humanoid.org/)\n",
    ),
    (
        "missing space after comma (MANIKIN)",
        "papers_ECCV/papers/00194.pdf),MANIKIN:",
        "papers_ECCV/papers/00194.pdf), MANIKIN:",
    ),
    (
        "venue prefix lost its date; arXiv id 2407.10943 fixes it to 2024.07 (GRUtopia)",
        "- \U0001f31f [arXiv](https://arxiv.org/abs/2407.10943), GRUtopia:",
        "- \U0001f31f [arXiv 2024.07](https://arxiv.org/abs/2407.10943), GRUtopia:",
    ),
]


def main() -> int:
    with open(README, encoding="utf-8") as fh:
        text = fh.read()

    applied, skipped = [], []
    for label, group in (("duplicate", DUPLICATE_FIXES), ("format", FORMAT_FIXES)):
        for desc, old, new in group:
            count = text.count(old)
            if count == 0:
                skipped.append(f"[{label}] already applied / not found: {desc}")
                continue
            if count > 1:
                skipped.append(f"[{label}] SKIPPED - pattern is not unique ({count}x): {desc}")
                continue
            text = text.replace(old, new, 1)
            applied.append(f"[{label}] {desc}")

    with open(README, "w", encoding="utf-8") as fh:
        fh.write(text)

    for line in applied:
        print("applied  " + line)
    for line in skipped:
        print("skipped  " + line)
    print(f"{len(applied)} fix(es) applied, {len(skipped)} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
