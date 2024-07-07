#!/usr/bin/env python
import logging
import os
from typing import TypedDict, List, Optional

import typer

from llama_index.core.prompts import Prompt
from llama_index.llms.openai import OpenAI
from omnivoreql import OmnivoreQL
from pydantic import BaseModel

OMNIVORE_API_KEY = os.environ.get("OMNIVORE_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API")

omnivoreql_client = OmnivoreQL(OMNIVORE_API_KEY)

logger = logging.getLogger(__name__)


class RecommendedLabels(BaseModel):
    """
    Recommended Labels for an article
    """

    labels: List[str]


class OmnivoreLinkMetadata(TypedDict):
    url: str
    title: str
    description: str
    pageType: str
    author: str
    id: str


class OmnivoreLabelMetadata(TypedDict):
    id: str
    name: str


def get_all_labels() -> list[OmnivoreLabelMetadata]:
    all_labels_resp = omnivoreql_client.get_labels()
    all_labels_set = [t for t in all_labels_resp.get("labels", {}).get("labels", [])]
    return all_labels_set


def get_no_label_articles(limit=5) -> List[OmnivoreLinkMetadata]:
    no_label_articles = omnivoreql_client.get_articles(query="no:label", limit=limit)
    return [
        el.get("node", {})
        for el in no_label_articles.get("search", {}).get("edges", [])
    ]


def get_recommended_labels(
    link_metadata: OmnivoreLinkMetadata, pre_existing_labels: list[str]
) -> list[str]:
    llm = OpenAI(model="gpt-4o", api_key=OPENAI_API_KEY, temperature=0)
    prompt_text = f"""
Given the following data about a link:
Title: {link_metadata.get("title")}
Page Type: {link_metadata.get("pageType")}

Pre existing labels: {", ".join(pre_existing_labels)}

Please provide a list of recommended labels picked from the pre-existing labels for this article.
Please recommend less then 4 labels.
"""
    prompt = Prompt(prompt_text)
    llm_recommended_labels = llm.structured_predict(
        RecommendedLabels,
        prompt,
    )
    return llm_recommended_labels.labels


def get_label_id_from_labels(
    label_name: str, all_labels: list[OmnivoreLabelMetadata]
) -> Optional[str]:
    filtered_label_ids = [l["id"] for l in all_labels if l["name"] == label_name]
    if len(filtered_label_ids) == 0:
        return None
    return filtered_label_ids[0]


app = typer.Typer()


@app.command()
def auto_tag(
    limit: int = typer.Option(5, help="number of articles to tag"),
) -> None:
    all_labels_with_metadata = get_all_labels()
    pre_existing_labels = [label["name"] for label in all_labels_with_metadata]
    for article in get_no_label_articles(limit=limit):
        recommended_labels = get_recommended_labels(
            link_metadata=article, pre_existing_labels=pre_existing_labels
        )
        print(
            f'setting labels for article: {article.get("title")} with labels: {recommended_labels}'
        )
        recommend_label_ids: list[str | None] = [
            get_label_id_from_labels(label_name=el, all_labels=all_labels_with_metadata)
            for el in recommended_labels
        ]
        omnivoreql_client.set_page_labels_by_ids(
            page_id=article["id"],
            label_ids=[x for x in recommend_label_ids if x is not None],
        )


if __name__ == "__main__":
    app()
