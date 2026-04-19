# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "click>=8.2.1",
#     "open-lifeworlds-python-lib",
# ]
#
# [tool.uv.sources]
# open-lifeworlds-python-lib = { git = "https://github.com/open-lifeworlds/open-lifeworlds-python-lib.git" }
# ///

import json
import os
import sys
from functools import cache

import click
from dotenv import load_dotenv
from openlifeworlds.config.data_product_manifest_loader import (
    load_data_product_manifest,
)
from openlifeworlds.extract.data_extractor import extract_data
from openlifeworlds.extract.osmnx_graph_loader import load_osmnx_graph
from openlifeworlds.extract.partridge_graph_loader import load_transit_graph
from openlifeworlds.transform.data_point_generator import generate_points_hexagon
from openlifeworlds.transform.public_transport.networkx_graph_combiner import (
    combine_graphs,
)
from shapely import Point

from lib.transform.public_transport_commute.data_commute_hexagon_calculator import (
    calculate_commute_hexagons,
)
from lib.transform.public_transport_commute.data_commute_time_calculator import (
    calculate_commute_times,
)
from lib.transform.public_transport_commute.data_commute_time_metric_calculator import (
    calculate_commute_metrics,
)

file_path = os.path.realpath(__file__)
script_path = os.path.dirname(file_path)

load_dotenv()


@click.command()
@click.option("--clean", "-c", default=False, is_flag=True, help="Regenerate results.")
@click.option("--quiet", "-q", default=False, is_flag=True, help="Do not log outputs.")
@click.option("--upload", "-u", default=False, is_flag=True, help="Upload results.")
def main(clean, quiet, upload):
    data_path = os.path.join(script_path, "data")
    bronze_path = os.path.join(data_path, "01-bronze")
    silver_path = os.path.join(data_path, "02-silver")
    gold_path = os.path.join(data_path, "03-gold")

    data_product_manifest = load_data_product_manifest(config_path=script_path)

    query = "Berlin, Germany"

    year = 2024

    hexagon_resolutions = [7, 8, 9]
    hexagon_resolution_max = max(hexagon_resolutions)

    #
    # Extract
    #

    extract_data(
        data_product_manifest=data_product_manifest,
        results_path=bronze_path,
        clean=clean,
        quiet=quiet,
    )

    geojson_file_path = os.path.join(
        os.path.join(bronze_path, "berlin-lor-city", "berlin-lor-city.geojson")
    )
    geojson_feature = get_geojson_feature_by_name(
        os.path.join(bronze_path, "berlin-lor-city", "berlin-lor-city.geojson"),
        "Berlin",
    )

    walk_graph = load_osmnx_graph(
        results_path=bronze_path,
        query=query,
        network_type="walk",
        walk_speed_kph=5.0,
        simplified=True,
        clean=clean,
        quiet=quiet,
    )

    generate_points_hexagon(
        results_path=bronze_path,
        query=query,
        geojson_feature=geojson_feature,
        hexagon_resolution=hexagon_resolution_max,
        clean=clean,
        quiet=quiet,
    )

    for start_hour, end_hour in [(7, 9)]:
        transit_graph = load_transit_graph(
            source_path=bronze_path,
            results_path=bronze_path,
            query=query,
            geojson_feature=geojson_feature,
            year=year,
            start_hour=start_hour,
            end_hour=end_hour,
            clean=clean,
            quiet=quiet,
        )

        #
        # Transform
        #

        combined_graph = combine_graphs(
            results_path=silver_path,
            query=query,
            walk_graph=walk_graph,
            transit_graph=transit_graph,
            year=year,
            start_hour=start_hour,
            end_hour=end_hour,
            clean=clean,
            quiet=quiet,
        )

        BOSCH_ULLSTEINSTRASSE = Point(13.3851451, 52.4541182)
        BOSCH_BISMARKSTRASSE = Point(13.2969174, 52.5107521)

        calculate_commute_times(
            source_path=bronze_path,
            results_path=silver_path,
            query=query,
            graph=combined_graph,
            hexagon_resolution=hexagon_resolution_max,
            year=year,
            start_hour=start_hour,
            end_hour=end_hour,
            target_points=[
                ("ullsteinstrasse", BOSCH_ULLSTEINSTRASSE),
                ("bismarckstrasse", BOSCH_BISMARKSTRASSE),
            ],
            clean=clean,
            quiet=quiet,
        )

        calculate_commute_metrics(
            source_path=silver_path,
            results_path=silver_path,
            query=query,
            hexagon_resolution=hexagon_resolution_max,
            year=year,
            start_hour=start_hour,
            end_hour=end_hour,
            clean=clean,
            quiet=quiet,
        )

        for hexagon_resolution in hexagon_resolutions:
            calculate_commute_hexagons(
                source_path=silver_path,
                results_path=gold_path,
                query=query,
                geojson_file_path=geojson_file_path,
                hexagon_resolution=hexagon_resolution,
                hexagon_resolution_max=hexagon_resolution_max,
                year=year,
                start_hour=start_hour,
                end_hour=end_hour,
                clean=clean,
                quiet=quiet,
            )


def get_geojson_feature_by_name(file_path, name):
    return next(
        (
            feature
            for feature in read_geojson_file(file_path)["features"]
            if feature["properties"]["name"] == name
        ),
        None,
    )


@cache
def read_geojson_file(file_path):
    with open(file=file_path, mode="r", encoding="utf-8") as geojson_file:
        return json.load(geojson_file, strict=False)


if __name__ == "__main__":
    main(sys.argv[1:])
