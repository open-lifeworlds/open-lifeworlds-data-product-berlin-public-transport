import os

import geopandas as gpd

# noinspection PyUnresolvedReferences
import h3pandas
from openlifeworlds.tracking_decorator import TrackingDecorator


@TrackingDecorator.track_time
def calculate_commute_hexagons(
    source_path,
    results_path,
    query,
    geojson_file_path,
    hexagon_resolution=7,
    hexagon_resolution_max=9,
    year=2024,
    start_hour=None,
    end_hour=None,
    clean=False,
    quiet=False,
):
    """
    Generates hexagonal grid
    :param source_path: source path
    :param results_path: results path
    :param query: query
    :param geojson_file_path: geojson file path
    :param hexagon_resolution: hexagon resolution, for edge lengths see https://h3geo.org/docs/core-library/restable#edge-lengths
    :param hexagon_resolution_max: max hexagon resolution
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

    metrics_geojson_path = os.path.join(
        source_path,
        f"{area_prefix}-public-transport-commute-{year}-{time_window_suffix}",
        f"{area_prefix}-points-{hexagon_resolution_max}-with-metrics.geojson",
    )
    hexagon_geojson_path = os.path.join(
        results_path,
        f"{area_prefix}-public-transport-commute-{year}-{time_window_suffix}",
        f"{area_prefix}-points-{hexagon_resolution}-with-hexagons.geojson",
    )

    if clean or not os.path.exists(hexagon_geojson_path):
        gp_dataframe_points = gpd.read_file(metrics_geojson_path)
        gp_dataframe_city = gpd.read_file(geojson_file_path)

        # Calculate hexagons
        gp_dataframe_exploded = gp_dataframe_city.explode(index_parts=True)
        gp_dataframe_h3 = gp_dataframe_exploded.h3.polyfill_resample(hexagon_resolution)

        # Blend in metrics
        gp_dataframe_points_in_polygon = gpd.sjoin(
            gp_dataframe_points, gp_dataframe_h3, how="inner", predicate="within"
        )
        gp_dataframe_average_metric = gp_dataframe_points_in_polygon.groupby(
            "h3_polyfill"
        )["commute_time_surplus_after_relocation"].mean()
        gp_dataframe_final = gp_dataframe_h3.merge(
            gp_dataframe_average_metric, left_index=True, right_index=True
        )

        write_geojson_file(
            hexagon_geojson_path,
            gp_dataframe_final,
            clean,
            quiet,
        )
    else:
        print(f"✓ Already exists {os.path.basename(hexagon_geojson_path)}")


#
# Helpers
#


def write_geojson_file(file_path, gp_dataframe, clean, quiet):
    if not os.path.exists(file_path) or clean:
        # Make results path
        os.makedirs(os.path.join(os.path.dirname(file_path)), exist_ok=True)

        gp_dataframe.to_file(file_path)

        not quiet and print(f"✓ Generate hexagons into {os.path.basename(file_path)}")
    else:
        print(f"✓ Already exists {os.path.basename(file_path)}")
