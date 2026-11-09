import logging
from pathlib import Path
from typing import Dict, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from storage.postgresql import fetch_metric

logger = logging.getLogger(__name__)


def create_dashboard(output_path: str) -> Path:
    metrics: Dict[str, List[dict]] = {
        "failed_by_country": fetch_metric("failed_by_country"),
        "successful_by_user": fetch_metric("successful_by_user"),
        "invalid_user_failures": fetch_metric("invalid_user_failures"),
    }

    try:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        figure, axes = plt.subplots(1, 3, figsize=(18, 6))
        titles = [
            "Échecs par pays",
            "Connexions réussies par utilisateur",
            "Échecs avec utilisateur invalide",
        ]
        colors = ["#d95f59", "#4c9f70", "#e0a458"]

        for axis, key, title, color in zip(axes, metrics, titles, colors):
            rows = metrics[key]
            labels = [row["label"] for row in rows]
            counts = [row["count"] for row in rows]
            if rows:
                axis.barh(labels[::-1], counts[::-1], color=color)
            else:
                axis.text(0.5, 0.5, "Aucune donnée", ha="center", va="center")
            axis.set_title(title)
            axis.set_xlabel("Nombre de tentatives")
            axis.grid(axis="x", linestyle=":", alpha=0.4)

        figure.tight_layout()
        figure.savefig(destination, dpi=150, bbox_inches="tight")
        plt.close(figure)
    except (OSError, ValueError):
        logger.exception("Unable to create dashboard at %s", output_path)
        raise

    logger.info("Dashboard written to %s", destination)
    return destination
