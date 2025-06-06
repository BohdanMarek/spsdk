#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2025 NXP
#
# SPDX-License-Identifier: BSD-3-Clause
"""Nxpimage BEE group."""

import logging

import click

from spsdk.apps.utils.common_cli_options import (
    SpsdkClickGroup,
    spsdk_config_option,
    spsdk_family_option,
    spsdk_output_option,
)
from spsdk.apps.utils.utils import filepath_from_config
from spsdk.image.bee import Bee
from spsdk.utils.config import Config
from spsdk.utils.family import FamilyRevision
from spsdk.utils.misc import get_printable_path, write_file

logger = logging.getLogger(__name__)


@click.group(name="bee", cls=SpsdkClickGroup)
def bee_group() -> None:
    """Group of sub-commands related to BEE."""


@bee_group.command(name="export", no_args_is_help=True)
@spsdk_config_option(klass=Bee)
def bee_export_command(config: Config) -> None:
    """Generate BEE Images from YAML/JSON configuration.

    The configuration template files could be generated by subcommand 'get-template'.
    """
    bee_export(config)


def bee_export(config: Config) -> None:
    """Generate BEE Images from YAML/JSON configuration."""
    bee = Bee.load_from_config(config)

    output_folder = config.get_output_file_name("output_folder")
    output_name = filepath_from_config(config, "output_name", "encrypted", output_folder)

    write_file(bee.export(), output_name, mode="wb")
    logger.info(f"Created BEE Image:\n{get_printable_path(output_name)}")

    for idx, header in enumerate(bee.export_headers()):
        if header:
            header_output = filepath_from_config(
                config, "header_name", "bee_ehdr", output_folder, file_extension=f"{idx}.bin"
            )
            write_file(header, header_output, mode="wb")
            logger.info(f"Created BEE Header:\n{get_printable_path(header_output)}")

    click.echo("Success. BEE files have been created")


@bee_group.command(name="get-template", no_args_is_help=True)
@spsdk_family_option(families=Bee.get_supported_families())
@spsdk_output_option(force=True)
def bee_get_template_command(family: FamilyRevision, output: str) -> None:
    """Create template of configuration in YAML format.

    The template file name is specified as argument of this command.
    """
    bee_get_template(family, output)


# pylint: disable=unused-argument    # preparation for the future
def bee_get_template(family: FamilyRevision, output: str) -> None:
    """Create template of configuration in YAML format."""
    click.echo(f"Creating {output} template file.")
    write_file(Bee.get_config_template(family), output)
