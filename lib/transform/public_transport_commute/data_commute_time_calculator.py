import json
import os
from functools import cache

import networkx as nx
import osmnx as ox
from openlifeworlds.tracking_decorator import TrackingDecorator
from shapely import Point
from tqdm import tqdm


@TrackingDecorator.track_time
def calculate_commute_times(
    source_path,
    results_path,
    query,
    graph,
    hexagon_resolution=7,
    year=2024,
    end_hour=None,
    start_hour=None,
    checkpoint_interval=100,
    target_points=None,
    debug=False,
    clean=False,
    quiet=False,
):
    if target_points is None:
        target_points = []

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

    # Define paths
    points_geojson_path = os.path.join(
        source_path,
        f"{area_prefix}-points",
        f"{area_prefix}-points-{hexagon_resolution}.geojson",
    )
    reachable_area_geojson_path = os.path.join(
        results_path,
        f"{area_prefix}-public-transport-commute-{year}-{time_window_suffix}",
        f"{area_prefix}-points-{hexagon_resolution}-with-commute-time.geojson",
    )
    checkpoint_path = reachable_area_geojson_path.replace(
        ".geojson", "-checkpoint.geojson"
    )

    if not clean and os.path.exists(reachable_area_geojson_path):
        print(f"✓ Already exists {os.path.basename(reachable_area_geojson_path)}")
        return

    if not clean and os.path.exists(checkpoint_path):
        print(f"Resuming from checkpoint: {os.path.basename(checkpoint_path)}")
        geojson = load_geojson_file(checkpoint_path)
    else:
        geojson = load_geojson_file(points_geojson_path)

    # Convert node IDs to integer
    graph = nx.convert_node_labels_to_integers(graph, label_attribute="original_id")

    # Calculate distances to target points
    reverse_graph = graph.reverse()
    target_point_durations = {}
    for name, reference_point in target_points:
        target_node = ox.distance.nearest_nodes(
            graph, reference_point.x, reference_point.y
        )

        # Calculate travel times FROM all nodes TO this target node
        durations = nx.single_source_dijkstra_path_length(
            reverse_graph, source=target_node, weight="weight"
        )
        target_point_durations[name] = durations

    processed_count = 0
    for feature in tqdm(
        geojson["features"],
        desc="Enhance features with commute time",
        total=len(geojson["features"]),
        unit="feature",
    ):
        # Skip if already calculated (resumable)
        if all(
            [
                f"commute_time_{point[0]}" in feature["properties"]
                for point in target_points
            ]
        ):
            continue

        reference_point = feature["geometry"]["coordinates"]
        enhance_feature(
            graph,
            feature,
            reference_point=Point(reference_point[0], reference_point[1]),
            target_point_durations=target_point_durations,
        )

        processed_count += 1
        if processed_count % checkpoint_interval == 0:
            write_geojson_file(checkpoint_path, geojson, clean=True, quiet=True)

    write_geojson_file(
        reachable_area_geojson_path,
        geojson,
        clean,
        quiet,
    )

    # Clean up checkpoint
    if os.path.exists(checkpoint_path):
        os.remove(checkpoint_path)


def enhance_feature(
    graph,
    feature,
    reference_point: Point,
    target_point_durations: {str, Point},
):
    start_node_id = ox.distance.nearest_nodes(
        graph, reference_point.x, reference_point.y
    )

    for name, durations in target_point_durations.items():
        # Look up duration
        duration = durations[start_node_id]
        feature["properties"][f"commute_time_{name}"] = duration / 60

    return feature


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

            not quiet and print(f"✓ Generate points into {os.path.basename(file_path)}")
    else:
        print(f"✓ Already exists {os.path.basename(file_path)}")
