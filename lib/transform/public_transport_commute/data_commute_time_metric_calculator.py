import json
import os
from functools import lru_cache, cache

from openlifeworlds.tracking_decorator import TrackingDecorator
from tqdm import tqdm


@TrackingDecorator.track_time
def calculate_commute_metrics(
    source_path,
    results_path,
    query,
    hexagon_resolution=7,
    year=2024,
    start_hour=None,
    end_hour=None,
    clean=False,
    quiet=False,
):
    """
    Calculates metrics for each feature
    :param source_path: source path
    :param results_path: results path
    :param query: query
    :param hexagon_resolution: hexagon resolution
    :param year: year
    :param start_hour: start hour
    :param end_hour: end hour
    :param clean: clean
    :param quiet: quiet
    """

    # Define area prefix
    area_prefix = (
        "-".join(list(reversed(query.split(",")))[1:]).lower().replace(" ", "")
    )
    # Define time window suffix
    time_window_suffix = (
        f"{str(start_hour).zfill(2)}-{str(end_hour).zfill(2)}"
        if start_hour is not None and end_hour is not None
        else "avg"
    )

    # Define file paths
    points_geojson_path = os.path.join(
        source_path,
        f"{area_prefix}-public-transport-commute-{year}-{time_window_suffix}",
        f"{area_prefix}-points-{hexagon_resolution}-with-commute-time.geojson",
    )
    metrics_geojson_path = os.path.join(
        results_path,
        f"{area_prefix}-public-transport-commute-{year}-{time_window_suffix}",
        f"{area_prefix}-points-{hexagon_resolution}-with-metrics.geojson",
    )

    if clean or not os.path.exists(metrics_geojson_path):
        geojson = load_geojson_file(points_geojson_path)

        for feature in tqdm(
            geojson["features"],
            desc="Calculate metrics",
            total=len(geojson["features"]),
            unit="feature",
        ):
            commute_time_ullsteinstrasse = int(
                feature["properties"]["commute_time_ullsteinstrasse"]
            )
            commute_time_bismarckstrasse = int(
                feature["properties"]["commute_time_bismarckstrasse"]
            )

            feature["properties"] = {
                "commute_time_ullsteinstrasse": commute_time_ullsteinstrasse,
                "commute_time_bismarckstrasse": commute_time_bismarckstrasse,
                "commute_time_surplus_after_relocation": commute_time_bismarckstrasse
                - commute_time_ullsteinstrasse,
            }

        write_geojson_file(
            metrics_geojson_path,
            geojson,
            clean,
            quiet,
        )
    else:
        print(f"✓ Already exists {os.path.basename(metrics_geojson_path)}")


#
# Helpers
#


@cache
def load_geojson_file(file_path):
    with open(file=file_path, mode="r", encoding="utf-8") as geojson_file:
        return json.load(geojson_file, strict=False)


def write_geojson_file(file_path, geojson_content, clean, quiet):
    if not os.path.exists(file_path) or clean:
        # Make results path
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as geojson_file:
            json.dump(geojson_content, geojson_file, ensure_ascii=False)

            not quiet and print(
                f"✓ Generate metrics into {os.path.basename(file_path)}"
            )
    else:
        print(f"✓ Already exists {os.path.basename(file_path)}")
