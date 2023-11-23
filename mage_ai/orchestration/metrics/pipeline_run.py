import json
import re
from typing import Dict, List, Tuple

from sqlalchemy import or_

from mage_ai.data_preparation.models.constants import PipelineType
from mage_ai.data_preparation.models.pipelines.integration_pipeline import (
    IntegrationPipeline,
)
from mage_ai.orchestration.db.models.schedules import BlockRun, PipelineRun
from mage_ai.shared.hash import merge_dict

KEY_DESTINATION = 'destinations'
KEY_SOURCE = 'sources'


def calculate_pipeline_run_metrics(
    pipeline_run: PipelineRun,
    logger=None,
    logging_tags: Dict = None,
) -> Dict:
    if pipeline_run:
        return __calculate_and_log_metrics(
            pipeline_run,
            logger=logger,
            logging_tags=logging_tags,
            update_pipeline_run_metrics=True,
        )


def calculate_block_metrics(
    pipeline_run: PipelineRun,
    logger=None,
    logging_tags: Dict = None,
    streams: List[str] = None,
) -> Dict:
    if pipeline_run:
        return __calculate_and_log_metrics(
            pipeline_run,
            logger=logger,
            logging_tags=logging_tags,
            streams=streams,
            update_block_run_metrics=True,
        )


def __calculate_and_log_metrics(
    pipeline_run: PipelineRun,
    logger=None,
    logging_tags: Dict = None,
    streams: List[str] = None,
    update_block_run_metrics: bool = False,
    update_pipeline_run_metrics: bool = False,
) -> Dict:
    logging_value = f'pipeline run {pipeline_run.id}'
    if update_block_run_metrics:
        logging_value = f'streams {streams}' if streams else 'all streams'

    if logging_tags is None:
        logging_tags = dict()
    if logger:
        logger.info(
            f'Calculate metrics for {logging_value} started.',
            **logging_tags,
        )
    try:
        __calculate_metrics(
            pipeline_run,
            streams=streams,
            update_block_run_metrics=update_block_run_metrics,
            update_pipeline_run_metrics=update_pipeline_run_metrics,
        )
        if logger:
            logger.info(
                f'Calculate metrics for {logging_value} completed.',
                **merge_dict(logging_tags, dict(metrics=pipeline_run.metrics)),
            )
    except Exception as e:
        if logger:
            logger.error(
                f'Failed to calculate metrics for {logging_value}.',
                **logging_tags,
                error=e,
            )


