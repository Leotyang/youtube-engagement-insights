"""LLM trait tagging: one Claude call per video against config.TRAIT_TAXONOMY.

Output: data/interim/videos_tagged.csv = videos.csv columns + trait_* columns
        + tag_model + tag_prompt_version, so re-tags are traceable.

Usage:  python -m src.tagging
Colab:  from src import tagging; df_tagged = tagging.load_or_tag(df_videos)
"""

import json
import os
import time

import anthropic
import pandas as pd

from src import config

TAGGING_PROMPT = """You are tagging a YouTube video against a fixed content-trait taxonomy.

Traits:
{taxonomy}

Video metadata:
Title: {title}
Description: {description}
Tags: {tags}

Return ONLY a JSON object with one key per trait above, each a short label/phrase. No other text."""


def get_client():
    if not config.ANTHROPIC_API_KEY:
        return None
    return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


def tag_video(client, video_row):
    prompt = TAGGING_PROMPT.format(
        taxonomy="\n".join(f"- {trait}: {definition}" for trait, definition in config.TRAIT_TAXONOMY.items()),
        title=video_row["title"],
        description=str(video_row["description"] or "")[:500],
        tags=video_row["tags"],
    )
    message = client.messages.create(
        model=config.TAGGING_MODEL,
        max_tokens=512,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in message.content if block.type == "text")
    # Strip ```json fences if the model adds them despite the instruction.
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


def tag_videos(client, df_videos):
    tags = []
    for _, row in df_videos.iterrows():
        try:
            tags.append(tag_video(client, row))
        except Exception as error:
            print(f"Failed to tag {row['video_id']}: {error}")
            tags.append({trait: None for trait in config.TRAIT_TAXONOMY})
        time.sleep(0.2)
    df_tags = pd.DataFrame(tags).add_prefix("trait_")
    df_tags["tag_model"] = config.TAGGING_MODEL
    df_tags["tag_prompt_version"] = config.TAGGING_PROMPT_VERSION
    return pd.concat([df_videos.reset_index(drop=True), df_tags], axis=1)


def load_or_tag(df_videos):
    """Tag only videos not already in the tagged file; otherwise load what exists."""
    client = get_client()

    df_existing = pd.read_csv(config.TAGGED_VIDEOS_PATH) if os.path.exists(config.TAGGED_VIDEOS_PATH) else pd.DataFrame()

    if client and not df_videos.empty:
        already_tagged = set(df_existing["video_id"]) if not df_existing.empty else set()
        df_new = df_videos[~df_videos["video_id"].isin(already_tagged)]
        print(f"Tagging {len(df_new)} new videos ({len(already_tagged)} already tagged)")
        df_tagged = pd.concat([df_existing, tag_videos(client, df_new)]) if not df_new.empty else df_existing
        df_tagged.to_csv(config.TAGGED_VIDEOS_PATH, index=False)
        print(f"Saved {len(df_tagged)} tagged videos to {config.TAGGED_VIDEOS_PATH}")
        return df_tagged

    if not df_existing.empty:
        print(f"Loaded {len(df_existing)} previously tagged videos from {config.TAGGED_VIDEOS_PATH}")
        return df_existing

    print("Set ANTHROPIC_API_KEY (.env or Colab secret) and ingest videos first, then re-run.")
    return df_videos.copy()


if __name__ == "__main__":
    from src import ingest

    load_or_tag(ingest.load_or_ingest())
