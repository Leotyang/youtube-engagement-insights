"""Trait definitions and the universal 0-4 scale every trait is scored on.

PLACEHOLDER traits until the team's list lands (see TASK.md). Replace the TRAITS dict,
bump TAGGING_PROMPT_VERSION in config.py, and re-run tag_videos.py.
"""

# trait name -> one-line definition. A trait is something a video can *be* to a degree.
TRAITS = {
    "tutorial": "Step-by-step instruction intended to teach the viewer how to do something.",
    "humor": "Content played for laughs: jokes, comedic timing, absurdity, bits.",
    "challenge": "A stated goal, dare, or competition the creator attempts to complete.",
    "product_review": "Evaluation of a specific product, service, or piece of media.",
    "storytelling": "A narrative arc with setup, development, and payoff.",
    "personal_vlog": "Day-in-the-life or behind-the-scenes footage of the creator's own life.",
    "high_production": "Cinematic camera work, sets, effects, or editing well beyond a talking head.",
    "sponsored_content": "Paid promotion or brand integration woven into the video.",
}

SCALE = """Score every trait on this universal 0-4 scale. Read "X" as the trait being scored.
0 - Absent. Nothing in the video is X. A viewer would not associate the video with X.
1 - Incidental. The creator did not intend X, but some part of the video has X value implicitly.
2 - Explicit segment. The video as a whole is not X, but at least one part is deliberately X and signaled as such.
3 - Featured. X is one of the video's stated purposes; a substantial dedicated portion is X, but the video also does other things.
4 - Defining. The video is X and nothing else. Remove X and there is no video left.
Tie-breakers: intent beats accident (explicit framing -> at least 2); coverage moves you up (segment 2, major portion 3, whole 4); when torn between two levels, pick the lower."""

## ask Austin tomorrow