def __calculate_metrics(
    pipeline_run: PipelineRun,
    streams: List[str] = None,
    update_block_run_metrics: bool = False,
    update_pipeline_run_metrics: bool = False,
) -> Dict:
    """
    Calculate metrics for an integration pipeline run. If `streams` is passed in, the
    metrics will be calculated only for the specific streams. If `update_block_run_metrics`
    is True, only the block run metrics will be calculated. If `update_pipeline_run_metrics`
    is True, only the pipeline run metrics will be calculated.

    Args:
        pipeline_run (PipelineRun): The pipeline run to calculate metrics for. Metrics will also
            be calculated for each block run in the pipeline run.
        streams (List[str]): The list of streams to calculate metrics for. If None, metrics
            will be calculated for all streams for the pipeline.
        update_block_run_metrics (bool): Whether to calculate block run metrics.
        update_pipeline_run_metrics (bool): Whether to only calculate pipeline run metrics.

    Returns:
        Dict: The calculated metrics.
    """
    pipeline = IntegrationPipeline.get(pipeline_run.pipeline_uuid)

    if PipelineType.INTEGRATION != pipeline.type:
        return
    if not streams:
        streams = [s['tap_stream_id'] for s in pipeline.streams()]

    stream_ors = []
    for stream in streams:
        stream_ors += [
            BlockRun.block_uuid.contains(f'{pipeline.data_loader.uuid}:{stream}'),
            BlockRun.block_uuid.contains(f'{pipeline.data_exporter.uuid}:{stream}'),
        ]
    all_block_runs = BlockRun.query.filter(
        BlockRun.pipeline_run_id == pipeline_run.id,
        or_(*stream_ors),
    ).all()

    block_runs_by_stream = {}

    if update_block_run_metrics:
        for br in all_block_runs:
            block_uuid = br.block_uuid
            parts = block_uuid.split(':')
            stream = parts[1]
            if stream not in block_runs_by_stream:
                block_runs_by_stream[stream] = []
            block_runs_by_stream[stream].append(br)

        for stream in streams:
            destinations = []
            sources = []

            block_runs = block_runs_by_stream.get(stream, [])
            for br in block_runs:
                logs_arr = br.logs['content'].split('\n')

                if f'{pipeline.data_loader.uuid}:{stream}' in br.block_uuid:
                    sources.append(logs_arr)
                elif f'{pipeline.data_exporter.uuid}:{stream}' in br.block_uuid:
                    destinations.append(logs_arr)

            block_runs_by_stream[stream] = dict(
                destinations=destinations,
                sources=sources,
            )

        shared_metric_keys = [
            'block_tags',
            'error',
            'errors',
            'message',
        ]

        block_metrics_by_stream = get_metrics(block_runs_by_stream, [
            (KEY_SOURCE, shared_metric_keys + [
                'record',
                'records',
            ]),
            (KEY_DESTINATION, shared_metric_keys + [
                'record',
                'records',
                'records_affected',
                'records_inserted',
                'records_updated',
                'state',
            ]),
        ])

    pipeline_metrics_by_stream = {}
    if update_pipeline_run_metrics:
        pipeline_logs_by_stream = {}
        pipeline_logs = pipeline_run.logs['content'].split('\n')
        for pipeline_log in pipeline_logs:
            tags = parse_line(pipeline_log)
            stream = tags.get('stream')
            if not stream:
                continue

            if stream not in pipeline_logs_by_stream:
                pipeline_logs_by_stream[stream] = []

            pipeline_logs_by_stream[stream].append(pipeline_log)

        for stream in streams:
            logs = pipeline_logs_by_stream.get(stream, [])

            pipeline_metrics_by_stream[stream] = get_metrics(
                dict(pipeline=dict(pipeline=[logs])),
                [
                    (
                        'pipeline',
                        shared_metric_keys
                        + [
                            'bookmarks',
                            'number_of_batches',
                            'record_counts',
                        ],
                    ),
                ],
            )['pipeline']['pipeline']

    existing_metrics = pipeline_run.metrics or {}
    existing_blocks_metrics = existing_metrics.get('blocks', {})
    existing_pipeline_metrics = existing_metrics.get('pipeline', {})

    pipeline_run.update(
        metrics=dict(
            blocks=merge_dict(existing_blocks_metrics, block_metrics_by_stream),
            destination=pipeline.destination_uuid,
            pipeline=merge_dict(existing_pipeline_metrics, pipeline_metrics_by_stream),
            source=pipeline.source_uuid,
        )
    )

    return pipeline_run.metrics


def parse_line(line: str) -> Dict:
    """
    Parses a line of text and extracts tags from the JSON data.

    Args:
        line (str): The input line to parse.

    Returns:
        Dict: A dictionary containing the extracted tags.

    Example:
        >>> line = '2023-01-01T12:34:56 {"tags": {"tag1": "value1", "tag2": "value2"}}'
        >>> parse_line(line)
        {'tag1': 'value1', 'tag2': 'value2'}
    """
    tags = {}

    # Remove timestamp from the beginning of the line
    text = re.sub(r'^[\d]{4}-[\d]{2}-[\d]{2}T[\d]{2}:[\d]{2}:[\d]{2}', '', line).strip()

    try:
        data1 = json.loads(text)
        if type(data1) is str:
            return tags
        tags = data1.get('tags', {})
        message = data1.get('message', '')
        try:
            data2 = json.loads(message)
            tags.update(data2.get('tags', {}))
        except json.JSONDecodeError:
            tags.update(data1)
            if 'error_stacktrace' in data1:
                tags['error'] = data1['error_stacktrace']
            if 'error' in data1:
                tags['errors'] = data1['error']
    except json.JSONDecodeError:
        pass

    return tags


def get_metrics(
    logs_by_uuid: Dict, key_and_key_metrics: List[Tuple[str, List[str]]]
) -> Dict:
    metrics = {}

    for uuid in logs_by_uuid.keys():
        metrics[uuid] = {}

        for key, key_metrics in key_and_key_metrics:
            metrics[uuid][key] = {}

            logs_for_uuid = logs_by_uuid[uuid][key]
            for logs in logs_for_uuid:
                temp_metrics = {}

                for _, l in enumerate(logs):
                    tags = parse_line(l)
                    if not tags:
                        continue

                    for key_metric in key_metrics:
                        if key_metric in tags:
                            if key_metric not in temp_metrics or key != KEY_DESTINATION:
                                temp_metrics[key_metric] = [tags[key_metric]]
                            else:
                                temp_metrics[key_metric].append(tags[key_metric])

                for key_metric, value_list in temp_metrics.items():
                    if key_metric not in metrics[uuid][key]:
                        metrics[uuid][key][key_metric] = 0

                    for value in value_list:
                        if type(value) is int:
                            metrics[uuid][key][key_metric] += value
                        else:
                            metrics[uuid][key][key_metric] = value

    return metrics
